# FPGA / Quartus methodology rules

FPGA implementation is a first-class discipline, separate from RTL lint and Questa simulation.

## Principles

- **Device and tool reality:** pinouts, clocks, and IO standards belong in FPGA-specific collateral (constraints, top-level wrappers), not scattered in generic RTL.
- **Reproducible builds:** The builder writes **`synth_hw.tcl`** under `workdir/<tag>/<ip>/quartus/` from `cfg/ip.yaml` `fpga:` (family, device, revision, top_entity) plus the **generated RTL filelist** (`+incdir+` → `SEARCH_PATH`, sources → `SYSTEMVERILOG_FILE`). Quartus then runs **`quartus_sh -t synth_hw.tcl`** with `execute_flow -compile`; `.qpf`/`.qsf` appear in that same directory after `project_new`. Commit templates only if you need hand-edited assignments beyond what Tcl generates.
- **Order with simulation:** When `-fpga` is combined with `-test` or `-regress`, the builder runs FPGA **after** each simulation path finishes (per test: `vlog` → `vsim` → log review), matching a bring-up style similar in spirit to **fpga_mafia** (`-hw` then `-sim` then `-fpga`).

## Checklist (when extending the default Tcl flow)

- [ ] `cfg/ip.yaml` `fpga:` matches the **real board** (device, package, family).
- [ ] Constraints (SDC, pin assignments) added to Tcl or checked-in `.qsf` fragments once the auto project is stable.
- [ ] MIF/hex load paths documented if soft CPU or embedded memories are used.
- [ ] `quartus.log` under `workdir/.../quartus/` is the first review artifact on failure; the builder also prints **`[quartus-triage]`** (report paths, `rg` hint, first error-like log lines) on stderr when `quartus_sh` fails.

## Naming

- Prefer clear `fpga/` or `quartus/` directories per IP when projects grow; keep paths declared in `cfg/ip.yaml` or a dedicated FPGA config file the builder reads.
