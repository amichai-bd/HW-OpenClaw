# dv methodology rules

Dynamic verification in this repository should feel UVM-shaped without importing UVM.

## Architectural intent

- testbench tops stay thin
- interfaces own DUT-facing timing structure
- packages own reusable declarations and helpers
- env directories own generator, driver, monitor, model, scoreboard, coverage, agent, env, and tracker
- tests and regressions are explicit and YAML-driven

## Expected structure

- `tb/`: top-level hookup, plusargs, DUT instantiation, env construction
- `if/`: DUT-facing interface signals, clocking intent, modports if needed
- `pkg/`: reusable declarations, imports, utility helpers
- `env/`: predictable component split and shared tracker logic
- `tests/`: explicit named tests
- `regressions/`: explicit grouped suites

## Naming and file rules

- follow lowercase file naming across DV collateral
- keep file names aligned to their role, for example `<ip>_driver.sv`, `<ip>_monitor.sv`, `<ip>_env.sv`
- keep the TB top named `<ip>_tb.sv`
- keep interfaces in `if/`, not buried inside the TB
- keep reusable declarations in `pkg/` or `env/`, not scattered through tests

## Testbench rules

- keep the TB top thin
- do not let the TB become the place where all test behavior accumulates
- test selection should come from YAML and plusargs, not directory discovery or ad hoc branching
- top-level outputs should leave structured artifacts after simulation
- the TB should mainly own clock/reset, DUT hookup, interface hookup, plusargs, and env construction
- stimulus generation and checking belong in the environment split, not inlined into the TB

## Tracker rules

- top-level IO tracking is part of the default DV expectation
- each test run should produce stable review artifacts
- log paths, tracker JSON paths, and wave paths should come from config/build flow rather than being invented in code
- tracker output should be easy for automation to point at and easy for humans to review after failures

## Coding style

- use `always_comb` and `always_ff`
- do not use plain `always`
- do not initialize `logic` on declaration lines
- keep non-blocking assignments inside approved macros only
- if support logic needs a new sequential pattern, add or extend shared macros first

## Review checklist

- what stimulus exists
- what observation exists
- what checking exists
- what artifact remains after the run
- is the test selection explicit and YAML-driven
- is the environment structure still predictable
- are logs, tracker output, and wave output routed through the structured builder paths
- is the TB still thin enough that a reviewer can understand it quickly

## Avoid

- ad hoc TB-local behavior that bypasses the environment structure
- hidden test discovery logic
- DV code that writes outputs to invented or fallback paths
- raw one-off logging formats when a structured artifact already exists
