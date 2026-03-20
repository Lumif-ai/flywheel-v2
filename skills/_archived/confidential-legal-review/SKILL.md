---
name: confidential-legal-review
version: 3.0
description: >
  DEPRECATED — redirects to the unified `legal` skill. Use `legal` instead for all legal document reviews (single, comparison, and batch) with PII redaction.
---

# Confidential Legal Review — DEPRECATED

> **This skill has been superseded by the unified `legal/` skill (v1.0).**

All functionality — single document review, redline comparison, and batch deal review — with PII redaction is now handled by the `legal` skill.

**What to do:** Use the `legal` skill instead. It provides:
- Same PII-first architecture (Presidio + spaCy, fully local)
- Same three modes (review, compare, batch)
- Full detailed instructions per mode (loaded on demand from worker files)
- Entity consistency across documents via `--seed-mapping`
- Post-redaction PII verification

The `legal` skill at `~/.claude/skills/legal/SKILL.md` is the single entry point for all legal document work.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.
