# hw-openclaw wiki

This wiki is the version-controlled specification surface of the repository.

The repository is intended to be:

- spec-driven
- GitHub-flow-driven
- AI-native and CLI-first
- structurally predictable across disciplines
- gated by CI, PR-reference checks, PR-Agent review, and CodeRabbit review before auto-merge
- explicit about the difference between repository-managed review checks and GitHub App review threads

The wiki exists so that repository changes start from a written specification instead of from ad hoc code edits.

## Start here

If you are new to the repository, read these first:

- [spec-driven-development](flows-methods-phylosophy/spec-driven-development)
- [github-flow](flows-methods-phylosophy/github-flow)
- [repo-structure](flows-methods-phylosophy/repo-structure)
- [builder-methodology](flows-methods-phylosophy/builder-methodology)

For a fresh clone:

- run `./setup`
- then use `./build`

If you are changing code in a discipline, jump directly to:

- [rtl overview](rtl/rtl)
- [dv overview](dv/dv)
- [fv overview](fv/fv)
- [syn overview](syn/syn)

If you are looking for rules rather than structure, use:

- [rtl coding style](flows-methods-phylosophy/rtl-coding-style)
- [dv methodology](flows-methods-phylosophy/dv-methodology)
- [formal methodology](flows-methods-phylosophy/formal-methodology)
- [synthesis methodology](flows-methods-phylosophy/synthesis-methodology)

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
8. keep ownership of the pull request until CI is green, PR-Agent findings, CodeRabbit findings, and review issues are fixed, and the pull request is merged

   PR-Agent and CodeRabbit both participate in the merge gate, but they do so differently:

   - PR-Agent runs as a repository-managed GitHub Actions check, guided by `.pr_agent.toml`
   - CodeRabbit runs as a GitHub App review/check, guided by `.coderabbit.yaml`
   - PR-Agent should produce structured findings that agents work through
   - CodeRabbit can also hold the pull request open through unresolved review conversations when `request_changes_workflow: true` is enabled

9. sync the local workspace back to `main`

The important rule is not that every issue must change the wiki.
The important rule is that every issue must begin from the wiki.

## Wiki browsing model

This wiki mirrors the source disciplines at the top level, but it is not meant to behave like a recursive file browser.

- the top-level and IP-level pages are the normal entry points
- the methodology pages under `flows-methods-phylosophy/` carry the repository-wide rules
- deeper mirrored directories do not need placeholder pages unless they have real spec content to say

Use the hierarchical sidebar and the discipline overview pages first.

### GitHub Wiki tab versus this `wiki/` tree

The **versioned source** is this directory on `main`. The **GitHub Wiki** UI is a generated mirror: the on-demand `update-wiki` skill clones the wiki git repository (`*.wiki.git`), replaces its content with the local `wiki/` tree, commits, pushes, and removes the temporary clone.

Prefer editing markdown here through pull requests. Edits made only in the Wiki web editor can be overwritten on the next skill-driven publish.

Publishing runs by explicit agent action through `.codex/skills/update-wiki/scripts/update-wiki.py`. The compatibility wrapper `./bin/wiki-publish` delegates to the same skill script.

To **inspect the live published wiki as a git tree** (optional), from the repository root clone the wiki remote into the ignored folder `HW-OpenClaw-wiki` (see root `.gitignore`):

```sh
git clone https://github.com/amichai-bd/HW-OpenClaw.wiki.git HW-OpenClaw-wiki
```

To compare with what the skill would publish from this `wiki/` tree, run `./bin/wiki-publish --dry-run --output /tmp/hw-wiki-publish-preview` and diff against `HW-OpenClaw-wiki`.

## Main areas

- [rtl](rtl/rtl)
- [dv](dv/dv)
- [fv](fv/fv)
- [syn](syn/syn)
- [flows methods philosophy](flows-methods-phylosophy/flows-methods-phylosophy)
