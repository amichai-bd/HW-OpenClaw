# fv

> **Historical / legacy:** The default `./build` stack is **Windows + Git Bash**, **Questa** (`vlib`/`vlog`/`vsim`), and **Intel Quartus** (`-fpga`). Formal verification is **not** a supported builder target in this configuration. This wiki tree remains as **spec mirror / reference** for any future formal work. See [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack) and repo `AGENTS.md`.

This section specifies the formal verification discipline under `src/fv/`.

The repository treats formal as a first-class discipline, separate from RTL, DV, and synthesis.

Current areas:

- `common/` for shared assumptions and helpers
- `fifo/` for FIFO formal collateral
- `counter/` for counter formal collateral

Start here:

- [fv common](/amichai-bd/HW-OpenClaw/wiki/fv/common/fv-common)
- [fv fifo](/amichai-bd/HW-OpenClaw/wiki/fv/fifo/fv-fifo)
- [fv counter](/amichai-bd/HW-OpenClaw/wiki/fv/counter/fv-counter)
- [formal methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/formal-methodology)
