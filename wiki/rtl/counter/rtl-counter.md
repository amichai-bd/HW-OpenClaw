# rtl counter

This page specifies the counter RTL area under `src/rtl/counter/`.

Current collateral:

- `code/counter.sv`
- `filelist_rtl_counter.f`
- `lint/verilator_waiver.vlt`

Intent:

- the counter RTL stays self-contained except for shared collateral imported from `src/rtl/common/`
- the RTL filelist is the declared source entry point for lint, simulation, formal, and synthesis flows
- lint waivers belong under the IP-local `lint/` area, not in the builder or in shared config
