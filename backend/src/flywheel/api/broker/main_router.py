"""Broker main router — assembles all domain sub-routers under /broker prefix."""
from __future__ import annotations

from fastapi import APIRouter

from .carriers import carriers_router
from .clients import clients_router
from .contacts import contacts_router
from .projects import projects_router
from .quotes import quotes_router
from .recommendations import recommendations_router
from .solicitations import solicitations_router

router = APIRouter(prefix="/broker", tags=["broker"])

router.include_router(clients_router)
router.include_router(contacts_router)
router.include_router(carriers_router)
router.include_router(projects_router)
router.include_router(quotes_router)
router.include_router(solicitations_router)
router.include_router(recommendations_router)
