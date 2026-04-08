# hw-openclaw wiki

This wiki is the version-controlled specification surface of the repository.

The repository is intended to be:

- spec-driven
- GitHub-flow-driven
- AI-native and CLI-first
- structurally predictable across disciplines

The wiki exists so that repository changes start from a written specification instead of from ad hoc code edits.

## How to use this wiki

Before implementation work starts:

1. find the relevant wiki path
2. open or update an issue that begins `according to wiki wiki/...`
3. decide whether the issue is:
   - an implementation bug under an already-correct spec
   - or a spec clarification / spec change that should update the wiki
4. make the change in `src/`, `cfg/`, `tools/`, or elsewhere according to the wiki
5. review the final implementation against the wiki before merge

The important rule is not that every issue must change the wiki.
The important rule is that every issue must begin from the wiki.

## Structure

- `rtl/` mirrors `src/rtl/`
- `dv/` mirrors `src/dv/`
- `fv/` mirrors `src/fv/`
- `syn/` mirrors `src/syn/`
- `flows-methods-phylosophy/` captures repository-wide methods, structure, coding rules, and development philosophy beyond the direct `src/` mirror

## Recommended starting pages

- [spec-driven-development](flows-methods-phylosophy/spec-driven-development.md)
- [repo-structure](flows-methods-phylosophy/repo-structure.md)
- [builder-methodology](flows-methods-phylosophy/builder-methodology.md)
- [rtl-coding-style](flows-methods-phylosophy/rtl-coding-style.md)
- [dv-methodology](flows-methods-phylosophy/dv-methodology.md)

## Mirrored source entry points

- [rtl](rtl/index.md)
- [dv](dv/index.md)
- [fv](fv/index.md)
- [syn](syn/index.md)
- [flows-methods-phylosophy](flows-methods-phylosophy/index.md)
