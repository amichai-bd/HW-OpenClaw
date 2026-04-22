# rtl fifo

This page specifies the FIFO RTL area under `src/rtl/fifo/`.

Current collateral:

- `code/fifo.sv`
- `filelist_rtl_fifo.f`
- `lint/verilator_waiver.vlt` (legacy filename; **Questa** `-lint` uses `vlog -lint` on this filelist, not Verilator)

Intent:

- the FIFO RTL stays self-contained except for shared collateral imported from `src/rtl/common/`
- the RTL filelist is the declared source entry point for **Questa** `vlog -lint`, **Quartus** `-fpga` (RTL-only filelist), and DV flows that consume RTL through filelists
- lint waivers belong under the IP-local `lint/` area, not in the builder or in shared config
