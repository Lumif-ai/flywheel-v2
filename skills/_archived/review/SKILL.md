---
name: review
enabled: false
version: 1.0.0
description: |
  Pre-landing PR review. Analyzes diff against main for SQL safety, LLM trust
  boundary violations, conditional side effects, and other structural issues.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - AskUserQuestion
web_tier: 1
---

# Pre-Landing PR Review

You are running the `/review` workflow. Analyze the current branch's diff against main for structural issues that tests don't catch.

---

## Step 1: Check branch

1. Run `git branch --show-current` to get the current branch.
2. If on `main`, output: **"Nothing to review — you're on main or have no changes against main."** and stop.
3. Run `git fetch origin main --quiet && git diff origin/main --stat` to check if there's a diff. If no diff, output the same message and stop.

---

## Step 2: Read the checklist

Read `.claude/skills/review/checklist.md`.

**If the file cannot be read, STOP and report the error.** Do not proceed without the checklist.

---

## Step 3: Get the diff

Fetch the latest main to avoid false positives from a stale local main:

```bash
git fetch origin main --quiet
```

Run `git diff origin/main` to get the full diff. This includes both committed and uncommitted changes against the latest main.

---

## Step 4: Two-pass review

Apply the checklist against the diff in two passes:

1. **Pass 1 (CRITICAL):** SQL & Data Safety, LLM Output Trust Boundary
2. **Pass 2 (INFORMATIONAL):** Conditional Side Effects, Magic Numbers & String Coupling, Dead Code & Consistency, LLM Prompt Issues, Test Gaps, View/Frontend

Follow the output format specified in the checklist. Respect the suppressions — do NOT flag items listed in the "DO NOT flag" section.

---

## Step 5: Output findings

**Always output ALL findings** — both critical and informational. The user must see every issue.

- If CRITICAL issues found: output all findings, then for EACH critical issue use a separate AskUserQuestion with the problem, your recommended fix, and options (A: Fix it now, B: Acknowledge, C: False positive — skip).
  After all critical questions are answered, output a summary of what the user chose for each issue. If the user chose A (fix) on any issue, apply the recommended fixes. If only B/C were chosen, no action needed.
- If only non-critical issues found: output findings. No further action needed.
- If no issues found: output `Pre-Landing Review: No issues found.`

---

## Important Rules

- **Read the FULL diff before commenting.** Do not flag issues already addressed in the diff.
- **Read-only by default.** Only modify files if the user explicitly chooses "Fix it now" on a critical issue. Never commit, push, or create PRs.
- **Be terse.** One line problem, one line fix. No preamble.
- **Only flag real problems.** Skip anything that's fine.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/review.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Review focus areas
- Severity thresholds

### What NOT to save
- Session-specific content, temporary overrides, confidential data

## Dependency Check (Step 0a)
- Verify current directory is a git repository (`git rev-parse --is-inside-work-tree`). Abort if not.
- Verify `origin/main` is reachable (`git rev-parse --verify origin/main`). Abort if remote is not configured.
- Verify `.claude/skills/review/checklist.md` exists. Abort if missing -- the review cannot proceed without the checklist.

## Input Validation
- Confirm the current branch is not `main` before computing a diff. If on `main`, stop immediately.
- Verify `git diff origin/main --stat` produces non-empty output. If no diff exists, report "Nothing to review" and stop.
- If a merge conflict is in progress (`git ls-files -u | head -1`), stop and tell the user to resolve conflicts first.

## Error Handling
- **No diff found:** Report "Nothing to review -- you're on main or have no changes against main." and stop cleanly.
- **Merge conflict in progress:** Detect unmerged files and stop with "Merge conflict detected. Resolve conflicts before running /review."
- **Checklist file unreadable:** If `checklist.md` cannot be read, stop immediately rather than running a partial review.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
