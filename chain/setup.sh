#!/usr/bin/env bash
# Start a four node local FISCO BCOS network with the official build_chain.sh, compile and deploy
# LifelineEvidence, and print the settings for .env. Needs docker. Lifeline never needs this to run.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-../.venv/bin/python}"

docker compose up -d
echo "Waiting for node0's JSON RPC on 127.0.0.1:20200..."
for _ in $(seq 1 60); do
    if curl -sS -m 2 -X POST -H 'Content-Type: application/json' \
        --data '{"jsonrpc":"2.0","method":"getBlockNumber","params":["group0",""],"id":1}' http://127.0.0.1:20200 >/dev/null 2>&1; then
        break
    fi
    sleep 5
done

# The official solc image, for the London EVM the FISCO BCOS 3.x EVM runs.
docker run --rm -v "$PWD":/src ethereum/solc:0.8.11 --optimize --bin --abi --evm-version london --overwrite -o /src/build /src/LifelineEvidence.sol

"$PYTHON" deploy.py
