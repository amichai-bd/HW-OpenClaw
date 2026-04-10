# fv fifo

This page specifies the FIFO formal verification collateral under `src/fv/fifo/`.

Current structure:

- `code/` for formal environment helpers and wrappers
- `properties/` for property modules
- `proofs/` for proof tops and proof composition
- `filelist_fv_fifo.f` as the declared formal entry point

Intent:

- keep assumptions, environment helpers, properties, and proofs separated
- make the filelist the single declared source entry for the builder
