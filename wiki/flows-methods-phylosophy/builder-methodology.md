# builder methodology

The builder should stay declarative and YAML-driven.

- target and step orchestration should be described in tool YAML
- dependency order and parallelism should be encoded through `depends_on`
- the Python builder should act as a generic executor and action dispatcher
- IP-specific paths and selections should come from config YAML, not filesystem discovery
- successful output should be human-readable and machine-friendly
- build collateral should be structured under `workdir/<tag>/<ip>/...`
