# repo structure

The repository uses a predictable mirrored structure.

- `src/rtl/`, `src/dv/`, `src/fv/`, and `src/syn/` are distinct engineering disciplines
- the wiki mirrors that structure so the specification can be found near the implementation conceptually
- `wiki/flows-methods-phylosophy/` captures repository-wide rules and methods that are broader than one mirrored source directory
- `cfg/` owns configuration source of truth
- `tools/` owns implementation
- `bin/` and the repo-root `./build` expose user-facing commands
- `workdir/` owns generated run collateral
