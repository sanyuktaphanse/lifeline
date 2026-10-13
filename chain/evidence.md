# Chain record

What ran on the local FISCO BCOS network, on which machine, with block numbers, head hashes and times. Every value below was read from the running chain with its native JSON RPC, or from `data/ledger.jsonl`, on 13 October 2026, by commands given at the end of this page. Nothing here was typed from memory.

## The machine

A Mac with Apple silicon, Darwin 24.6.0 on arm64, running Docker Desktop. The network is the container `chain-fisco-1`, image `ubuntu:24.04`, which `chain/setup.sh` started: four nodes of FISCO BCOS v3.16.4 on 127.0.0.1, with node0's native JSON RPC on port 20200. On 13 October 2026 the container had been up for 4 days. The contract `LifelineEvidence.sol` is at `0x6849f21d1e455e9f0712b1e99fa4fcd23758e8f1`, deployed by the anchor account `0x5773c3ffecd80168f204d67ba77260e9a3eed4e2`, as `chain/deployment.json` records.

## The run of 8 October 2026

`chain/README.md` tells this run. The first network was built on 8 October and its first anchor was confirmed at 14:47:40 UTC in block 3. An attacker's malformed transaction then stopped that network at block 5, so it was removed and rebuilt, and the contract deployed again. The blocks below belong to the rebuilt network, which is the one still running; the first network's blocks no longer exist.

| Block | Block time, UTC | What it holds | Head hash | Head sequence |
| --- | --- | --- | --- | --- |
| 1 | 2026-10-08 15:14:15.709 | The contract deployed, transaction `0xf96691269f8d137be9865894b5978680e469c349d5262cec31ef3fcd3dd113be` | none | none |
| 3 | 2026-10-08 15:14:31.178 | An anchor, transaction `0x2e7e3d120d1affdcda7b644e8a1c5a949e930a6a564dd40882649a5d5a01dc4c` | `1247d085cd0ad47640ce18b37c9a4b3fc3b46b59f702fde4f9c1227e6a09847d` | 1 |
| 7 | 2026-10-08 15:15:05.264 | The anchor of a rent payment made through the API with `ANCHOR=fisco`, transaction `0xc39d81e0ba7e92fc02942506c2b81aa7153c166f7a65982ca3b936318dc5bb8a` | `fe0593bc0d5d22758915a5296bf0d22abd015c965bf97226e35b4172fa6674b2` | 7 |

Blocks 2, 4, 5 and 6 each hold one more transaction to the contract; block 5's was sent from another account, `0xb595b18c88b1f651ca387489067f855b5c8e6720`. For blocks 3 and 7, the contract's `verify` returns a record written by the anchor account with the same block number and the same time as the block, so `FiscoBcosAnchor.verify` reports both heads anchored.

The head anchored in block 7 is in none of the ledgers in `data/` or in the `data_` folders beside it on this machine.

## The anchors in `data/ledger.jsonl`

The demo ledger in `data/`, which the API writes, holds 249 entries and verifies with no break. Its 8 anchor entries are all local, signed into `data/anchors.jsonl`, at sequences 44, 58, 93, 144, 152, 182, 218 and 249, from 2026-10-09 11:26:28 UTC to 2026-10-11 12:56:42 UTC. None of them is on the chain, because the API ran with the default `ANCHOR=local`.

## The anchor of 13 October 2026

The head of `data/ledger.jsonl` was anchored on the chain on 13 October 2026, through `FiscoBcosAnchor` from `core/anchor_fisco.py`, the class the loop uses with `ANCHOR=fisco`. The ledger was only read: its SHA 256 was `17ec0e4a3f1d16b2c290a2766c6dd29b2e4460bfb56969d3699bed15230798d4` before and after, and no anchor entry was added to it.

| Block | Block time, UTC | Transaction | Head hash | Head sequence |
| --- | --- | --- | --- | --- |
| 8 | 2026-10-13 08:26:24.802 | `0xa02b493eb1e01c8acf36c354f1f3c1914b581d1cbbad251ccb352f57e75b0e2d` | `233f9d3024d9585d744de8435a4ccd2cfc2d351e3ac18a67dede1de12a74dce9` | 249 |

`FiscoBcosAnchor.verify` then returned true for that head, with block 8 and the sender `0x5773c3ffecd80168f204d67ba77260e9a3eed4e2`. The chain's block number went from 7 to 8.

## How to read it again

With the network running, from the repository root:

```bash
curl -s -X POST http://127.0.0.1:20200 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"getBlockByNumber","params":["group0","",7,false,true],"id":1}'
curl -s -X POST http://127.0.0.1:20200 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"getTransaction","params":["group0","","0xc39d81e0ba7e92fc02942506c2b81aa7153c166f7a65982ca3b936318dc5bb8a",false],"id":1}'
```

The block's `timestamp` is in milliseconds. A transaction's `input` is the selector `70c127c6` of `anchor(bytes32,uint64,bytes32)`, then the head hash, then the head sequence as a 32 byte number, then the keyed hash of the user id. With `FISCO_RPC_URL`, `FISCO_CONTRACT_ADDRESS` and `FISCO_KEY_PATH` set as `chain/setup.sh` prints them, `FiscoBcosAnchor().record_of(head_hash)` reads the contract's record of a head.
