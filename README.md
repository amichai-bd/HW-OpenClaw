# HW-OpenClaw

HW-OpenClaw is a **Windows + Git Bash** hardware repository: SystemVerilog RTL, pure-SystemVerilog DV, a **YAML-driven `./build` flow** using **Intel Questa/ModelSim** (`vlib`, `vlog`, `vsim`) and **Intel Quartus** for FPGA work. Legacy `src/fv/`, `src/syn/`, and `src/pd/` trees remain as reference; the **supported** builder targets are lint, compile, sim, regress, Quartus smoke (`-fpga`), and QA.

## Status

Main branch ([`ci`](.github/workflows/ci.yml) workflow on `main`):

[![ci on main](https://github.com/amichai-bd/HW-OpenClaw/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/amichai-bd/HW-OpenClaw/actions/workflows/ci.yml?query=branch%3Amain)

The badge reflects the latest completed GitHub Actions run for `main`, not the state of open pull requests.

## Repository structure

```text
.
├── bin/
│   ├── build
│   └── setup
├── wiki/
│   ├── Home.md
│   ├── dv/
│   ├── fv/
│   ├── rtl/
│   ├── syn/
│   ├── pd/
│   └── flows-methods-phylosophy/
├── cfg/
│   ├── env.sh
│   ├── env.yaml
│   └── ip.yaml
├── src/
│   ├── dv/
│   │   └── <ip>/
│   │       ├── code/
│   │       │   ├── env/
│   │       │   ├── if/
│   │       │   ├── pkg/
│   │       │   ├── tb/
│   │       │   └── tests/
│   │       ├── filelist/
│   │       └── regressions/
│   ├── fv/
│   │   ├── common/
│   │   │   ├── assumptions/
│   │   │   └── scripts/
│   │   └── <ip>/
│   │       ├── code/
│   │       ├── proofs/
│   │       └── properties/
│   ├── pd/
│   │   ├── common/
│   │   │   └── scripts/
│   │   └── <ip>/
│   ├── rtl/
│   │   ├── common/
│   │   │   └── include/
│   │   └── <ip>/
│   │       ├── code/
│   │       ├── lint/
│   │       └── filelist_rtl_<ip>.f
│   └── syn/
│       └── common/
│           ├── lib/
│           └── scripts/
├── tools/
│   ├── README.md
│   └── build/
│       ├── build.py
│       └── build.yaml
└── workdir/
```

## Design rules

- Spec-driven development: repo-root `wiki/` is the specification surface; see `AGENTS.md` and `.codex/rules/`.
- YAML is the source of truth: `tools/build/build.yaml`, `cfg/ip.yaml`, `cfg/env.yaml`.
- `cfg/env.sh` exports environment data from `cfg/env.yaml` for Git Bash.
- RTL filelists use `$MODEL_ROOT`; the builder writes resolved filelists under `workdir/<tag>/<ip>/filelist/`.
- Shared RTL headers live under `src/rtl/common/`.
- DV follows the existing package/env/tb/tests layout under `src/dv/<ip>/`.

## Quick start

Install **PyYAML** (`pip install pyyaml`), **Questa/ModelSim**, and **Quartus** (on `PATH` or set absolute paths in `cfg/env.yaml` / `cfg/env.local.yaml`).

```sh
. cfg/env.sh
./build -h
./build -ip fifo -qa
./build -ip fifo -lint -compile -test sanity -tag dev1
./build -ip fifo -regress level_0 -tag dev1
./build -ip fifo -fpga -tag q1
```

Waveforms (optional GTKWave):

```sh
./build -debug
```

`./build` sources `cfg/env.sh` then runs `tools/build/build.py`. `-debug` must be used alone; `-test` and `-regress` are mutually exclusive.

```sh
./setup
./setup --check
```

`./setup` prints Windows-oriented notes; `./setup --check` runs `version_cmd` for each tool in `cfg/env.yaml` (use `--ci` to relax failures on CI where EDA tools are absent).

## CI

- [.github/workflows/ci.yml](.github/workflows/ci.yml) runs on **windows-latest**: Python syntax check and `build.py -h`. Full Questa/Quartus runs are expected on **developer machines** with tools installed.
- PR-Agent and CodeRabbit workflows are unchanged; see `.pr_agent.toml` and `.coderabbit.yaml`.
- Wiki publish skill: [.codex/skills/update-wiki/](.codex/skills/update-wiki/).

## Current flow

- **Lint:** `vlog -lint` on RTL filelist (`tools/build/build.yaml` → `lint_sim`).
- **Compile:** `vlib` + `vlog` on full filelist (`compile_sim`).
- **Test / regress:** `vsim -c` with existing plusargs (`simulate_sim`); outputs under `workdir/<tag>/<ip>/tests/` or `regressions/`.
- **FPGA:** `-fpga` writes `synth_hw.tcl` under `workdir/.../quartus/` (from `cfg/ip.yaml` `fpga:` and the RTL filelist) and runs `quartus_sh -t synth_hw.tcl` (`execute_flow -compile`). With `-test`/`-regress`, FPGA runs **after** per-test vlog → vsim → review.
- **QA:** structure, filelists, wiki RTL/DV pages, style rules → `workdir/.../qa/qa_report.txt`.

## Development workflow

- Start meaningful changes from an issue.
- Start the issue according to the relevant wiki page or wiki path.
- Tag the issue with the correct labels for the type of change.
- Implement each issue on a short-lived branch named with the issue number prefix.
- Open a pull request before merging to `main`.
- Reference the relevant wiki path in the pull request as well.
- After a pull request is opened, keep ownership of it until it is green, merged, and synced back to local `main`.
- PR-Agent findings are part of the PR ownership model. If PR-Agent raises review findings, address them on the same branch before merge.
- CodeRabbit findings and open review threads are also part of the PR ownership model. If CodeRabbit raises review findings, address them on the same branch before merge.
- Treat the two review systems slightly differently:
  - PR-Agent is primarily a required CI-style review check plus structured review comment.
  - CodeRabbit is primarily a required GitHub App review/check that can also hold merge through unresolved review threads.
- Native GitHub auto-merge is the expected finish path once the required PR/build checks and conversation-resolution requirements are satisfied.
- The agent that opened the pull request should keep polling its checks and review state, fix issues on the same branch, and stay with it until merge completes.
- Merge, delete the branch, and sync local workspaces back to `main`.
