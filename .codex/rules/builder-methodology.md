# builder methodology rules

The builder should act as a generic executor of YAML-defined flow, not as a second source of project truth.

## Source of truth

- build target and step orchestration comes from `tools/build/build.yaml`
- IP-specific paths, tops, tests, regressions, and output layout come from config YAML
- environment data comes from `cfg/env.yaml`
- do not re-encode repository structure in Python when YAML already owns it

## Config split

- `cfg/ip.yaml` owns IP-specific metadata and output layout
- `cfg/fv.yaml` owns shared formal profiles
- `cfg/synth.yaml` owns shared synthesis profiles
- `cfg/pd.yaml` owns shared physical-design profiles and backend expectations
- `cfg/env.yaml` owns environment data and exported shell contract

## Graph and execution rules

- targets select root steps
- steps declare `depends_on`
- dependency order and parallelism should come from YAML, not hardcoded sequencing
- the builder may implement reusable primitive actions, but should not accumulate ad hoc discipline-specific policy where YAML can express it

## UX rules

- resolved command should be explicit
- status output should show wait, start, and done clearly
- completed steps should point to review artifacts
- errors should fail clearly and avoid guesswork
- interactive selection is acceptable when the user leaves required selectors unspecified
- when interactive selection is used, the builder should still print the final resolved command before execution

## Artifact rules

- generated filelists belong under `workdir/<tag>/<ip>/filelist/`
- compile, test, regress, lint, FV, synth, PD, and debug outputs should use stable structured paths
- logs and summary artifacts should be machine-friendly and human-readable

## Entrypoint rules

- `. cfg/env.sh` is the shell entrypoint
- `./setup` is the required repository bootstrap entrypoint for fresh clones and CI provisioning
- `./build` is the required user-facing repository entrypoint
- `./build -qa` is the standard repository QA flow for one IP
- `./build -ip <ip> -pd` is the standard physical-design entry point for one IP
- `./build -ip <ip> -pd -pd-exec` is optional local-only: requires a resolvable `openroad` after the scaffold; do not add to default CI
- do not treat raw simulator, formal, or synthesis tool commands as the normal repo interface
- CI should invoke the same setup and builder entrypoints used locally
- default CI is expected to exercise **Tier 1** of the software stack only until PD is deliberately added; see `wiki/flows-methods-phylosophy/software-stack.md`

## Avoid

- path discovery by searching the repo tree
- hardcoded fallback locations
- workflow meaning hidden only in Python
- output layouts invented inside scripts instead of derived from config
- hidden defaults that are not visible in the YAML source of truth
- repo structure drift that could have been caught by a validator but was left implicit
- handwritten style drift that could have been caught deterministically before review
