# synthesis methodology

Synthesis is a separate engineering discipline.

- synthesis collateral lives under `src/syn/`
- shared synthesis libraries and scripts live under `src/syn/common/`
- the synthesis flow should stay explicit, generic, and config-driven
- synthesized outputs and reports should live under `workdir/<tag>/<ip>/synth/`
- synthesis should emit a machine-readable summary artifact in addition to raw reports
- the current flow is a foundation flow, not a signoff flow

## Review intent

The synthesis discipline should make it easy to answer:

- what script/profile was used
- what technology assumptions were used
- what outputs were produced
- what warnings or limitations are known

Foundation-level synthesis is still valuable, but it should be honest about what it is and is not.
