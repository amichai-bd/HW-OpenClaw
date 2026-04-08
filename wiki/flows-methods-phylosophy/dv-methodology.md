# dv methodology

Dynamic verification should use a structured UVM-like environment without importing UVM.

- testbench tops stay thin
- interfaces own DUT-facing timing structure
- package directories own reusable declarations
- env directories own generator, driver, monitor, model, scoreboard, coverage, agent, env, and tracker
- test and regression selection should be YAML-driven
- top-level IO tracking should produce structured tracker artifacts
- the repository favors predictable DV architecture over ad hoc per-testbench style
