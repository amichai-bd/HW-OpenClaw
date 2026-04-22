# rtl coding style

RTL should follow a predictable SystemVerilog style that is easy to review, easy to lint, and easy for tooling to reason about.

## Naming

- module names and file names must match
- module and file names must be lowercase
- parameter names must be uppercase
- signal names should be lowercase with underscores

## Structural style

- use `always_comb` for combinational logic
- use `always_ff` for sequential logic
- do not use plain `always`
- do not combine `logic` declarations with inline initialization or assignment
- keep declarations separate from behavioral assignment

## Sequential style

- sequential updates should be structurally obvious
- repository macro style should wrap the intended non-blocking sequential pattern
- explicit handwritten non-blocking assignments should not appear in RTL or DV source code (nor in any legacy formal-support code under `src/fv/`)
- if a sequential pattern is needed and no suitable macro exists yet, add or extend the approved macro surface first instead of writing ad hoc `<=`

## Shared collateral

- shared macros, includes, and generic reusable collateral belong under `src/rtl/common/`
- IP-local RTL should not depend accidentally on another IP’s local RTL tree
- cross-IP composition is allowed only when architecturally intentional and declared explicitly

## Review intent

The style rules are not just cosmetic.
They exist so that:

- RTL intent is easy to parse
- lint and structural review work from consistent structure
- generated tooling and AI agents can infer the code shape without special-case heuristics
- code review focuses on behavior and architecture instead of format ambiguity
