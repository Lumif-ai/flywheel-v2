---
name: _shared
version: "0.1.0"
description: Shared Python helpers (context_utils, recipe_utils, validate_skills) reused across skills. Not directly invokable — consumed via depends_on.
enabled: false
tags: ["library"]
assets: ["*.py"]
---

Library module, not directly invokable. Provides shared utilities consumed by other skills via `depends_on: ["_shared"]`.
