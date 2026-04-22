# repo structure

The repository uses a predictable mirrored structure so humans and AI agents can understand intent from paths with minimal guesswork.

## Top-level intent

- `src/` owns engineering source collateral
- `wiki/` owns the written specification
- `.codex/rules/` owns condensed execution-facing agent rules derived from the wiki
- `cfg/` owns configuration source of truth
- `tools/` owns implementation of tooling
- `bin/` and repo-root entrypoints expose user-facing commands
- `workdir/` owns generated run collateral

Standard repository entrypoints:

- `./setup` for fresh-clone bootstrap and CI provisioning
- `./build` for validation and discipline execution

## Source disciplines

The major source disciplines are intentionally separated:

- `src/rtl/`
  design implementation
- `src/dv/`
  dynamic verification
- `src/fv/`
  formal verification (**historical**; not wired into the default `./build` stack)
- `src/syn/`
  synthesis collateral (**historical**; active FPGA flow is Quartus under `./build -fpga`)
- `src/pd/`
  physical design (**historical**; no OpenROAD gate in the default builder)

This separation matters because each discipline has:

- different collateral
- different tool flows
- different output artifacts
- different review concerns

## Mirrored wiki model

The wiki mirrors the `src/` structure at the top level:

- `wiki/rtl/` mirrors `src/rtl/`
- `wiki/dv/` mirrors `src/dv/`
- `wiki/fv/` mirrors `src/fv/` (historical spec mirror)
- `wiki/syn/` mirrors `src/syn/` (historical)
- `wiki/pd/` mirrors `src/pd/` (historical)

This does not mean every wiki page must be equally detailed.
It means every source area has an obvious specification home.

For GitHub Wiki browsing, the mirror should stay readable:

- keep strong overview pages at the top level and at the IP level
- do not create placeholder landing pages for every deep directory unless they carry real specification content
- prefer fewer content-bearing pages over many thin generic landing pages that only restate the tree
- rely on GitHub Wiki's default page navigation and the main overview pages
- use extensionless wiki-internal links so pages feel like wiki pages rather than markdown files
- publish the generated GitHub Wiki mirror on demand through `.codex/skills/update-wiki/` (see [codex-agent-skills](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/codex-agent-skills))

## Repository-wide method pages

`wiki/flows-methods-phylosophy/` exists because some rules are broader than one mirrored `src/` directory:

- spec-driven development
- GitHub flow
- AI-native CLI-first work style
- builder methodology
- coding style
- methodology per discipline

## Predictability rules

The structure should help answer these questions quickly:

- where does implementation for this discipline live?
- where is the spec for that area?
- where is the config?
- where is the tool implementation?
- where do generated artifacts go?

If a new directory or tool makes those answers less obvious, the structure should be reconsidered.

The repository should also validate these answers automatically through the standard QA flow rather than depending only on review memory.
