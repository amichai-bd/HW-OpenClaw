# rtl coding style

RTL should follow a predictable SystemVerilog style.

- module names and file names must match and remain lowercase
- parameter names must be uppercase
- signal names should be lowercase with underscores
- use `always_comb` for combinational logic
- use `always_ff` for sequential logic
- do not use plain `always`
- do not combine `logic` declarations with inline initialization or assignment
- non-blocking sequential updates should follow the repository macro style instead of ad hoc explicit `<=` coding when that rule applies
- shared macros and generic reusable collateral belong under `src/rtl/common/`
