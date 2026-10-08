"""Deploy LifelineEvidence to the local FISCO BCOS network over its web3 JSON RPC and print the settings.

Run by setup.sh after the network is up and the contract is compiled into chain/build/. It creates the
anchor key in chain/anchor.key when there is none, which git ignores, and never prints the key.
"""

import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.anchor_fisco import FiscoConfig, JsonRpcTransport, _private_key  # noqa: E402
from core.evm_tx import address_of  # noqa: E402

CHAIN = ROOT / "chain"
KEY = CHAIN / "anchor.key"
BYTECODE = CHAIN / "build" / "LifelineEvidence.bin"
DEPLOYMENT = CHAIN / "deployment.json"
RPC_URL = "http://127.0.0.1:20200"
# secp256k1's group order: a private key is a whole number from one to below it.
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def main() -> None:
    if not KEY.exists():
        key = secrets.randbelow(ORDER - 1) + 1
        KEY.write_text(f"{key:064x}\n", encoding="utf-8")
        KEY.chmod(0o600)
    config = FiscoConfig(RPC_URL, "", str(KEY))
    private_key = _private_key(str(KEY))
    receipt = JsonRpcTransport().send_raw(config, private_key, "", bytes.fromhex(BYTECODE.read_text().strip()))
    address = receipt.get("contractAddress")
    if not address:
        raise SystemExit(f"The deployment was mined with no contract address: {receipt}")
    DEPLOYMENT.write_text(json.dumps({"contract_address": address, "transaction": receipt["transactionHash"],
                                      "block": int(receipt["blockNumber"]), "sender": address_of(private_key)}, indent=2))
    print(f"LifelineEvidence deployed at {address} in block {int(receipt['blockNumber'])}.")
    print("Set these in .env to anchor on this network:")
    print("ANCHOR=fisco")
    print(f"FISCO_RPC_URL={RPC_URL}")
    print(f"FISCO_CONTRACT_ADDRESS={address}")
    print(f"FISCO_KEY_PATH={KEY}")


if __name__ == "__main__":
    main()
