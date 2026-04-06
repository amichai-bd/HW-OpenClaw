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
│       └── <ip>/
│           ├── code/
│           └── filelist_rtl_<ip>.f
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
- Tests and regressions are selected from YAML definitions under `src/dv/<ip>/code/tests/` and `src/dv/<ip>/regressions/`.
- Each simulation run writes structured collateral under `workdir/<tag>/<ip>/...`.
- Test outputs include at least a simulation log, a tracker JSON file, and a VCD waveform when waveform dumping is enabled in the environment config.

## Development workflow

- Start meaningful changes from an issue.
- Implement each issue on a short-lived branch named with the issue number prefix.
- Open a pull request before merging to `main`.
- Merge, delete the branch, and sync local workspaces back to `main`.
