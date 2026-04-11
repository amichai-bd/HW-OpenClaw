# physical-design common

`src/pd/common/` is the shared physical-design collateral area.

Common collateral belongs here when it can be reused across IPs, for example:

- generic OpenROAD TCL fragments
- common floorplan generation helpers
- common IO placement conventions
- timing/SDC generation helpers
- report parsers and summary generation helpers
- layout image generation helpers

IP-specific floorplan decisions should not be hardcoded here. They should be
declared through `cfg/ip.yaml` and materialized into `workdir/<tag>/<ip>/pd/`.
