"""Broker main router — assembles all domain sub-routers under /broker prefix.

Sub-routers are imported lazily so this file can be imported even before
individual sub-router files exist. During Phase 131 build-out, sub-routers
are added one plan at a time.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/broker", tags=["broker"])

# Sub-routers are included here as they are created in subsequent plans.
# Plans 02-04 will add:
#   from .clients import clients_router; router.include_router(clients_router)
#   from .contacts import contacts_router; router.include_router(contacts_router)
#   from .carriers import carriers_router; router.include_router(carriers_router)
#   from .projects import projects_router; router.include_router(projects_router)
#   from .quotes import quotes_router; router.include_router(quotes_router)
#   from .solicitations import solicitations_router; router.include_router(solicitations_router)
#   from .recommendations import recommendations_router; router.include_router(recommendations_router)
