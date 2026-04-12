# misc tools

This directory holds optional debugging utilities that are not standard repository
entrypoints.

Normal flow execution should use repo-root `./build`. Utilities here may inspect
or transform generated artifacts, but they must not become hidden flow policy.
