# fv counter

This page specifies the counter formal verification collateral under `src/fv/counter/`.

Current structure:

- `code/` for formal environment helpers and wrappers
- `properties/` for property modules
- `proofs/` for proof tops and proof composition
- `filelist_fv_counter.f` as the declared formal entry point

Intent:

- keep assumptions, environment helpers, properties, and proofs separated
- make the filelist the single declared source entry for the builder
