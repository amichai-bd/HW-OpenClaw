# AGENTS.md — HW-OpenClaw repository

## Workflow

- All meaningful changes should start as an issue.
- Each issue should be implemented on a short-lived branch.
- Open a pull request for review/gating before merging to `main`.
- After merge, sync local workspace clones back to `main` before starting the next task.
- Branches are expected to be short-lived: minutes to hours, not long-running.
- After merge, delete the branch both on origin and locally.

## Project shape

- Hardware design / chip design project.
- SystemVerilog and Verilator are the initial focus.
- Future work may include debug trackers, formal verification, synthesis, and floorplanning.

## Communication

- Treat WhatsApp instructions as the source of task direction.
- Keep repository changes small and task-focused.
