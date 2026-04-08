# dv

This section specifies the dynamic verification environment under `src/dv/`.

The DV environments in this repository follow a structured, UVM-like layout without importing UVM:

- `code/if/` for interfaces
- `code/pkg/` for the thin DV package
- `code/env/` for generator, driver, monitor, model, scoreboard, coverage, config, tracker, and related support code
- `code/tb/` for the thin top-level testbench
- `code/tests/` for test YAML
- `filelist/` for declared DV source entry points
- `regressions/` for regression YAML

Start here:

- [dv fifo](fifo/index.md)
- [dv counter](counter/index.md)
- [dv methodology](../flows-methods-phylosophy/dv-methodology.md)
