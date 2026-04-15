---
name: git-commit
description: Use when Codex needs to inspect the full working tree, propose one or more local commit groups, suggest group-specific verification commands, and prepare each commit with explicit confirmation.
---

# Git Commit

## Overview

Use this skill for **local commits only** in this repository. Read the whole working tree, propose commit groups from all current changes, stop on risky scope, suggest verification commands per group, and wait for explicit confirmation before each local commit.

Read [project-commit-policy.md](./references/project-commit-policy.md) before acting.

## Workflow

1. Read the repo-root [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md).
2. Inspect the full working tree with:

   ```powershell
   uv run python .\skill\git-commit\scripts\inspect_commit_scope.py --repo . --format json
   ```

3. Review `workspace_files`, `proposed_groups`, `unassigned_files`, and `global_blocking_reasons`.
4. If any global blocking reason is present, stop and explain the exact block.
5. Present the proposed commit groups:
   - group id
   - files
   - support files
   - suggested verification commands
   - suggested Conventional commit title
6. Ask for explicit confirmation on one group at a time.
7. After a group is confirmed:
   - stage only that group's files
   - rerun the inspection to ensure the scope has not drifted
   - rerun the suggested verification commands
   - show the final Conventional commit title
   - wait for explicit confirmation again before `git commit`
8. After one group is committed, inspect the remaining working tree again and continue with the next group if any remain.

## Hard Stops

Refuse to continue when any of these is true:

- No workspace changes
- Any file is partially staged and partially unstaged
- A file cannot be assigned to exactly one commit group
- A group has no reliable verification command and is not docs-only
- The suggested title cannot describe the group in one clear line

When the scope is ambiguous, stop and ask for manual cleanup instead of forcing a commit.

## Commit Scope Rules

- Treat `tracked`, `unstaged`, and `untracked` changes as candidates during analysis.
- Do not attempt hunk splitting.
- Do not silently override partial staging.
- Allow docs, tests, config, and assets to attach to a single primary topic only when the attachment is unambiguous.
- Do not revert unrelated changes.
- Do not auto-push.
- Do not open or suggest a PR as part of this skill.

## Verification Rules

- Use the suggested verification commands from the inspection report.
- Always rerun them before the commit.
- Docs-only groups may proceed without code verification.
- Never rely on historical verification results.

## Commit Title Rules

Use a one-line Conventional commit title:

- `feat`: new behavior or new capability
- `fix`: user-visible bug fix
- `refactor`: structure change without intended behavior change
- `docs`: documentation-only change
- `test`: test-only change
- `chore`: maintenance work with no better type

Requirements:

- Keep it in English
- Keep it short
- Describe one commit group only
- Never merge unrelated themes into one title

## Resources

### scripts/

- [inspect_commit_scope.py](./scripts/inspect_commit_scope.py): Inspect the full working tree, build proposed commit groups, and return suggested verification commands.

### references/

- [project-commit-policy.md](./references/project-commit-policy.md): Repository-specific commit grouping, verification, and blocking rules.
