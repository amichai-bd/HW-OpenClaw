# rtl fifo

This page specifies the FIFO RTL area under `src/rtl/fifo/`.

Current collateral:

- `code/fifo.sv`
- `filelist_rtl_fifo.f`
- `lint/verilator_waiver.vlt`

Intent:

- the FIFO RTL stays self-contained except for shared collateral imported from `src/rtl/common/`
- the RTL filelist is the declared source entry point for lint, simulation, formal, and synthesis flows
- lint waivers belong under the IP-local `lint/` area, not in the builder or in shared config
