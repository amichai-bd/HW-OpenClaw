# rtl

This section specifies the design implementation under `src/rtl/`.

Use this area for:

- IP-level RTL intent
- shared RTL collateral under `common/`
- lint expectations that are specific to RTL layout

Start here:

- [rtl common](/amichai-bd/HW-OpenClaw/wiki/rtl/common/rtl-common)
- [rtl fifo](/amichai-bd/HW-OpenClaw/wiki/rtl/fifo/rtl-fifo)
- [rtl counter](/amichai-bd/HW-OpenClaw/wiki/rtl/counter/rtl-counter)
- [rtl coding style](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/rtl-coding-style)

Repository rule:

- cross-IP composition is allowed when architecturally intentional
- shared macros and generic reusable collateral belong under `src/rtl/common/`
- ad hoc dependence on a neighbor IP's local collateral is not allowed
