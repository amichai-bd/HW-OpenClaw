# formal verification methodology rules

Formal verification is a first-class discipline in this repository.

## Structural rules

- formal collateral lives under `src/fv/`
- shared assumptions and reusable scripts live under `src/fv/common/`
- each IP uses the split:
  - `code/`
  - `properties/`
  - `proofs/`
- formal filelists follow the same repository pattern as RTL and DV

## Naming and file rules

- keep formal file names aligned to their role
- environment/wrapper logic belongs in `code/`
- property modules belong in `properties/`
- top-level proof entry modules belong in `proofs/`
- shared assumptions should stay reusable and generic when possible

## Configuration rules

- IP-level formal selection belongs in `cfg/ip.yaml`
- shared formal profile data belongs in `cfg/fv.yaml`
- solver choice and proof profile should be explicit
- do not inline source lists into config YAML when a formal filelist should exist

## Proof style

- assumptions should be explicit and reviewable
- property intent should be easy to read from the proof structure
- choose full proofs when tractable
- choose bounded safety honestly when state-space or memory complexity requires it
- small parameter points are acceptable when they are clearly intentional and documented
- do not hide architectural shortcuts inside the proof wrapper without making them obvious to the reviewer

## Coding style

- use `always_comb` and `always_ff`
- do not use plain `always`
- do not initialize `logic` on declaration lines
- keep non-blocking assignments inside approved macros only
- compute next-state in combinational logic where practical and register through approved macros

## Artifact rules

- formal runs should emit raw tool outputs plus a machine-readable summary
- automation should consume the summary rather than scraping raw tool text when possible
- run outputs belong under `workdir/<tag>/<ip>/fv/`
- proof configuration should be reconstructable from the emitted artifacts and selected config

## Review checklist

- what property is being checked
- what assumptions constrain the proof
- which profile and solver are selected
- what summary artifact reports the result
- is the proof structure located in the expected `code/`, `properties/`, `proofs/` split
- is the proof honest about what is full proof versus bounded proof

## Avoid

- hidden assumptions
- solver or profile choice that is implied rather than declared
- direct source enumeration in config YAML when a formal filelist should exist
- treating bounded proofs as if they were stronger than they are
