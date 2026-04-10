# dv fifo

This page specifies the FIFO dynamic verification environment under `src/dv/fifo/`.

Current structure:

- `code/if/`
- `code/pkg/`
- `code/env/`
- `code/tb/`
- `code/tests/`
- `filelist/`
- `regressions/`

Important intent:

- the testbench remains thin
- environment behavior lives in `env/`
- tracker logic is part of the DV environment and may be included into the TB through declared include paths
- tests and regressions are YAML-defined and consumed by the repository builder

The filelist under `filelist/` is the declared DV entry point.
