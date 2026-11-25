---
name: vibeops-manage-worktrees
description: Use when parallel implementation needs isolated Git workspaces, or when integrating and cleaning up completed worktrees.
---

# Manage worktrees

Use the host terminal and Git tools; do not start another coding CLI.
1. Inspect git status --short, git worktree list --porcelain, repository root and current branch. Preserve user changes. Record the intended base commit and integration branch in artifacts/sdlc-progress.md.
2. Decide whether isolation is necessary. Read-only tasks can share a workspace. Use separate worktrees for independent source edits. Assign each worker explicit paths and dependencies; isolation does not eliminate merge conflicts.
3. Choose a unique sibling path outside the repository and a new branch, such as sdlc/task-id. Check both are unused. Quote paths. Run git worktree add -b BRANCH PATH BASE_COMMIT with concrete values. Never overwrite an existing directory or force branch reuse.
4. Inspect project setup instructions in the new directory. Run authorized setup and relevant baseline checks; record pre-existing failures before implementation. Run each worker in its assigned directory with goal, acceptance criteria, owned paths and required checks.
5. Collect changed paths, commits, exact check commands and outcomes, unresolved issues. Inspect the actual diff. Create scoped commits only for the assigned changes; avoid staging unrelated files or secrets.
6. Integrate sequentially into the recorded target branch only when integration is within the user request. Check target status first. Merge or cherry-pick the reviewed commits using the project convention. Resolve conflicts by inspecting both changes; never discard either side blindly. Rerun affected checks after integration and record the tested commit. If integration is not authorized, leave the branch ready for a PR.
7. Before cleanup, inspect status including untracked files and confirm work is integrated or preserved in a committed branch. Use git worktree remove PATH without --force. If removal refuses, retain it and report why. Keep the branch by default; never delete branches or uncommitted work merely to complete cleanup.
