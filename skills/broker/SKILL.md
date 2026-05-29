---
name: broker
version: "1.2"
description: Broker module shared Python helpers (api_client with Pattern 3a extract/save helpers, field_validator, portals.base, portals.mapfre). Not directly invokable — consumed via depends_on by broker-* skills.
enabled: false
tags:
  - library
assets:
  - "*.py"
  - "portals/*.py"
  - "portals/*.yaml"
---

Library module, not directly invokable. Provides the broker HTTP client
(`api_client.py`), input validators (`field_validator.py`), and Playwright
portal drivers (`portals/base.py` + `portals/mapfre.py`) consumed by `broker-*`
skills via `depends_on: ["broker"]`.

## v1.2 — Pattern 3a (Phase 150.1, CC-as-Brain)

`api_client.py` exposes 10 Pattern 3a helpers (5 `extract_*` / 5 `save_*`
pairs) for contract-analysis, policy-extraction, quote-extraction,
solicitation-draft, and recommendation-draft. Each `extract_*` returns
`{prompt, tool_schema, documents, metadata}` so Claude-in-conversation runs
inline analysis locally; each `save_*` persists the tool-use output verbatim
(backend makes ZERO LLM calls). Every helper emits
`X-Flywheel-Skill: <skill-name>` so the backend's
`require_subsidy_decision` dependency can enforce the allowlist, and accepts
BYOK via the JSON body `api_key` field.

## Playwright portals

Playwright portal state lives at `~/.flywheel/broker/portals/<carrier>/` — never
`__file__`-relative. See `portals/base.py` for the `launch_persistent_context`
contract and `portals/mapfre.py` for the mapfre STATE_DIR declaration.
