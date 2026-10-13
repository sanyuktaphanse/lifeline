# Licences

Lifeline is released under the MIT licence in `LICENSE`, copyright 2026 the Lifeline team: Sanyukta, Joanne and Pearlin.

This page lists the licence of every third party component Lifeline installs or downloads, as each component's own metadata or repository states it. It was read on 13 October 2026.

## Python packages in `requirements.txt`

Each licence was read with `pip show` from the installed package, `License-Expression` where the package sets it and `License` otherwise. Only the packages `requirements.txt` names are listed, not the packages they pull in.

| Package | Version installed | Licence |
| --- | --- | --- |
| pydantic | 2.13.5 | MIT |
| pytest | 9.1.1 | MIT |
| PyYAML | 6.0.3 | MIT |
| anthropic | 1.3.0 | MIT |
| dashscope | 1.27.3 | Apache 2.0 |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| fastapi | 0.141.1 | MIT |
| starlette | 1.6.0 | BSD-3-Clause |
| uvicorn | 0.52.4 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |

## Node packages in `app/package.json`

The licence was read from the `license` field of each package's own `package.json` in `app/node_modules`. The app has one dependency, a development dependency for its tests, and it installs the packages below it.

| Package | Version | Licence |
| --- | --- | --- |
| @playwright/test, named in `app/package.json` | 1.56.1 | Apache-2.0 |
| playwright, installed by @playwright/test | 1.56.1 | Apache-2.0 |
| playwright-core, installed by playwright | 1.56.1 | Apache-2.0 |
| fsevents, installed by playwright on macOS only | 2.3.2 | MIT |

## What `chain/setup.sh` downloads

The licence was read from each project's own repository at the version used.

| Component | Version | Where it comes from | Licence |
| --- | --- | --- | --- |
| FISCO BCOS node binary | v3.16.4 | The release archive `fisco-bcos-linux-<arch>.tar.gz` of github.com/FISCO-BCOS/FISCO-BCOS, downloaded by `chain/nodes_in_container.sh` | Apache License 2.0, `LICENSE` at tag v3.16.4 |
| `build_chain.sh` | v3.16.4 | `tools/BcosAirBuilder/build_chain.sh` in the same repository, downloaded by `chain/nodes_in_container.sh` | Apache License 2.0, the repository's `LICENSE` at tag v3.16.4 |
| solc image `ethereum/solc:0.8.11` | 0.8.11 | The Solidity compiler, github.com/argotorg/solidity, formerly github.com/ethereum/solidity, run by `chain/setup.sh` | GNU General Public License v3, `LICENSE.txt` at tag v0.8.11 |

The compiler is run as a tool from its image, and no compiler code is in this repository.
