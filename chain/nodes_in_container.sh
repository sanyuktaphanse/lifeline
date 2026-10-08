#!/usr/bin/env bash
# Runs inside the container: builds four nodes with the official build_chain.sh once, then starts them.
set -euo pipefail
VERSION="v3.16.4"
cd /chain
if ! command -v curl >/dev/null || ! command -v openssl >/dev/null || ! command -v uuidgen >/dev/null; then
    apt-get update -qq && apt-get install -y -qq curl openssl uuid-runtime >/dev/null
fi
if [[ ! -d nodes/127.0.0.1 ]]; then
    case "$(uname -m)" in
        aarch64|arm64) ARCH="aarch64" ;;
        *) ARCH="x86_64" ;;
    esac
    [[ -f build_chain.sh ]] || curl -sSfL -o build_chain.sh "https://raw.githubusercontent.com/FISCO-BCOS/FISCO-BCOS/${VERSION}/tools/BcosAirBuilder/build_chain.sh"
    curl -sSfL -o "fisco-bcos-linux-${ARCH}.tar.gz" "https://github.com/FISCO-BCOS/FISCO-BCOS/releases/download/${VERSION}/fisco-bcos-linux-${ARCH}.tar.gz"
    tar -xzf "fisco-bcos-linux-${ARCH}.tar.gz"
    bash build_chain.sh -l 127.0.0.1:4 -p 30300,20200 -o nodes -e ./fisco-bcos
    for node in nodes/127.0.0.1/node*; do
        # Plain HTTP on the native RPC; this network only listens inside the container and on localhost.
        sed -i 's/^\(\s*\)enable_ssl=true/\1enable_ssl=false/' "${node}/config.ini"
    done
fi
bash nodes/127.0.0.1/start_all.sh
sleep 3
tail -F nodes/127.0.0.1/node0/log/* 2>/dev/null
