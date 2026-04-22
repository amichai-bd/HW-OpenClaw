# AGENTS.md — HW-OpenClaw

Operating contract for agents in **this repository only**. The product is an **FPGA-oriented**, **Windows + Git Bash** hardware flow: **Questa/ModelSim** (`vlib`, `vlog`, `vsim`) for RTL/DV and **Intel Quartus** for FPGA implementation. There is **no** Linux/WSL path, **no** Verilator, **no** Yosys/SBY formal flow, and **no** ASIC-style physical-design scaffold in the active builder.

## Read order

1. This file.
2. `wiki/Home.md` for navigation.
3. `.codex/rules/README.md` and the rule file for the task (`rtl-coding-style.md`, `dv-methodology.md`, `fpga-quartus-methodology.md`, `builder-methodology.md`, `github-flow.md`).
4. Wiki canon for stack and lint: `wiki/flows-methods-phylosophy/software-stack.md`, `wiki/flows-methods-phylosophy/fpga-quartus-methodology.md`, `wiki/flows-methods-phylosophy/lint-methodology.md`.
5. Mirrored wiki under `wiki/rtl/`, `wiki/dv/`, and `wiki/flows-methods-phylosophy/` when changing behavior or structure.

## Repository layout (FPGA stack)

```text
bin/       user entrypoints (build, etc.)
cfg/       YAML: env + IP metadata (paths, tops, tests)
.codex/    agent rules + skills
src/rtl/   SystemVerilog RTL
src/dv/    dynamic verification (tb, env, tests, regressions)
tools/     builder implementation
wiki/      version-controlled spec surface
workdir/   generated outputs (gitignored)
```

Legacy directories under `src/fv/`, `src/syn/`, and `src/pd/` may still exist as **historical reference**; the **supported** flow is RTL + DV + Quartus. Do not add new formal or ASIC-PD dependencies without an explicit repo decision.

## Standard commands

- Shell: `. cfg/env.sh` (exports from `cfg/env.yaml`).
- Build: `./build` → `bin/build` → `tools/build/build.py`.

Typical invocations:

```bash
./build -ip fifo -qa -lint -compile -test sanity -tag dev1
./build -ip fifo -regress level_0 -tag dev1
./build -ip fifo -fpga -tag q1
./build -ip fifo -compile -test sanity -fpga -tag q1   # vlog→vsim→review, then Quartus
```

- `-qa` — structure, filelists, wiki presence, RTL/DV style rules.
- `-lint` — `vlog -lint` on RTL filelist.
- `-compile` — `vlib` + `vlog` on full DV filelist.
- `-test` / `-regress` — per test: **`vlog`** (logged to `tests/<name>/vlog.log`) → **`vsim`** → **review** (tails logs + artifact paths), then any later targets.
- `-fpga` — writes `workdir/<tag>/<ip>/quartus/synth_hw.tcl` from `cfg/ip.yaml` `fpga:` + RTL filelist, runs **`quartus_sh -t synth_hw.tcl`** (full `execute_flow -compile`). If `-test` or `-regress` is also selected, FPGA runs **after** simulation completes. On failure, stderr includes **`[quartus-triage]`** (key `.rpt` paths, a suggested `rg` line, and the first matching error lines from `quartus.log`).
- `-debug` — GTKWave on saved VCDs (optional tool).

Override environment file: `HW_OPENCLAW_ENV_FILE` or `cfg/env.local.yaml` (gitignored).

## Tooling assumptions

- **Host:** Windows, **Git Bash** (USB-friendly FPGA programming).
- **EDA:** Questa/ModelSim and Quartus on **PATH** or set absolute `exe` paths in `cfg/env.yaml` / `env.local.yaml`.
- **Python:** `python` on PATH for `cfg/env.sh` and the builder.

## Spec and process

- Spec-driven: meaningful changes tie to issues and `wiki/` paths.
- PRs reference wiki; keep `.codex/rules/` aligned when agent-facing guidance changes.
- PR-Agent / CodeRabbit expectations remain as configured in `.pr_agent.toml` / `.coderabbit.yaml`.

## Agent email

- Use `.codex/skills/send-email/` for outbound mail; do not commit secrets (`~/.openclaw/secrets/agentmail.env`).

## Wiki mirror

- Publish the GitHub wiki mirror with `.codex/skills/update-wiki/` when needed.
