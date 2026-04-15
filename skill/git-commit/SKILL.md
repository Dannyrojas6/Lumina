---
name: git-commit
description: Use when Codex needs to inspect the full working tree, propose one or more local commit groups, suggest group-specific verification commands, and prepare each commit with explicit confirmation.
---

# Git Commit

## Overview

Use this skill for **local commits only** in this repository. Read the whole working tree, propose commit groups from all current changes, route ambiguous support files into `review_candidates`, and wait for explicit confirmation before each local commit.

Read [project-commit-policy.md](./references/project-commit-policy.md) before acting.

## Workflow

1. Read the repo-root [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md).
2. Inspect the full working tree with:

   ```powershell
   uv run python .\skill\git-commit\scripts\inspect_commit_scope.py --repo . --format json
   ```

3. Review `workspace_files`, `proposed_groups`, `review_candidates`, `unassigned_files`, and `global_blocking_reasons`.
4. If any hard global blocking reason is present, stop and explain the exact block.
5. If `review_candidates` is non-empty:
   - inspect diffs for those files
   - draft one recommended target group per file, with a short reason
   - present the recommendations for human confirmation
   - only after confirmation, include those files in the confirmed group
6. Present the proposed commit groups:
   - group id
   - files
   - support files
   - suggested verification commands
   - suggested Conventional commit title
7. Ask for explicit confirmation on one group at a time.
8. After a group is confirmed:
   - stage only that group's files
   - rerun the inspection to ensure the scope has not drifted
   - rerun the suggested verification commands
   - show the final Conventional commit title
   - wait for explicit confirmation again before `git commit`
9. After one group is committed, inspect the remaining working tree again and continue with the next group if any remain.

## Hard Stops

Refuse to continue when any of these is true:

- No workspace changes
- No commit candidates remain after ignoring local-only files
- Any file is partially staged and partially unstaged
- A file still cannot be assigned after the review-candidate pass
- A group has no reliable verification command and is not docs-only
- The suggested title cannot describe the group in one clear line

`review_candidates` are not a hard stop by themselves. They require an agent review pass and human confirmation before staging.

## Commit Scope Rules

- Treat `tracked`, `unstaged`, and `untracked` changes as candidates during analysis.
- Do not attempt hunk splitting.
- Do not silently override partial staging.
- Allow docs, tests, config, and assets to attach to a single primary topic only when the attachment is unambiguous.
- When attachment is plausible but not automatic, move the file into `review_candidates` instead of hard-blocking immediately.
- Report known local-only note files as ignored instead of treating them as commit candidates.
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
