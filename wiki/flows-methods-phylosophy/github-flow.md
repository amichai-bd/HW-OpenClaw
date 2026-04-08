# github flow

The repository follows GitHub flow.

- all meaningful work starts from an issue
- each issue starts from the wiki and should use the correct labels
- each issue should be implemented on a short-lived branch
- branch names should start with the issue number
- each change should go through a pull request before merge to `main`
- the agent that opens the pull request keeps ownership of it until merge
- agents should poll pull requests for CI and review state, fix problems, and keep pushing to the same branch until the pull request merges
- CI gates `main`, and issue / pull-request reference checks are part of the normal path
- native GitHub auto-merge is the expected merge path once the required review and required checks are clean
- after merge, local workspaces should sync back to `main`
- short-lived branches should be deleted both locally and on origin
