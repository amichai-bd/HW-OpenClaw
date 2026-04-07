# AGENTS.md — HW-OpenClaw repository

## Workflow

- All meaningful changes should start as an issue.
- Each issue should be implemented on a short-lived branch.
- Branch names must include the related issue number as a prefix.
- Open a pull request for review/gating before merging to `main`.
- After merge, sync local workspace clones back to `main` before starting the next task.
- Branches are expected to be short-lived: minutes to hours, not long-running.
- After merge, delete the branch both on origin and locally.
- If a commit resolves an issue, mention the issue in the commit message and/or PR body using closing language such as `Closes #<issue>`.

## Project shape

- Hardware design / chip design project.
- SystemVerilog and Verilator are the initial focus.
- Future work may include debug trackers, formal verification, synthesis, and floorplanning.

## Communication

- Treat WhatsApp instructions as the source of task direction.
- Keep repository changes small and task-focused.
- In project text, avoid spelling out the term FIFO directly; represent the IP name as `<IP>` instead.
- The repository tree uses the lowercase structure below:

```text
.
├── bin/
├── cfg/
│   ├── env.yaml
│   ├── fv.yaml
│   ├── ip.yaml
│   └── synth.yaml
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
│   ├── rtl/
│       ├── common/
│       │   └── include/
│       └── <ip>/
│           ├── code/
│           ├── lint/
│           └── filelist_rtl_<ip>.f
│   └── syn/
│       └── common/
│           ├── lib/
│           └── scripts/
├── tools/
└── workdir/
```

## Coding style and methodology

- Module and file names should match, and both must be lowercase.
- Parameter names must be uppercase.
- Signal names should be lowercase with underscores.
- Use `always_comb` for combinational logic and `always_ff` for sequential logic. Do not use plain `always` blocks.
- Do not combine `logic` declarations with inline assignment or initialization. Keep declarations separate from behavioral assignment.
- Avoid explicit non-blocking assignment style in favor of macros when that rule is introduced later.

## Tool and config rules

- Repository tools must treat YAML files as the source of truth.
- Do not hardcode fallback paths, inferred defaults, search patterns, or directory discovery logic inside scripts.
- If a tool needs build steps, it must read them from the tool YAML file.
- If a tool needs IP-specific paths, tops, binaries, tests, regressions, or other repository locations, it must read them from the relevant config YAML file.
- Repository environment data should live in `cfg/env.yaml`, and shell tools should source `cfg/env.sh` as the entry point to that data.
- The shell export contract itself should be defined in `cfg/env.yaml`; `cfg/env.sh` should stay agnostic and only materialize the YAML-defined exports and PATH updates.
- Shared formal profile data should live in `cfg/fv.yaml`.
- Shared synthesis profile data should live in `cfg/synth.yaml`.
- User-facing repo commands should live under `bin/` as thin launchers, while implementation code should stay under `tools/`.
- Formal-specific collateral should live under `src/fv/`, not under `rtl/`, `dv/`, or `syn/`.
- Shared formal collateral such as reusable SBY scripts and common assumptions should live under `src/fv/common/`.
- Formal collateral for each IP should follow the split `code/`, `properties/`, and `proofs/`, with shared assumptions and scripts under `src/fv/common/`.
- Formal collateral should use per-IP formal filelists, following the same repository pattern as RTL and DV, instead of enumerating `.sv` sources inline in `cfg/ip.yaml`.
- Shared RTL includes, macros, and reusable generic collateral should live under `src/rtl/common/`, not under any individual IP directory.
- Cross-IP composition is allowed when architecturally intentional. Reusable generic building blocks should move to `common/`, while larger IPs may explicitly integrate smaller IPs through declared filelists and config rather than ad hoc dependency on a neighbor IP’s local collateral.
- Synthesis-specific collateral should live under `src/syn/`, not under `rtl/` or `dv/`.
- Shared synthesis collateral such as generic libraries and reusable synthesis scripts should live under `src/syn/common/`.
- IP-level formal selection should live in `cfg/ip.yaml`, while reusable formal profiles and solver metadata should live in `cfg/fv.yaml`.
- IP-level synthesis selection should live in `cfg/ip.yaml`, while reusable synthesis profiles and technology metadata should live in `cfg/synth.yaml`.
- Source filelists should be authored relative to `$MODEL_ROOT`.
- Tools should translate source filelists into generated explicit filelists under `workdir/` when downstream tools require absolute paths.
- Structured run outputs should be described in YAML and emitted under `workdir/<tag>/<ip>/...`.
- Scripts should fail clearly when required YAML keys or files are missing instead of guessing.
- RTL lint collateral such as waiver files should live under `src/rtl/<ip>/lint/` next to the RTL code.
- Formal runs should emit a machine-readable summary artifact derived from the raw SBY run outputs so automation can consume stable data without scraping SBY text logs.
- Different IPs may select different formal profiles in `cfg/ip.yaml`. Use full proofs where tractable and bounded safety profiles where state-space or memory complexity makes that the more honest first step.
- The initial synthesis flow is a generic Yosys foundation flow, not a signoff flow. Synthesis warnings from generic mapping should be captured in report artifacts under `workdir/<tag>/<ip>/synth/`, not hidden.
- Synthesis runs should also emit a machine-readable summary artifact derived from the raw reports so automation can consume stable data without scraping Yosys text logs.

## Standard DV layout

- Each IP DV environment should follow this layout:

```text
src/dv/<ip>/
├── code/
│   ├── tb/
│   │   └── <ip>_tb.sv
│   ├── if/
│   │   └── <ip>_if.sv
│   ├── pkg/
│   │   └── <ip>_dv_pkg.sv
│   ├── env/
│   │   ├── <ip>_types.sv
│   │   ├── <ip>_cfg.sv
│   │   ├── <ip>_generator.sv
│   │   ├── <ip>_driver.sv
│   │   ├── <ip>_monitor.sv
│   │   ├── <ip>_model.sv
│   │   ├── <ip>_scoreboard.sv
│   │   ├── <ip>_coverage.sv
│   │   ├── <ip>_agent.sv
│   │   ├── <ip>_env.sv
│   │   └── <ip>_tracker.svh
│   └── tests/
├── filelist/
└── regressions/
```

- `tb` should stay thin and only own top-level hookup, plusargs, DUT instantiation, and environment construction.
- `if` should own DUT-facing interface signals, clocking blocks, and modports when needed.
- `pkg` should gather reusable DV types, configuration helpers, and shared utility functions.
- `env` should contain the predictable verification component split: generator, driver, monitor, model, scoreboard, coverage, agent, env, and tracker.
- Test-specific selection should come from YAML and plusargs, not from ad hoc directory discovery or implicit defaults.

## Repository expectations

- `README.md` should describe the current repository layout and the standard developer entrypoints.
- The standard shell entrypoint is `. cfg/env.sh`.
- The standard builder entrypoint is `build` from the repo `bin/` directory after sourcing the environment.
- The standard builder flows include `build -ip <ip> -lint`, `-fv`, `-synth`, `-compile`, `-test <test>`, `-regress <regression>`, and `-debug`.
- Debug flow should prefer structured artifacts already emitted by the builder, including tracker JSON files and VCD waveforms under `workdir/`.
- Formal flow should emit both raw SBY outputs and a derived `fv_summary.yaml` artifact under `workdir/<tag>/<ip>/fv/`.
- Synthesis flow should emit both raw reports and a derived `synth_summary.yaml` artifact under `workdir/<tag>/<ip>/synth/`.
