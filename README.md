# HW-OpenClaw

HW-OpenClaw is a hardware-design repository driven through short task cycles, with SystemVerilog RTL, a pure-SystemVerilog DV environment, and a YAML-driven builder flow around Verilator.

## Repository structure

```text
.
├── bin/
│   └── build
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
│   └── rtl/
│       ├── common/
│       │   └── include/
│       └── <ip>/
│           ├── code/
│           ├── lint/
│           └── filelist_rtl_<ip>.f
│   └── syn/
│       ├── common/
│       │   ├── constraints/
│       │   └── lib/
│       └── <ip>/
│           └── scripts/
├── tools/
│   └── build/
│       ├── build.py
│       └── build.yaml
└── workdir/
```

## Design rules

- YAML files are the source of truth for tool flow, IP metadata, output layout, and environment data.
- `cfg/env.yaml` owns environment and tool data, while `cfg/env.sh` is the shell entry point that exports that data.
- `cfg/ip.yaml` owns IP-specific metadata and the structured output layout under `workdir/`.
- `tools/` contains implementations. `bin/` contains thin user-facing launchers that are added to `PATH`.
- Shared RTL collateral should live under `src/rtl/common/`, not inside a specific IP tree.
- Synthesis-specific collateral should live under `src/syn/`, separate from both `rtl/` and `dv/`.
- Shared synthesis collateral such as generic liberty files, default constraints, and reusable synthesis scripts should live under `src/syn/common/`.
- Source filelists are authored relative to `$MODEL_ROOT`, and the builder generates explicit filelists under `workdir/` for tools like Verilator.
- DV environments follow a predictable UVM-shaped split: interface, package, generator, driver, monitor, model, scoreboard, coverage, agent, env, tracker, and thin top-level testbench.

## Quick start

Source the repository environment first:

```sh
. cfg/env.sh
```

Then invoke the builder through the standard repo launcher:

```sh
build -ip fifo -compile
build -ip fifo -lint
build -ip fifo -synth
build -ip fifo -test sanity
build -ip fifo -regress level_0
```

To browse saved waveform runs:

```sh
build -debug
```

That mode lists saved VCD-backed runs under `workdir/`, sorted by time, and lets you pick one to open in GTKWave.

## Current flow

- Compile uses Verilator through the YAML-defined build flow in `tools/build/build.yaml`.
- RTL lint uses Verilator `--lint-only` through the YAML-defined build flow in `tools/build/build.yaml`.
- Synthesis uses Yosys through the YAML-defined build flow in `tools/build/build.yaml`.
- The current synthesis flow uses a vendored generic liberty for FF legalization and a generic CMOS gate mapping path with a delay target.
- The current synthesis `check` report is informational. It is captured as a run artifact, but it is not yet a hard signoff gate because the generic mapped flow still emits Yosys-level structural warnings that need a richer technology model to resolve cleanly.
- Tests and regressions are selected from YAML definitions under `src/dv/<ip>/code/tests/` and `src/dv/<ip>/regressions/`.
- Each simulation run writes structured collateral under `workdir/<tag>/<ip>/...`.
- Test outputs include at least a simulation log, a tracker JSON file, and a VCD waveform when waveform dumping is enabled in the environment config.
- Lint-specific collateral and waiver files live under `src/rtl/<ip>/lint/`, while lint run outputs go under `workdir/<tag>/<ip>/lint/`.
- Synthesis-specific source collateral lives under `src/syn/<ip>/`, while synth run outputs go under `workdir/<tag>/<ip>/synth/`.
- Synth outputs include a generated Yosys script, a synthesized netlist, JSON netlist, machine-readable `stat` report, area report, and a synthesis `check` report.

## Development workflow

- Start meaningful changes from an issue.
- Implement each issue on a short-lived branch named with the issue number prefix.
- Open a pull request before merging to `main`.
- Merge, delete the branch, and sync local workspaces back to `main`.
