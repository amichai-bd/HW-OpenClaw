# HW-OpenClaw

HW-OpenClaw is a hardware-design repository driven through short task cycles, with SystemVerilog RTL, a pure-SystemVerilog DV environment, and a YAML-driven builder flow around Verilator.

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
│   └── flows-methods-phylosophy/
├── cfg/
│   ├── env.sh
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
│   └── build/
│       ├── build.py
│       └── build.yaml
└── workdir/
```

## Design rules

- The repository follows spec-driven development. The repo-root `wiki/` is the version-controlled specification surface.
- `wiki/` mirrors the `src/` structure at the top level, and `wiki/flows-methods-phylosophy/` captures repository-wide flow, methods, and philosophy.
- Every issue must reference the relevant wiki path and begin from the specification with wording such as `according to wiki wiki/...`.
- `src/` changes must be reviewed against the referenced wiki and should update the wiki when the intended structure, behavior, or method changes.
- wiki changes must also be reviewed against the affected `src/` paths so spec and implementation do not drift.
- YAML files are the source of truth for tool flow, IP metadata, output layout, and environment data.
- `cfg/env.yaml` owns environment and tool data, while `cfg/env.sh` is the shell entry point that exports that data.
- `cfg/ip.yaml` owns IP-specific metadata and the structured output layout under `workdir/`.
- `cfg/fv.yaml` owns shared formal profiles, solver selection, and reusable formal script selection.
- `cfg/synth.yaml` owns shared synthesis profiles, reusable script selection, and synthesis-technology metadata.
- `tools/` contains implementations. `bin/` contains thin user-facing launchers that are added to `PATH`.
- Formal-verification collateral should live under `src/fv/`, separate from both `rtl/`, `dv/`, and `syn/`.
- Shared formal collateral such as reusable SBY scripts and common assumptions should live under `src/fv/common/`.
- Formal collateral should follow a predictable split: common assumptions/scripts, IP-local environment code, IP-local properties, and IP-local proof wrappers.
- Shared RTL collateral should live under `src/rtl/common/`, not inside a specific IP tree.
- Synthesis-specific collateral should live under `src/syn/`, separate from both `rtl/` and `dv/`.
- Shared synthesis collateral such as generic liberty files and reusable synthesis scripts should live under `src/syn/common/`.
- IPs select synthesis behavior in `cfg/ip.yaml` via a synth profile, while the shared profile definitions live in `cfg/synth.yaml`.
- Source filelists are authored relative to `$MODEL_ROOT`, and the builder generates explicit filelists under `workdir/` for tools like Verilator.
- DV environments follow a predictable UVM-shaped split: interface, package, generator, driver, monitor, model, scoreboard, coverage, agent, env, tracker, and thin top-level testbench.

## Quick start

For normal repository usage, bootstrap first:

```sh
./setup
```

Then invoke the builder through the standard repo launcher:

```sh
./build -ip fifo -compile
./build -ip fifo -lint
./build -ip counter -fv
./build -ip fifo -synth
./build -ip fifo -test sanity
./build -ip fifo -regress level_0
./build -ip fifo -lint -fv -synth -regress level_2
./build -ip counter -compile -test sanity
```

To browse saved waveform runs:

```sh
./build -debug
```

That mode lists saved VCD-backed runs under `workdir/`, sorted by time, and lets you pick one to open in GTKWave.

The repo-root `./build` launcher sources `cfg/env.sh` automatically, then delegates to `bin/build`. Source `. cfg/env.sh` directly only when you want the shell environment for manual tool use outside the standard repo entrypoints. The builder accepts multiple discipline flags in one command and resolves step dependencies automatically. Shared prerequisites such as generated filelists and compile run once per invocation when needed. `-debug` must be used by itself, and `-test` and `-regress` remain mutually exclusive.

For a fresh clone or a clean CI runner, use the repository bootstrap entrypoint first:

```sh
./setup
./setup --check
```

`./setup` installs the required open-source toolchain from the YAML-defined bootstrap contract in `cfg/env.yaml`, including Verilator, Yosys, SBY, GTKWave, and the formal solver dependencies. `./setup --check` verifies the installed toolchain without reinstalling it.

Repository structure can be validated explicitly per IP:

```sh
./build -ip fifo -qa
./build -ip counter -qa -lint -fv -synth -regress level_2
```

The QA flow checks that the IP structure, config references, source filelists, mirrored wiki pages, and a deterministic subset of the repository style rules match the repository contract before deeper discipline flows run. Each QA run emits a `workdir/<tag>/<ip>/qa/qa_report.txt` artifact listing the checked handwritten sources and any violations.

## CI

- GitHub Actions uses the same `build` entrypoint as local development. CI does not invent a separate flow outside the repository builder.
- The main CI gate lives in [.github/workflows/ci.yml](.github/workflows/ci.yml).
- Spec-reference enforcement runs as separate [issue-reference](.github/workflows/issue-reference.yml) and [pr-reference](.github/workflows/pr-reference.yml) workflows so issue checks and PR checks stay visible without skipped jobs.
- PR review enforcement also runs through [pr-agent](.github/workflows/pr-agent.yml), configured by the repo-root [.pr_agent.toml](.pr_agent.toml).
- CodeRabbit is configured from the repo-root [.coderabbit.yaml](.coderabbit.yaml) and runs alongside PR-Agent on this public repository through the CodeRabbit GitHub App.
- The current CI uses one `gate` job on `ubuntu-latest`.
- That job uses the same repo bootstrap entrypoint as local development, then runs two explicit builder invocations: one for `fifo` and one for `counter`.
- The workflow sources `. cfg/env.sh` and uploads the structured `workdir/` outputs for both IPs as artifacts.
- PR-Agent is part of the normal PR gate. It runs as a repository-managed GitHub Actions check and is configured by `.pr_agent.toml`.
- CodeRabbit is also part of the normal PR gate. It runs as the CodeRabbit GitHub App, is configured by `.coderabbit.yaml`, and can block merge both through its required `CodeRabbit` check and through unresolved review conversations.
- PR-Agent review comments are expected to use a structured `Summary` / `Findings` / `Final status` format so blocking findings are easy to distinguish from informational notes.
- CodeRabbit is configured with `request_changes_workflow: true` so its review comments can participate directly in the merge-blocking conversation-resolution flow.
- The repository secret used by PR-Agent is `OPENAI_KEY`, and the action should stay pinned to an explicit upstream release instead of floating on `@main`.
- The repository also pins PR-Agent model selection in `.pr_agent.toml`: `gpt-5.4-2026-03-05` with fallback `o4-mini` and `reasoning_effort = "high"`.
- GitHub-hosted runners work with no repo-side manual setup beyond enabling Actions. Self-hosted runner registration, labels, and machine provisioning are manual GitHub/repo administration tasks outside the repository tree.
- CodeRabbit itself is installed as a GitHub App rather than a repo-authored Actions workflow, while PR-Agent is a repo-authored GitHub Actions workflow. That difference is intentional and is part of the normal gate design.

## Current flow

- Compile uses Verilator through the YAML-defined build flow in `tools/build/build.yaml`.
- `tools/build/build.yaml` is organized as declarative `targets` and `steps`.
- Targets declare root steps, tool requirements, optional selectors, and target-local context overlays.
- Steps declare `depends_on`, commands or actions, display names, and review artifacts.
- The Python builder resolves the selected targets, computes the dependency graph from `depends_on`, and runs independent disciplines in parallel when they do not depend on one another.
- The builder also provides a QA target so repository contracts can be checked explicitly before larger flows run.
- RTL lint uses Verilator `--lint-only` through the YAML-defined build flow in `tools/build/build.yaml`.
- Formal verification uses SBY through the YAML-defined build flow in `tools/build/build.yaml`.
- The current formal flow is selected through `cfg/fv.yaml`.
- Formal profiles are allowed to differ per IP. Simple control IPs can use full `prove`, while stateful data-path IPs can use bounded safety profiles until stronger proofs are practical.
- Synthesis uses Yosys through the YAML-defined build flow in `tools/build/build.yaml`.
- The current synthesis flow is selected through `cfg/synth.yaml`.
- The active shared synth profile uses a vendored generic liberty for FF legalization and a generic CMOS gate mapping path with a delay target.
- The current synthesis `check` report is informational. It is captured as a run artifact, but it is not yet a hard signoff gate because the generic mapped flow still emits Yosys-level structural warnings that need a richer technology model to resolve cleanly.
- Tests and regressions are selected from YAML definitions under `src/dv/<ip>/code/tests/` and `src/dv/<ip>/regressions/`.
- Each simulation run writes structured collateral under `workdir/<tag>/<ip>/...`.
- Test outputs include at least a simulation log, a tracker JSON file, and a VCD waveform when waveform dumping is enabled in the environment config.
- Lint-specific collateral and waiver files live under `src/rtl/<ip>/lint/`, while lint run outputs go under `workdir/<tag>/<ip>/lint/`.
- Shared formal source collateral lives under `src/fv/common/`, while formal run outputs go under `workdir/<tag>/<ip>/fv/`.
- Formal outputs include the generated `.sby` file, the SBY run directory, the formal log, and a derived `fv_summary.yaml` artifact for automation.
- The current formal collateral split is `src/fv/common/assumptions/`, `src/fv/common/scripts/`, `src/fv/<ip>/code/`, `src/fv/<ip>/properties/`, and `src/fv/<ip>/proofs/`.
- The current `<IP>` formal flow intentionally proves a reduced parameter point for control behavior, which is a standard way to keep bounded proofs tractable on parameterized stateful designs.
- Shared synthesis source collateral lives under `src/syn/common/`, while synth run outputs go under `workdir/<tag>/<ip>/synth/`.
- Synth outputs include a generated Yosys script, a synthesized netlist, JSON netlist, machine-readable `stat` report, area report, a synthesis `check` report, and a derived `synth_summary.yaml` artifact for automation.

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
