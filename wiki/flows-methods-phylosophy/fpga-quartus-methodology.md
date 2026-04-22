# FPGA / Quartus methodology (active stack)

This page matches the **supported** HW-OpenClaw flow: **Intel Quartus** for FPGA implementation, driven from `./build -fpga` and `cfg/ip.yaml` per-IP `fpga:` settings.

## Principles

- **Device reality:** family, device package, pin constraints, and SDC belong in FPGA-specific collateral (Tcl fragments, checked-in `.sdc`, or extended `synth_hw.tcl`), not mixed into generic RTL without intent.
- **Reproducible runs:** The builder writes `workdir/<tag>/<ip>/quartus/synth_hw.tcl`, runs `quartus_sh -t synth_hw.tcl`, and keeps logs under `quartus/quartus.log` and `quartus/output_files/`.
- **Simulation before FPGA (optional):** When `-fpga` is combined with `-test` or `-regress`, Quartus runs **after** simulation completes (per test: `vlog` → `vsim` → log review).

## Failure triage

When Quartus fails, the builder prints **`[quartus-triage]`** lines on **stderr**, including:

- **`primary_reports=`** — paths to `output_files/<revision>.{fit,sta,map,flow}.rpt` when they exist (or any `*.fit.rpt` / `*.sta.rpt` fallback).
- **`log_grep=`** — a copy-pastable `rg` hint against `quartus.log`.
- **`first_N_matching_lines_from_quartus.log`** — early error-like lines from the log so you do not open multi‑MB files blindly.

## Related

- [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack)
- [builder-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/builder-methodology)
- Repo `AGENTS.md` and `.codex/rules/fpga-quartus-methodology.md`
