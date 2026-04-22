# builder methodology

The builder stays **declarative and YAML-driven**.

- target and step orchestration are described in `tools/build/build.yaml`
- dependency order and parallelism are encoded through `depends_on` and target-level ordering in `tools/build/build.py`
- the Python builder acts as a generic executor and action dispatcher
- IP-specific paths and selections come from `cfg/ip.yaml` and `cfg/env.yaml`, not ad hoc filesystem discovery
- successful output should be human-readable and machine-friendly
- build collateral is structured under `workdir/<tag>/<ip>/...`

## Entrypoints

- `./setup` — fresh-clone checks (PyYAML, optional strict tool verification)
- `./build` — lint, compile, test, regress, fpga, qa, debug

CI should call the same entrypoints where possible instead of re-encoding tool logic.

## UX intent

Builder output should help a human or an AI understand:

- what command was resolved
- which steps are queued and which actually started
- which steps passed or failed
- which files to review next

The builder prefers:

- explicit resolved commands
- structured status lines
- stable artifact paths
- **actionable failure output** (for example **`[quartus-triage]`** on Quartus failure: report paths, `rg` hint, first matching lines from `quartus.log`)

## Structural validation

- `./build -ip <ip> -qa` is the standard repository QA flow
- QA checks config references, filelists, mirrored wiki pages, discipline layout, and a deterministic subset of the RTL style contract

## Historical note

Older documentation referred to **ASIC-style** `-fv`, `-synth`, and `-pd` targets and OpenROAD integration. The **active** builder is **Questa + Quartus on Windows**; see [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack).
