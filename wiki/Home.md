# hw-openclaw wiki

This wiki is the version-controlled specification surface of the repository.

The repository is intended to be:

- spec-driven
- GitHub-flow-driven
- AI-native and CLI-first
- structurally predictable across disciplines
- gated by CI, PR-reference checks, and PR-Agent review before auto-merge

The wiki exists so that repository changes start from a written specification instead of from ad hoc code edits.

## Start here

If you are new to the repository, read these first:

- [spec-driven-development](flows-methods-phylosophy/spec-driven-development.md)
- [github-flow](flows-methods-phylosophy/github-flow.md)
- [repo-structure](flows-methods-phylosophy/repo-structure.md)
- [builder-methodology](flows-methods-phylosophy/builder-methodology.md)

If you are changing code in a discipline, jump directly to:

- [rtl overview](rtl/index.md)
- [dv overview](dv/index.md)
- [fv overview](fv/index.md)
- [syn overview](syn/index.md)

If you are looking for rules rather than structure, use:

- [rtl coding style](flows-methods-phylosophy/rtl-coding-style.md)
- [dv methodology](flows-methods-phylosophy/dv-methodology.md)
- [formal methodology](flows-methods-phylosophy/formal-methodology.md)
- [synthesis methodology](flows-methods-phylosophy/synthesis-methodology.md)

## How to use this wiki

Before implementation work starts:

1. find the relevant wiki page
2. open or update an issue that begins `according to wiki wiki/...`
3. apply the correct issue labels
4. decide whether the issue is:
   - an implementation bug under an already-correct spec
   - or a spec clarification / spec change that should update the wiki
5. implement the change on a short-lived issue branch
6. open a gated pull request that also references the wiki
7. review the final implementation against the wiki before merge
8. keep ownership of the pull request until CI is green, PR-Agent findings and review issues are fixed, and the pull request is merged
9. sync the local workspace back to `main`

The important rule is not that every issue must change the wiki.
The important rule is that every issue must begin from the wiki.

## Wiki browsing model

This wiki mirrors the source disciplines at the top level, but it is not meant to behave like a recursive file browser.

- the top-level and IP-level pages are the normal entry points
- the methodology pages under `flows-methods-phylosophy/` carry the repository-wide rules
- deeper mirrored directories do not need placeholder pages unless they have real spec content to say

Use the sidebar and the discipline overview pages first.

## Main areas

- [rtl](rtl/index.md)
- [dv](dv/index.md)
- [fv](fv/index.md)
- [syn](syn/index.md)
- [flows methods phylosophy](flows-methods-phylosophy/index.md)
