# builder methodology

The builder should stay declarative and YAML-driven.

- target and step orchestration should be described in tool YAML
- dependency order and parallelism should be encoded through `depends_on`
- the Python builder should act as a generic executor and action dispatcher
- IP-specific paths and selections should come from config YAML, not filesystem discovery
- successful output should be human-readable and machine-friendly
- build collateral should be structured under `workdir/<tag>/<ip>/...`
- physical-design targets should use the same YAML graph instead of a separate
  script-only flow

The repository bootstrap path should also stay standard:

- `./setup` is the fresh-clone and CI provisioning entrypoint
- `./build` is the execution entrypoint
- CI should use those same entrypoints instead of re-encoding package and tool logic

The **scope** of `./setup` is **Tier 1** of the [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack) definition (RTL through synthesis). Physical-design backends are **Tier 2** and stay explicit in `cfg/pd.yaml` / `cfg/env.yaml` until the project wires them into bootstrap or CI.

## UX intent

Builder output should help a human or an AI understand:

- what command was resolved
- which steps are queued
- which steps actually started
- which steps passed or failed
- which files should be reviewed next

The builder should prefer:

- explicit resolved commands
- structured status lines
- stable artifact paths
- minimal ambiguity in failure output

## Structural validation

The repository should be able to validate its own structural contract.

- `./build -ip <ip> -qa` is the standard repository QA flow
- QA should check config references, filelists, mirrored wiki pages, discipline layout, and a deterministic subset of the repository style contract
- the enforced style subset should stay deterministic and low-ambiguity, for example plain `always`, inline `logic` initialization, and handwritten non-blocking assignments
- larger IPs should enter the repository only after passing the same structural contract

## Physical-design bootstrap

`./build -ip <ip> -pd` is the physical-design entry point.

At the foundation stage, PD depends on synthesis, writes a structured
`pd_summary.yaml`, and emits reviewable DEF, GDSII, SPEF, report, and image
artifacts from the internal scaffold. When `-pd-exec` is explicitly requested,
the builder also fails clearly if the declared OpenROAD binary is missing. This
keeps the flow honest: the repository has a PD contract and final-artifact shape,
but it does not pretend those artifacts are PDK-backed signoff before the backend
is installed and wired.
