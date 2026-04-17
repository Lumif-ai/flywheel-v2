---
name: broker
version: "1.0"
description: Broker module shared Python helpers (api_client, field_validator, portals.base, portals.mapfre). Not directly invokable — consumed via depends_on by broker-* skills.
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

Playwright portal state lives at `~/.flywheel/broker/portals/<carrier>/` — never
`__file__`-relative. See `portals/base.py` for the `launch_persistent_context`
contract and `portals/mapfre.py` for the mapfre STATE_DIR declaration.
