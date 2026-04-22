# builder methodology rules

The builder is a YAML-driven executor for **FPGA development on Windows** (Questa + Quartus). Python implements primitives; policy lives in YAML.

## Source of truth

- `tools/build/build.yaml` — targets and steps, `depends_on`, review hints.
- `cfg/ip.yaml` — per-IP filelists, tops, tests, regressions, `output_layout` paths.
- `cfg/env.yaml` — tool executables and shell export contract.
- Do not duplicate this structure in ad hoc Python.

## Graph and execution

- Targets list `root_steps`; steps list `depends_on`.
- Parallelism: multiple targets in one invocation may run concurrently; respect shared `workdir` conventions.
- Questa `work` libraries live under `workdir/<tag>/<ip>/compile/` for compile/sim; lint uses `workdir/.../lint/`.

## UX

- Print resolved `./build ...` before work.
- Status lines: wait → start → done-pass / done-fail with duration.
- On failure, print review paths (logs, waves).
- Interactive `-test` / `-regress` when name omitted is allowed.

## Artifacts

- Generated absolute filelists: `workdir/<tag>/<ip>/filelist/`.
- Logs, VCDs, Quartus `quartus.log` and `quartus/output_files/` reports: under `workdir/<tag>/<ip>/...` per `cfg/ip.yaml` `output_layout`.

## Entrypoints

- `cfg/env.sh` — materialize exports from `cfg/env.yaml`.
- `./build` — **the** user-facing flow (lint, compile, test, regress, fpga, qa, debug).
- Do not document raw `vlog`/`quartus_map` as the primary interface; wrap via `./build`.

## Avoid

- Hidden defaults not present in YAML.
- Path discovery by scanning the repo.
- Reintroducing Linux-only or Verilator/Yosys/SBY flows without restoring full config and CI support.
