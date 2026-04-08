# spec driven development

The repository follows spec-driven development.

- every meaningful change starts from an issue
- every issue must reference the relevant wiki path and begin from the intended specification
- implementation should follow the spec instead of inventing behavior ad hoc in code
- if code reveals ambiguity, missing detail, or a wrong assumption in the wiki, the wiki should be clarified as part of the change
- if the issue is only an implementation bug under an already-correct spec, `src/` may change without a wiki edit, but the issue must still reference the wiki

Recommended issue opening pattern:

```text
according to wiki wiki/<path>/...
```
