# rtl coding style rules

This file is the execution-facing RTL rule set for agents.

## Naming

- module names are lowercase
- file names are lowercase
- module name and file name must match
- parameter names are uppercase
- signal names are lowercase with underscores
- localparams should be uppercase when they behave like constants

## Structural style

- use `always_comb` for combinational logic
- use `always_ff` for sequential logic
- never use plain `always`
- separate declarations from behavior
- do not initialize `logic` on the declaration line
- prefer small, obvious blocks over large mixed-intent blocks

## Sequential style

- handwritten code should not contain explicit non-blocking assignments
- keep non-blocking assignments inside approved macros only
- if a sequential pattern is needed, first look for an existing macro
- if no suitable macro exists, add or extend the macro surface instead of writing ad hoc `<=`
- when possible, compute next-state in `always_comb` and register it through macros

## Shared collateral

- shared RTL includes and macros belong under `src/rtl/common/`
- do not bury generally reusable collateral under a single IP
- cross-IP composition is allowed only when it is deliberate architecture, not an accidental path dependency

## Filelists

- source filelists are authored relative to `$MODEL_ROOT`
- do not hardcode absolute source paths
- do not let scripts guess missing filelist content

## Review checklist

- does the file follow lowercase naming and matching module/file names
- is combinational logic clearly separate from sequential logic
- are sequential updates macro-wrapped
- are declarations cleanly separated from behavior
- is shared collateral placed in the right common directory

## Avoid

- plain `always`
- inline-initialized `logic`
- mixed combinational and sequential intent in one block
- accidental dependency on a neighbor IP’s local RTL tree
- silent fallback behavior in RTL support scripts
