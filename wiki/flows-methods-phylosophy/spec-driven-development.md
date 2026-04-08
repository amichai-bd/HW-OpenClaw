# spec driven development

The repository follows spec-driven development.

In this repository, the specification is not a separate document that drifts away from code.
The specification is the version-controlled `wiki/` tree.

## What spec driven means here

- every meaningful change starts from an issue
- every issue must reference the relevant wiki path
- every issue should carry the correct labels for the change type
- implementation should follow the spec instead of inventing behavior ad hoc in code
- if code reveals ambiguity, missing detail, or a wrong assumption in the wiki, the wiki should be clarified as part of the change
- if the issue is only an implementation bug under an already-correct spec, `src/` may change without a wiki edit, but the issue must still reference the wiki
- once the issue becomes a pull request, the agent should keep ownership of it until CI is green, review feedback is resolved, and the pull request merges

## Change categories

### implementation bug under correct spec

The wiki already says the right thing.
The implementation is simply wrong or incomplete.

In that case:

- the issue still starts from the wiki
- the code changes
- the wiki may remain unchanged

### implementation bug caused by ambiguous or weak spec

The implementation problem exposed a wiki problem:

- missing detail
- unclear rule
- wrong abstraction boundary
- high-level wording that was not actionable enough

In that case:

- the issue starts from the current wiki
- the wiki is clarified
- the implementation is updated accordingly

### new feature / refactor / behavioral change

If the intended behavior or structure changes, the wiki should change too.

That means:

- update the wiki first or together with the code
- then align the implementation
- then review the final implementation against the new wiki text

## Required issue framing

Recommended issue opening pattern:

```text
according to wiki wiki/<path>/...
```

Good examples:

```text
according to wiki wiki/rtl/fifo/code/index.md
according to wiki wiki/flows-methods-phylosophy/rtl-coding-style.md
according to wiki wiki/flows-methods-phylosophy/dv-methodology.md
```

## Review expectation

Every change should leave the repository in one of these two states:

- wiki was already correct and the implementation now matches it
- wiki and implementation were updated together and now match each other

Any other state is drift, and drift should be treated as a process problem.

## Expected completion state

A spec-driven change is only complete when all of the following are true:

- the issue references the relevant wiki path
- the issue is labeled correctly
- the pull request references the relevant wiki path
- required PR/build checks are green
- the pull request is merged through the normal gated GitHub flow, preferably with native auto-merge enabled
- the local workspace is synced back to `main`
