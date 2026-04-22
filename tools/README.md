# tools

Implementations invoked by repo entrypoints (`./build`, `./setup`).

## Build orchestration

- **`tools/build/build.yaml`** — declarative targets and steps (Questa lint/compile/sim, Quartus smoke, QA).
- **`tools/build/build.py`** — executor for that graph.
- **`tools/misc/`** — optional utilities.

## Stack

- **Windows + Git Bash** only for the supported flow.
- **Questa/ModelSim:** `vlib`, `vlog`, `vsim` (paths in `cfg/env.yaml`).
- **Intel Quartus:** `quartus_map` (and future project flows under `-fpga`).
- Override tools via **`HW_OPENCLAW_ENV_FILE`** or **`cfg/env.local.yaml`**.

## Setup

`./setup` documents optional Windows prerequisites (Python, PyYAML); EDA tools are installed separately (Intel FPGA suite).
