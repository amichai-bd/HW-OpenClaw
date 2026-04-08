# dv methodology

Dynamic verification should use a structured UVM-like environment without importing UVM.

The goal is methodology, not framework dependency.

## Architectural intent

The repository favors predictable DV architecture over ad hoc per-testbench style.

That means:

- testbench tops stay thin
- interfaces own DUT-facing timing structure
- package directories own reusable declarations
- env directories own generator, driver, monitor, model, scoreboard, coverage, agent, env, and tracker
- test and regression selection are YAML-driven
- top-level IO tracking produces structured tracker artifacts

## Why UVM-like without UVM

The repository wants the benefits of UVM-style thinking:

- separation of concerns
- reusable components
- predictable environment structure
- transaction-level reasoning

without taking on a heavyweight framework dependency that fights the current tool stack.

## Component expectations

### tb

- owns top-level hookup
- owns plusargs
- instantiates DUT and env
- should not become a dumping ground for test behavior

### if

- owns DUT-facing interface structure
- owns clocking and modport intent when needed

### pkg

- owns reusable declarations and imports

### env

- owns the predictable component split:
  generator, driver, monitor, model, scoreboard, coverage, agent, env, tracker

### tests and regressions

- tests define selected behaviors
- regressions define grouped execution sets
- both should be explicit and YAML-driven

## Tracker expectation

Top-level IO tracking is part of the default DV expectation.

The tracker exists so:

- runs leave structured artifacts
- debug is not only waveform-driven
- builders and automation can point to a stable review file

## Review intent

A DV change should be reviewable in terms of:

- what stimulus exists
- what observation exists
- what checking exists
- what artifact remains after the run

If that is hard to answer, the DV structure is probably drifting.

Sequential helper logic in DV and FV support code should follow the same repository style as RTL:

- use `always_ff` and `always_comb`
- keep non-blocking assignments inside approved macros only
- add or extend shared macros before introducing a new sequential pattern
