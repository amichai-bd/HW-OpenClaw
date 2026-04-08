# rtl

This section specifies the design implementation under `src/rtl/`.

Use this area for:

- IP-level RTL intent
- shared RTL collateral under `common/`
- lint expectations that are specific to RTL layout

Start here:

- [rtl common](common/index.md)
- [rtl fifo](fifo/index.md)
- [rtl counter](counter/index.md)
- [rtl coding style](../flows-methods-phylosophy/rtl-coding-style.md)

Repository rule:

- cross-IP composition is allowed when architecturally intentional
- shared macros and generic reusable collateral belong under `src/rtl/common/`
- ad hoc dependence on a neighbor IP's local collateral is not allowed
