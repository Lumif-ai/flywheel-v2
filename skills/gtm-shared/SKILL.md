---
name: gtm-shared
version: "1.0"
description: GTM-module shared Python helpers (gtm_utils, parallel). Not directly invokable — consumed via depends_on by gtm-* skills that need them.
enabled: false
tags:
  - library
assets:
  - "*.py"
---

Library module, not directly invokable. Provides GTM-module shared helpers:

- `gtm_utils.py` — account/contact enrichment and lookup utilities
- `parallel.py` — parallel execution helpers for batched GTM operations

Consumed by `gtm-*` skills via `depends_on: ["gtm-shared"]` where needed.
