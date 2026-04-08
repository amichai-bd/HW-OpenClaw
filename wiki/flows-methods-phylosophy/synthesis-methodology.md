# synthesis methodology

Synthesis is a separate engineering discipline.

- synthesis collateral lives under `src/syn/`
- shared synthesis libraries and scripts live under `src/syn/common/`
- the synthesis flow should stay explicit, generic, and config-driven
- synthesized outputs and reports should live under `workdir/<tag>/<ip>/synth/`
- synthesis should emit a machine-readable summary artifact in addition to raw reports
- the current flow is a foundation flow, not a signoff flow
