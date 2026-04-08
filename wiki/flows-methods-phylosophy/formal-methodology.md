# formal methodology

Formal verification is a first-class discipline.

- formal collateral lives under `src/fv/`
- shared assumptions and scripts live under `src/fv/common/`
- each IP should use the `code/`, `properties/`, and `proofs/` split
- formal filelists should follow the same repository pattern as RTL and DV
- formal should emit both raw tool outputs and a machine-readable summary artifact
- profiles may differ by IP based on tractability, but the choice should be explicit in config

## Review intent

Formal should be reviewable as specification-backed proof intent.

That means reviewers should be able to answer:

- what property is intended
- what assumptions exist
- what proof profile and solver are selected
- what artifact summarizes the result
