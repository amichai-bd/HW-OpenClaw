# syn common

This area specifies shared synthesis collateral under `src/syn/common/`.

Current contents:

- `lib/` for shared synthesis library collateral
- `scripts/` for shared synthesis scripts

Intent:

- keep common synthesis flow logic here
- keep per-run generated synthesis scripts under `workdir/`, not under `src/`
- keep synthesis profile selection in config YAML rather than hardcoded in scripts
- keep generated schematic DOT/SVG/PNG artifacts under `workdir/<tag>/<ip>/synth/`
- treat schematic visuals as structural synth review artifacts, not physical-design artifacts
