# github flow

The repository follows GitHub flow.

- all meaningful work starts from an issue
- each issue should be implemented on a short-lived branch
- branch names should start with the issue number
- each change should go through a pull request before merge to `main`
- CI gates `main`
- after merge, local workspaces should sync back to `main`
- short-lived branches should be deleted both locally and on origin
