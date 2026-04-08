# synthesis methodology rules

Synthesis is a separate engineering discipline, not an RTL appendix.

## Structural rules

- synthesis collateral lives under `src/syn/`
- shared libraries and scripts live under `src/syn/common/`
- per-IP synthesis collateral should be explicit and config-driven
- synthesis outputs belong under `workdir/<tag>/<ip>/synth/`

## Naming and file rules

- keep shared scripts and libraries under `src/syn/common/`
- keep per-IP synthesis collateral clearly separated from RTL and DV
- keep report names and output paths stable so automation can consume them reliably

## Configuration rules

- IP-level synthesis selection belongs in `cfg/ip.yaml`
- shared synthesis profiles and technology metadata belong in `cfg/synth.yaml`
- do not hardcode technology or profile assumptions in scripts when they belong in config

## Flow expectations

- the current flow is a foundation flow, not a signoff flow
- be honest about generic mapping limitations
- capture warnings in structured reports instead of hiding them
- emit both raw synthesis outputs and a machine-readable summary artifact
- prefer explicit profile-driven flow over hidden tool defaults

## Review checklist

- what synth profile was selected
- what library or technology assumptions were used
- what outputs were produced
- what warnings or limitations remain
- whether the result is foundation-grade or closer to signoff intent
- whether the summary artifact tells automation what it needs without scraping raw text

## Avoid

- pretending the generic flow is signoff quality
- hiding mapping or check warnings
- scattering synthesis collateral under RTL or DV trees
- duplicating source-of-truth path knowledge inside scripts
