# builder methodology

The builder should stay declarative and YAML-driven.

- target and step orchestration should be described in tool YAML
- dependency order and parallelism should be encoded through `depends_on`
- the Python builder should act as a generic executor and action dispatcher
- IP-specific paths and selections should come from config YAML, not filesystem discovery
- successful output should be human-readable and machine-friendly
- build collateral should be structured under `workdir/<tag>/<ip>/...`

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
