---
phase: 131-backend-atomic-release
plan: "02"
subsystem: api, database, services
tags: [sqlalchemy, fastapi, broker, services, context-store]

requires:
  - phase: 131-01
    provides: BrokerClient, BrokerClientContact, CarrierContact ORM models; broker/ package scaffold

provides:
  - BrokerClientService with create/get/list/update/delete, normalized_name dedup, context entity creation
  - BrokerContactService with client (20 limit) and carrier (10 limit) contact CRUD
  - create_context_entity() in context_store_writer.py — upsert ContextEntity, returns UUID, no commit

affects: [131-03, 131-04]

tech-stack:
  added: []
  patterns:
    - "Service methods take (db, tenant_id, ...) per call — no class-level state"
    - "All service methods call db.flush() not db.commit() — endpoint handler owns the transaction"
    - "IntegrityError from flush caught as HTTPException(409) in BrokerClientService.create/update"
    - "_normalize_name() strips legal suffixes via regex, removes accents via NFKD, collapses whitespace"
    - "Contact soft limits enforced via COUNT query before INSERT (not DB constraint)"
    - "create_context_entity uses local import for ContextEntity to avoid circular import risk"

key-files:
  created:
    - backend/src/flywheel/services/broker_client_service.py
    - backend/src/flywheel/services/broker_contact_service.py
  modified:
    - backend/src/flywheel/engines/context_store_writer.py

key-decisions:
  - "create_context_entity uses local import (from flywheel.db.models import ContextEntity inside function body) to avoid any circular import risk at module load time"
  - "_normalize_name regex strips Mexican/international legal suffixes (S.A. de C.V., S.A.P.I., S de RL) as well as US forms (LLC, Inc, Corp, Ltd)"
  - "BrokerContactService.delete_contact takes contact_type: str ('client' | 'carrier') parameter so one method handles both model types without separate endpoints"

duration: 8min
completed: 2026-04-15
---

# Phase 131 Plan 02: BrokerClientService, BrokerContactService, create_context_entity Summary

**BrokerClientService and BrokerContactService created with normalized dedup, contact soft limits, and context entity upsert — all methods flush without committing**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-15
- **Completed:** 2026-04-15
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- Added `create_context_entity()` to `context_store_writer.py` — pg_insert ON CONFLICT upsert on (tenant_id, name, entity_type), increments mention_count on conflict, returns UUID, no commit
- Created `BrokerClientService` with create/get/list/update/delete; create() computes normalized_name via `_normalize_name()`, upserts a ContextEntity, catches IntegrityError as HTTP 409
- `_normalize_name()` strips Mexican/US/EU legal suffixes (S.A. de C.V., LLC, Inc, GmbH, etc.), removes accents via NFKD, strips punctuation, collapses whitespace
- Created `BrokerContactService` with create_client_contact/list_client_contacts/update_client_contact, create_carrier_contact/list_carrier_contacts/update_carrier_contact, delete_contact
- Contact soft limits: 20 per BrokerClient, 10 per CarrierConfig — enforced via COUNT query before INSERT (not DB constraint, so graceful error message)
- Module docstring in context_store_writer.py updated to list `create_context_entity()` as a public function

## Task Commits

All tasks committed as a single per-plan commit:

1. **Task 1: Add create_context_entity() to context_store_writer.py** - `19e99ff`
2. **Task 2: Create BrokerClientService and BrokerContactService** - `19e99ff`

**Plan commit:** `19e99ff` — feat(131-02): add BrokerClientService, BrokerContactService, create_context_entity

## Files Created/Modified

- `backend/src/flywheel/services/broker_client_service.py` — BrokerClientService, CreateBrokerClientRequest, UpdateBrokerClientRequest, _normalize_name()
- `backend/src/flywheel/services/broker_contact_service.py` — BrokerContactService, CreateClientContactRequest, CreateCarrierContactRequest, UpdateContactRequest
- `backend/src/flywheel/engines/context_store_writer.py` — Added create_context_entity(), updated module docstring

## Decisions Made

- `create_context_entity` uses a local import for `ContextEntity` inside the function body to avoid circular import risk at module load time (context_store_writer imports from models, models doesn't import from context_store_writer, but the pattern is safer this way)
- `_normalize_name()` regex handles both Mexican legal suffixes (S.A. de C.V., S.A.P.I., S de RL) and common US/EU forms — this covers the primary target market for the broker module
- `BrokerContactService.delete_contact()` uses a single method with `contact_type: str` parameter to handle both BrokerClientContact and CarrierContact — reduces endpoint surface area in Plan 03

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all verification checks passed on first run.

## Next Phase Readiness

- Plan 03 (endpoint handlers) can import BrokerClientService and BrokerContactService directly
- create_context_entity is available for use by Plan 03 carrier endpoints as well
- No blockers

---
*Phase: 131-backend-atomic-release*
*Completed: 2026-04-15*
