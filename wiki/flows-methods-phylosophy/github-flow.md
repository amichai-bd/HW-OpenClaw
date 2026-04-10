# github flow

The repository follows GitHub flow.

- all meaningful work starts from an issue
- each issue starts from the wiki and should use the correct labels
- each issue should be implemented on a short-lived branch
- branch names should start with the issue number
- each change should go through a pull request before merge to `main`
- the agent that opens the pull request keeps ownership of it until merge
- agents should poll pull requests for CI, PR-Agent, CodeRabbit, and review state, fix problems, and keep pushing to the same branch until the pull request merges
- CI gates `main`, and issue / pull-request reference checks plus PR-Agent review and CodeRabbit review are part of the normal path
- native GitHub auto-merge is the expected merge path once the required PR/build checks and conversation-resolution requirements are clean
- after merge, local workspaces should sync back to `main`
- short-lived branches should be deleted both locally and on origin

PR-Agent findings are part of the normal PR ownership model and should be handled before merge.
CodeRabbit findings and unresolved review threads are also part of the normal PR ownership model and should be handled before merge.

The repository intentionally uses two different review mechanisms:

- PR-Agent is the repository-managed GitHub Actions review gate. It is configured in `.pr_agent.toml`, appears as a required PR check, and should present findings in a structured format.
- CodeRabbit is the GitHub App review gate. It is configured in `.coderabbit.yaml`, appears as the required `CodeRabbit` check, and can also block merge through unresolved review conversations.

Agents should not treat either review system as optional. Both must be watched and handled until the pull request is clean enough to auto-merge.
