# builder methodology

The builder should stay declarative and YAML-driven.

- target and step orchestration should be described in tool YAML
- dependency order and parallelism should be encoded through `depends_on`
- the Python builder should act as a generic executor and action dispatcher
- IP-specific paths and selections should come from config YAML, not filesystem discovery
- successful output should be human-readable and machine-friendly
- build collateral should be structured under `workdir/<tag>/<ip>/...`

The repository bootstrap path should also stay standard:

- `./setup` is the fresh-clone and CI provisioning entrypoint
- `./build` is the execution entrypoint
- CI should use those same entrypoints instead of re-encoding package and tool logic

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
