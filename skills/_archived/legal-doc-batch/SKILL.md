---
name: legal-doc-batch
version: 2.0
description: >
  DEPRECATED — redirects to the unified `legal` skill. Use `legal` instead for batch deal reviews with PII redaction.
---

# Legal Document Batch Review — DEPRECATED

> **This skill has been superseded by the unified `legal/` skill (v1.0).**

Cross-document batch analysis is now handled by the `legal` skill in Batch mode. The full batch instructions live in `~/.claude/skills/legal/workers/batch.md` and are loaded automatically when multiple related documents are detected.

**What to do:** Use the `legal` skill instead.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.
