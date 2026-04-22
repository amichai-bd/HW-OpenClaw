# software stack

This page defines **what tools the repository assumes today** and how responsibilities are split. Install recipes live in `AGENTS.md` and `cfg/env.yaml`; this page is **intent and boundaries**.

## Supported platform

- **Host:** **Windows + Git Bash** (the only first-class environment for `./build` and `./setup`).
- **Simulation / RTL–DV compile:** **Intel Questa / ModelSim** — `vlib`, `vlog`, `vsim` (declared in `cfg/env.yaml`).
- **FPGA:** **Intel Quartus Prime** — `quartus_sh` (and related tools on `PATH`); project generation and compile are driven by `./build -fpga`. See [fpga-quartus-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/fpga-quartus-methodology).

## Tier 1 — Daily engineering (`./setup` + `./build`)

**Role:** Spec-driven **RTL**, **DV**, **`vlog -lint`**, **`vlib`/`vlog` compile**, **`vsim` tests/regressions**, **`-qa`**, and **optional `-fpga`** when Quartus is installed locally.

**Source of truth:** `cfg/env.yaml`, `cfg/ip.yaml`, `tools/build/build.yaml`, `tools/build/build.py`.

**Typical targets:** `-qa`, `-lint`, `-compile`, `-test`, `-regress`, `-fpga`, `-debug` (GTKWave). CI on GitHub-hosted runners exercises **Python-level checks** only; full EDA runs are **local** with tools on `PATH` or overrides in `cfg/env.local.yaml`.

## Tier 2 — (Historical) ASIC-style formal, Yosys synth, OpenROAD PD

Formal verification, Yosys-based synthesis scaffolds, and OpenROAD-class physical design were part of an **earlier multi-tool vision**. **`src/fv/`, `src/syn/`, `src/pd/`** and matching wiki trees remain as **historical reference**; they are **not** part of the default `./build` contract today. Do not assume `cfg/fv.yaml`, `cfg/synth.yaml`, or `cfg/pd.yaml` exist in a minimal clone.

For methodology text that still describes those flows, see the **Historical / legacy** banners on the linked pages from [Home](/amichai-bd/HW-OpenClaw/wiki/Home).

## How the active pieces connect

```text
RTL + DV  →  ./setup (tools check)  →  ./build -lint -compile -test …
                                    →  ./build -fpga  (Quartus, RTL from generated filelists)
```

## Related pages

- [fpga-quartus-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/fpga-quartus-methodology)
- [builder-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/builder-methodology)
