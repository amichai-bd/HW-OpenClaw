# rtl counter

This page specifies the counter RTL area under `src/rtl/counter/`.

Current collateral:

- `code/counter.sv`
- `filelist_rtl_counter.f`
- `lint/verilator_waiver.vlt` (legacy filename; **Questa** `-lint` uses `vlog -lint` on this filelist, not Verilator)

Intent:

- the counter RTL stays self-contained except for shared collateral imported from `src/rtl/common/`
- the RTL filelist is the declared source entry point for **Questa** `vlog -lint`, **Quartus** `-fpga` (RTL-only filelist), and DV flows that consume RTL through filelists
- lint waivers belong under the IP-local `lint/` area, not in the builder or in shared config
