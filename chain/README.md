# The FISCO BCOS anchor

Lifeline can anchor its ledger head on a FISCO BCOS chain instead of in the local signed file. The chain is optional. `ANCHOR=local` is the default, CI never starts a network, and every test that needs one is skipped unless a node answers at `FISCO_RPC_URL`. Nothing about a payment depends on the chain: when the chain cannot be reached, the loop writes an `anchor_failed` note and the payment goes on.

## What reaches the chain

`LifelineEvidence.sol` stores, for each anchored head, the head hash, its sequence number, a SHA 256 hash of the user id, the block time, the block number and the sender. It holds no funds and no balances, accepts no payment, and stores no names, amounts, payees or user ids.

## What worked on this machine

Anchoring worked on 8 October 2026, on a Mac with Apple silicon running Docker Desktop. The ninety minute cap on the wiring started at 14:37 UTC; the first real anchor was confirmed at 14:47:40 UTC, and the wiring was finished at 14:49, about twelve minutes of the cap.

1. `docker compose up -d` in this folder started an Ubuntu 24.04 container that downloads the official `build_chain.sh` and the `fisco-bcos-linux-aarch64` binary of FISCO BCOS v3.16.4, released on 14 January 2026, and builds and starts four nodes on 127.0.0.1, with the native JSON RPC of node0 on port 20200 without SSL.
2. The official `ethereum/solc:0.8.11` image compiled the contract for the London EVM into `build/`.
3. `deploy.py` created an anchor key in `anchor.key` and deployed the contract in block 1.
4. `FiscoBcosAnchor` anchored a head in block 3, verified it, and read back its block number and block time, and `tests/test_anchor_fisco.py` passed its integration test against the node.

`setup.sh` runs steps 1 to 3 and prints the four settings for `.env`:

```
bash chain/setup.sh
ANCHOR=fisco
FISCO_RPC_URL=http://127.0.0.1:20200
FISCO_CONTRACT_ADDRESS=<the address it prints>
FISCO_KEY_PATH=<this folder>/anchor.key
```

`docker compose down` in this folder stops the network. The nodes, their keys, the build output, the downloaded tooling, the anchor key and `deployment.json` are generated here and ignored by git.

## Create your own network

You need Docker running and the repository's virtual environment, made once from the repository root with `python3 -m venv .venv` and `.venv/bin/pip install -r requirements.txt`. Then, from the repository root:

```
bash chain/setup.sh
```

It starts the container, downloads the official tooling, builds and starts four nodes, compiles and deploys the contract, and prints four lines. Put them in `.env`. With them set, `.venv/bin/python -m pytest tests/test_anchor_fisco.py` runs the three live tests instead of skipping them. To use a different Python, run `PYTHON=/path/to/python bash chain/setup.sh`.

Everything it creates stays in this folder, holds your own keys, and is ignored by git through `chain/.gitignore`, so none of it can be committed:

| Path | What it is |
| --- | --- |
| `nodes/` | The four nodes, their data, logs and configuration, the chain's CA key and certificates, each node's `node.pem` and SSL key, the SDK key, and the admin account key that `build_chain.sh` creates under `nodes/ca/accounts/` |
| `build/` | The compiled contract, `LifelineEvidence.bin` and `LifelineEvidence.abi` |
| `fisco-bcos` | The node binary, unpacked from the release |
| `fisco-bcos-*.tar.gz` | The release archive it came from |
| `build_chain.sh` | The official build script, downloaded for the release |
| `anchor.key` | Lifeline's anchor account key, one private key as 64 hexadecimal characters |
| `deployment.json` | The contract address, the deployment transaction and block, and the anchor account's address |

To stop the network, run `docker compose down` in this folder. To start over with a new chain, also remove `nodes/`, `build/` and `deployment.json`, and run `bash chain/setup.sh` again. The contract accepts anchors only from the account that deployed it, so if you also remove `anchor.key`, the next run creates a new key and deploys a new contract for it, and the old address no longer works.

## How the client reaches the chain

`core/anchor_fisco.py` tries two routes, each behind a small adapter a test can fake. The first is the FISCO BCOS Python SDK, which is not on PyPI and is not installed here, so it reports itself unavailable. The second is the node's native JSON RPC. A transaction is built in FISCO BCOS's TARS format, hashed and signed with secp256k1 in pure Python by `core/fisco_tx.py` and `core/evm_tx.py`, and sent with `sendTransaction`, which answers with the receipt once the transaction is in a block. No package was added.

## After the attacker brief

An independent attacker found eight breaks, now each a test in `tests/test_attack_five.py`. One of its probes sent a transaction with a malformed contract address, which FISCO BCOS v3.16.4 accepted into its pool and then failed to execute, so the network stopped making blocks at block 5. The client now refuses such an address before sending anything. The network was rebuilt with `docker compose down`, removing `nodes/`, and `bash chain/setup.sh`, and the contract, which now accepts anchors only from the account that deployed it and never overwrites a head, was deployed again. The live tests then passed: a head anchored and verified with its block, the same head refused a second time, and another account refused. A rent payment through the API with `ANCHOR=fisco` was anchored in block 7, and the verify endpoint reported it verified with its block number.

## What did not work, and what was not tried

1. The node's Ethereum compatible web3 JSON RPC, on port 8545, was tried first. It refuses every transaction whose sender has a zero balance, with `InsufficientFunds`, even at a gas price of zero, and the anchor account holds none. Granting a balance needs the chain's balance feature and a governor transaction, which was not attempted, so the client uses the native RPC instead.
2. The first container ran Ubuntu 22.04, whose glibc is older than the 2.38 the v3.16.4 binary needs, so the nodes started and exited. Ubuntu 24.04 fixed it.
3. Nothing was tried against a network of more than one machine, with SM cryptography, with SSL on the RPC, or with the permission model turned on.
