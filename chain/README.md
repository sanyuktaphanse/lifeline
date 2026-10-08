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

## How the client reaches the chain

`core/anchor_fisco.py` tries two routes, each behind a small adapter a test can fake. The first is the FISCO BCOS Python SDK, which is not on PyPI and is not installed here, so it reports itself unavailable. The second is the node's native JSON RPC. A transaction is built in FISCO BCOS's TARS format, hashed and signed with secp256k1 in pure Python by `core/fisco_tx.py` and `core/evm_tx.py`, and sent with `sendTransaction`, which answers with the receipt once the transaction is in a block. No package was added.

## What did not work, and what was not tried

1. The node's Ethereum compatible web3 JSON RPC, on port 8545, was tried first. It refuses every transaction whose sender has a zero balance, with `InsufficientFunds`, even at a gas price of zero, and the anchor account holds none. Granting a balance needs the chain's balance feature and a governor transaction, which was not attempted, so the client uses the native RPC instead.
2. The first container ran Ubuntu 22.04, whose glibc is older than the 2.38 the v3.16.4 binary needs, so the nodes started and exited. Ubuntu 24.04 fixed it.
3. Nothing was tried against a network of more than one machine, with SM cryptography, with SSL on the RPC, or with the permission model turned on.
