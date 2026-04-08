# github flow

The repository follows GitHub flow.

- all meaningful work starts from an issue
- each issue starts from the wiki and should use the correct labels
- each issue should be implemented on a short-lived branch
- branch names should start with the issue number
- each change should go through a pull request before merge to `main`
- the agent that opens the pull request keeps ownership of it until merge
- agents should poll pull requests for CI, PR-Agent, and review state, fix problems, and keep pushing to the same branch until the pull request merges
- CI gates `main`, and issue / pull-request reference checks plus PR-Agent review are part of the normal path
- native GitHub auto-merge is the expected merge path once the required PR/build checks and conversation-resolution requirements are clean
- after merge, local workspaces should sync back to `main`
- short-lived branches should be deleted both locally and on origin

PR-Agent findings are part of the normal PR ownership model and should be handled before merge.
