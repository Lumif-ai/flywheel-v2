"""
web_app.py - FastAPI web application for Flywheel.

Provides the web UI for the Flywheel context store with:
  - Auth stub (cookie sessions, ready for 11B OAuth)
  - Dashboard with health metrics, growth chart, attribution, context file browser
  - Onboarding flow (Tier 1 URL crawl, Tier 2 document upload, Tier 3 guided questions)
  - Skill showcase with engine type badges
  - API routes for HTMX partial updates
  - Static file serving and Jinja2 template rendering
  - lumif.ai branded layout with data ownership messaging

All routes use sync `def` (not async) because they call blocking
context_utils/health_monitor functions. FastAPI auto-runs sync routes
in a threadpool.
"""

import asyncio
import io
import logging
import os
import re
import secrets
import sys
import uuid
import zipfile
from pathlib import Path

# Load .env file (for ANTHROPIC_API_KEY, etc.) before any SDK imports
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))

logger = logging.getLogger(__name__)
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# sys.path setup (same pattern as other src/ modules)
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Import from existing modules (graceful fallback)
# ---------------------------------------------------------------------------

_health_monitor = None
_context_utils = None

try:
    import health_monitor as _health_monitor
except ImportError:
    _health_monitor = None

try:
    import context_utils as _context_utils
except ImportError:
    _context_utils = None

# Company intelligence module (onboarding)
_company_intel = None
try:
    import company_intel as _company_intel
except ImportError:
    _company_intel = None

# Retention module (contextual suggestions, what's changed)
_retention = None
try:
    import retention as _retention
except ImportError:
    _retention = None

# Integration framework
_integration_framework = None
try:
    import integration_framework as _integration_framework
except ImportError:
    _integration_framework = None

# Skill converter (skill listing)
_skill_converter = None
try:
    from skill_converter import ENGINE_REGISTRY as _ENGINE_REGISTRY
    import skill_converter as _skill_converter
except ImportError:
    _ENGINE_REGISTRY = {}
    _skill_converter = None

# Work items module
_work_items = None
try:
    import work_items as _work_items
except ImportError:
    _work_items = None

# Execution gateway (skill runner)
_execution_gateway = None
try:
    import execution_gateway as _execution_gateway
except ImportError:
    _execution_gateway = None

# Skill runner web (SSE streaming, output storage)
_skill_runner_web = None
try:
    import skill_runner_web as _skill_runner_web
except ImportError:
    _skill_runner_web = None

# Output renderer (HTML rendering of skill outputs)
_output_renderer = None
try:
    import output_renderer as _output_renderer
except ImportError:
    _output_renderer = None

# Suggestion engine (MAINTAIN section of agenda)
_suggestions = None
try:
    import suggestions as _suggestions
except ImportError:
    _suggestions = None

# Scheduler module (recurring skill execution)
_scheduler = None
try:
    import scheduler as _scheduler
except ImportError:
    _scheduler = None


def _get_health_dashboard() -> dict:
    """Get health dashboard data with graceful fallback."""
    if _health_monitor is not None:
        try:
            return _health_monitor.get_health_dashboard()
        except Exception:
            pass
    return {
        "file_count": 0,
        "total_entries": 0,
        "staleness_percentage": 0.0,
        "contradiction_count": 0,
        "last_backup_time": None,
        "synthesizer_health": {"status": "UNAVAILABLE"},
        "catalog_sync": True,
        "manifest_integrity": True,
        "timestamp": "unavailable",
    }


# ---------------------------------------------------------------------------
# App lifespan (background runner lifecycle)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app):
    """Start background runner and scheduler on startup, stop on shutdown."""
    # Start background runner (from Plan 06)
    try:
        from background_runner import start_runner
        start_runner()
        logger.info("Background runner started via lifespan")
    except ImportError:
        logger.debug("background_runner not available, skipping")
    except Exception as e:
        logger.warning("Failed to start background runner: %s", e)

    # Start scheduler (from Plan 07)
    _sched_thread = None
    try:
        from scheduler import SchedulerThread
        _sched_thread = SchedulerThread()
        _sched_thread.start()
        logger.info("Scheduler started via lifespan")
    except ImportError:
        logger.debug("scheduler not available, skipping")
    except Exception as e:
        logger.warning("Failed to start scheduler: %s", e)

    yield

    # Stop scheduler (from Plan 07)
    if _sched_thread is not None:
        try:
            _sched_thread.stop()
            logger.info("Scheduler stopped via lifespan")
        except Exception as e:
            logger.warning("Failed to stop scheduler: %s", e)

    # Stop background runner (from Plan 06)
    try:
        from background_runner import stop_runner
        stop_runner()
        logger.info("Background runner stopped via lifespan")
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Failed to stop background runner: %s", e)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Flywheel", version="0.1.0", lifespan=lifespan)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(_DIR, "static")),
    name="static",
)

# Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(_DIR, "templates"))

# Data ownership statement
DATA_OWNERSHIP = (
    "Your data lives on your machine. "
    "Export everything anytime. No lock-in."
)

# ---------------------------------------------------------------------------
# Auth stub (simple cookie session for 11B OAuth readiness)
# ---------------------------------------------------------------------------

_sessions: dict = {}

# ---------------------------------------------------------------------------
# Onboarding work types and sessions
# ---------------------------------------------------------------------------

ONBOARDING_WORK_TYPES = {
    "meeting": {"skill": "meeting-prep", "label": "Meeting Prep"},
    "outreach": {"skill": "gtm-outbound-messenger", "label": "Outreach"},
    "legal_review": {"skill": "legal-review", "label": "Legal Review"},
    "analysis": {"skill": "company-fit-analyzer", "label": "Competitive Analysis"},
    "investor": {"skill": "investor-update", "label": "Investor Update"},
    "demo": {"skill": "demo-script", "label": "Demo Script"},
}

# Separate onboarding session store (keyed by session_id token)
# Stores crawl results, company name, URL across onboarding steps
_onboarding_sessions: dict = {}


def get_current_user(request: Request) -> Optional[dict]:
    """Read flywheel_session cookie, return session dict or None."""
    session_id = request.cookies.get("flywheel_session")
    if not session_id:
        return None
    return _sessions.get(session_id)


def require_auth(request: Request) -> dict:
    """Like get_current_user but raises HTTPException(401) if no session."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"HX-Redirect": "/auth/login"},
        )
    return user


# ---------------------------------------------------------------------------
# Template context injection
# ---------------------------------------------------------------------------

def _template_context(request: Request, **kwargs) -> dict:
    """Build template context with injected globals."""
    user = get_current_user(request)
    ctx = {
        "request": request,
        "current_user": user,
        "data_ownership": DATA_OWNERSHIP,
    }
    ctx.update(kwargs)
    return ctx


def _is_htmx(request: Request) -> bool:
    """Check if the request is an HTMX request (content swap, not full page load)."""
    return request.headers.get("HX-Request") == "true"


def _page_context(request: Request, active_page: str, **kwargs) -> dict:
    """Build template context with active_page for sidebar highlighting."""
    ctx = _template_context(request)
    ctx["active_page"] = active_page
    ctx.update(kwargs)
    return ctx


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/login", response_class=HTMLResponse)
def auth_login_page(request: Request):
    """Render login page (stub)."""
    return templates.TemplateResponse(
        "auth/login.html",
        _template_context(request),
    )


@app.post("/auth/login")
def auth_login(request: Request, user_id: str = Form(...)):
    """Create session with cookie."""
    # Validate user_id to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', user_id):
        return templates.TemplateResponse(
            "auth/login.html",
            _template_context(request, error="Invalid user ID format"),
        )
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {
        "user_id": user_id,
        "session_id": session_id,
    }
    response = RedirectResponse(url="/agenda", status_code=303)
    response.set_cookie(
        key="flywheel_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )
    return response


@app.post("/auth/logout")
def auth_logout(request: Request):
    """Clear session cookie, redirect to login."""
    session_id = request.cookies.get("flywheel_session")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="flywheel_session")
    return response


@app.get("/auth/callback")
def auth_callback(request: Request):
    """OAuth callback placeholder for 11B."""
    # TODO: 11B OAuth attachment point -- handle OAuth provider callback here
    return RedirectResponse(url="/auth/login", status_code=303)


# ---------------------------------------------------------------------------
# Page routes (sync def -- blocking I/O via threadpool)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """Redirect to agenda if logged in, otherwise to onboarding."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/agenda", status_code=303)
    return RedirectResponse(url="/onboarding", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Dashboard page (requires auth).

    Fetches health metrics, growth data (7-day activity), attribution
    summary, context file stats, and contextual suggestions.
    """
    user = require_auth(request)
    health = _get_health_dashboard()

    # Growth data: entries added per day over last 7 days
    growth = _compute_growth_data()

    # Attribution summary: which agents/sources contributed most
    attribution_summary = _compute_attribution_summary()

    # Per-file stats
    file_stats = _compute_file_stats()

    # Contextual suggestion
    suggestion = None
    if _retention is not None:
        try:
            suggestion = _retention.get_contextual_suggestion()
        except Exception:
            pass

    # What's changed
    whats_changed = None
    if _retention is not None:
        try:
            whats_changed = _retention.get_whats_changed(user.get("user_id", ""))
        except Exception:
            pass

    # Determine if context store is empty (for guided setup empty state)
    is_context_empty = (
        health.get("total_entries", 0) == 0
        if isinstance(health, dict) else True
    )

    ctx = _page_context(
        request,
        active_page="dashboard",
        health=health,
        growth=growth,
        attribution_summary=attribution_summary,
        file_stats=file_stats,
        suggestion=suggestion,
        whats_changed=whats_changed,
        is_context_empty=is_context_empty,
    )
    tpl = "partials/dashboard_content.html" if _is_htmx(request) else "dashboard.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/agenda", response_class=HTMLResponse)
def agenda(request: Request):
    """Agenda page -- primary landing page for logged-in users.

    Groups work items into four sections:
      PREPARE: upcoming/preparing meetings and demos
      ACT: ready items needing user attention
      REVIEW: items needing review or recently completed
      MAINTAIN: rule-based suggestions from suggestions engine
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    # Load all work items
    all_items = []
    if _work_items is not None:
        try:
            all_items = _work_items.list_work_items(user_id)
        except Exception:
            pass

    # Group into sections
    prepare_items = []
    act_items = []
    review_items = []

    now = datetime.now()
    recent_cutoff = now - timedelta(days=3)

    for item in all_items:
        if item.status in ("upcoming", "preparing") and item.type in ("meeting", "demo"):
            prepare_items.append(item)
        elif item.status == "ready":
            act_items.append(item)
        elif item.status == "needs_review":
            review_items.append(item)
        elif item.status == "done":
            try:
                updated = datetime.fromisoformat(item.updated_at)
                if updated > recent_cutoff:
                    review_items.append(item)
            except (ValueError, TypeError):
                pass

    # Get MAINTAIN suggestions
    maintain_suggestions = []
    if _suggestions is not None:
        try:
            maintain_suggestions = _suggestions.get_suggestions(user_id)
        except Exception:
            pass

    # Get schedules for AUTOMATE section
    user_schedules = []
    suggested_schedules = []
    available_skills = []
    if _scheduler is not None:
        try:
            user_schedules = _scheduler.list_schedules(user_id)
        except Exception:
            pass
        # Filter suggested schedules by what user already has
        existing_skills = {s.skill_name for s in user_schedules}
        suggested_schedules = [
            s for s in _scheduler.SUGGESTED_SCHEDULES
            if s["skill_name"] not in existing_skills
        ]
    # Build available skills list from ENGINE_REGISTRY
    if _ENGINE_REGISTRY:
        available_skills = sorted(set(
            k.replace("ctx-", "") for k in _ENGINE_REGISTRY.keys()
        ))

    # Agenda count for sidebar badge (total actionable items)
    agenda_count = len(prepare_items) + len(act_items) + len(review_items)

    # Determine empty state type when no work items exist
    empty_state_type = None
    if not all_items:
        # Check if user has any companies in context store
        has_companies = False
        if _context_utils is not None:
            try:
                raw = _context_utils.read_context("company-core.md", "web-app")
                if raw and raw.strip():
                    has_companies = True
            except Exception:
                pass

        if not has_companies:
            empty_state_type = "new_user"
        else:
            # Check if calendar integration is connected
            has_calendar = False
            if _integration_framework is not None:
                try:
                    settings = _integration_framework.get_integration_settings(user_id)
                    cal_info = settings.get("google_calendar", settings.get("calendar", {}))
                    if isinstance(cal_info, dict) and cal_info.get("enabled"):
                        has_calendar = True
                except Exception:
                    pass

            if not has_calendar:
                empty_state_type = "no_calendar"
            else:
                empty_state_type = "clear_day"

    ctx = _page_context(
        request,
        active_page="agenda",
        prepare_items=prepare_items,
        act_items=act_items,
        review_items=review_items,
        maintain_suggestions=maintain_suggestions,
        schedules=user_schedules,
        suggested_schedules=suggested_schedules,
        available_skills=available_skills,
        today=now.strftime("%A, %B %d"),
        agenda_count=agenda_count if agenda_count > 0 else None,
        empty_state_type=empty_state_type,
    )
    tpl = "partials/agenda_content.html" if _is_htmx(request) else "agenda.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request):
    """Onboarding page (no auth required)."""
    return templates.TemplateResponse(
        "onboarding.html",
        _template_context(request),
    )


@app.post("/onboarding/url", response_class=HTMLResponse)
def onboarding_url(request: Request, company_url: str = Form(...)):
    """Tier 1: Crawl company URL, store results, redirect to work picker.

    Uses sync def because write_company_intelligence makes blocking
    fcntl.flock calls. asyncio.run() creates an event loop in the
    threadpool thread for the async crawl_company call.
    """
    if _company_intel is None:
        return HTMLResponse(
            '<div class="card error-card"><p>Company intelligence module not available.</p></div>'
        )

    try:
        # Auto-prefix https:// if missing but contains a dot
        url = company_url.strip()
        if "." in url and not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Crawl company website (async function called from sync route)
        crawl_result = asyncio.run(_company_intel.crawl_company(url))

        if not crawl_result.get("success"):
            return templates.TemplateResponse(
                "onboarding_result.html",
                _template_context(
                    request,
                    error="Could not crawl %s. Try uploading a document instead." % url,
                ),
            )

        # Combine raw pages into single text
        raw_text = "\n\n".join(crawl_result.get("raw_pages", {}).values())

        # Structure the intelligence
        intelligence = _company_intel.structure_intelligence(raw_text, "website-crawl")

        # Write to context store
        _company_intel.write_company_intelligence(
            intelligence, agent_id="web"
        )

        # Create onboarding session with crawl data
        ob_session_id = secrets.token_urlsafe(16)
        _onboarding_sessions[ob_session_id] = {
            "company_name": intelligence.get("company_name", ""),
            "company_url": url,
            "intelligence": intelligence,
            "pages_crawled": crawl_result.get("pages_crawled", 0),
        }

        # Redirect to work picker
        return RedirectResponse(
            url="/onboarding/work-picker?session=%s" % ob_session_id,
            status_code=303,
        )

    except Exception as e:
        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                error="Error processing URL: %s" % str(e),
            ),
        )


@app.get("/api/onboarding/crawl/stream")
async def crawl_stream(request: Request, url: str = ""):
    """SSE streaming endpoint for onboarding URL crawl.

    Streams crawl progress as Server-Sent Events: stage updates, individual
    facts, discovered pages, profile summary, and completion/error events.

    Uses async def + asyncio.to_thread() for blocking crawl_company call.
    Reuses sse_event helper from skill_runner_web.
    """
    from skill_runner_web import sse_event

    # Validate URL
    url = url.strip()
    if not url:
        async def _err():
            yield sse_event("error", {"message": "No URL provided.", "detail": "url parameter is empty"})
        return StreamingResponse(_err(), media_type="text/event-stream")

    if "." in url and not url.startswith(("http://", "https://")):
        url = "https://" + url

    if "." not in url:
        async def _err():
            yield sse_event("error", {"message": "That doesn't look like a valid URL.", "detail": "No dot in URL: %s" % url})
        return StreamingResponse(_err(), media_type="text/event-stream")

    if _company_intel is None:
        async def _err():
            yield sse_event("error", {"message": "Company intelligence module is not available.", "detail": "company_intel import failed"})
        return StreamingResponse(_err(), media_type="text/event-stream")

    async def _generate():
        import json as _json
        import time

        # Icon and label maps for streaming facts
        fact_icon_map = {
            "company_name": "Building2",
            "tagline": "Quote",
            "what_they_do": "FileText",
            "industries": "Briefcase",
            "target_customers": "Users",
            "products": "Package",
            "competitors": "Swords",
            "pricing_model": "CreditCard",
            "key_differentiators": "Sparkles",
            # Enrichment keys
            "employees": "UsersRound",
            "headquarters": "MapPin",
            "key_people": "UserCheck",
            "funding": "TrendingUp",
            "recent_news": "Newspaper",
            "tech_stack": "Code",
            "social_accounts": "Share2",
            "recent_press": "Newspaper",
            "blog_topics": "FileText",
        }

        fact_label_map = {
            "company_name": "Company",
            "tagline": "Tagline",
            "what_they_do": "Overview",
            "industries": "Industry",
            "target_customers": "Customers",
            "products": "Products",
            "competitors": "Competitors",
            "pricing_model": "Pricing",
            "key_differentiators": "Differentiators",
            # Enrichment keys
            "employees": "Team Size",
            "headquarters": "Headquarters",
            "key_people": "Leadership",
            "funding": "Funding",
            "recent_news": "Recent News",
            "tech_stack": "Tech Stack",
            "social_accounts": "Social",
            "recent_press": "Recent News",
            "blog_topics": "Blog Topics",
        }

        # Helper to emit a single fact, returns True if emitted
        def _format_fact(key, value, source="site"):
            if not value:
                return None
            if isinstance(value, list):
                if not value:
                    return None
                display_value = ", ".join(str(v) for v in value[:5])
            else:
                display_value = str(value)
            return {
                "label": fact_label_map.get(key, key),
                "value": display_value,
                "icon": fact_icon_map.get(key, "Info"),
                "source": source,
            }

        # ---------------------------------------------------------------
        # Phase 1: Crawl website
        # ---------------------------------------------------------------
        yield sse_event("stage", {"label": "Reading website...", "phase": "site", "url": url})

        crawl_result = None
        crawl_error = None
        start_time = time.monotonic()

        try:
            crawl_result = await asyncio.to_thread(
                asyncio.run, _company_intel.crawl_company(url)
            )
        except Exception as e:
            crawl_error = str(e)

        elapsed = time.monotonic() - start_time
        if elapsed > 30:
            yield sse_event("timeout", {"message": "Still working... some sites take longer."})

        if crawl_error or not crawl_result or not crawl_result.get("success"):
            error_msg = crawl_error or "Could not crawl this site. It may be blocking automated access."
            yield sse_event("error", {
                "message": "We couldn't connect to this site.",
                "detail": error_msg,
            })
            return

        # Emit discovered pages
        raw_pages = crawl_result.get("raw_pages", {})
        for page_path, _text in raw_pages.items():
            page_url = url.rstrip("/") + (page_path if page_path != "/" else "")
            yield sse_event("page", {"url": page_url, "title": page_path or "Homepage"})
            await asyncio.sleep(0.03)

        # ---------------------------------------------------------------
        # Phase 2: Extract intelligence from site content
        # ---------------------------------------------------------------
        yield sse_event("stage", {"label": "Extracting company signals...", "phase": "extract", "url": url})

        raw_text = "\n\n".join(raw_pages.values())
        intelligence = None
        try:
            intelligence = await asyncio.to_thread(
                _company_intel.structure_intelligence, raw_text, "website-crawl"
            )
        except Exception as e:
            yield sse_event("error", {
                "message": "Failed to extract intelligence from the site.",
                "detail": str(e),
            })
            return

        # Stream site-extracted facts immediately
        fact_count = 0
        site_keys = ["company_name", "tagline", "what_they_do", "industries",
                     "products", "target_customers", "competitors",
                     "pricing_model", "key_differentiators"]
        for key in site_keys:
            fact_data = _format_fact(key, intelligence.get(key), source="site")
            if fact_data:
                yield sse_event("fact", fact_data)
                fact_count += 1
                await asyncio.sleep(0.06)

        # ---------------------------------------------------------------
        # Phase 3: Web research enrichment
        # ---------------------------------------------------------------
        company_name = intelligence.get("company_name", "")
        # Pass source URL so enrichment can probe deep company pages
        intelligence["_source_url"] = url
        if company_name:
            yield sse_event("stage", {"label": "Deep research — searching web, probing team pages, news...", "phase": "research", "url": url})

            try:
                enriched = await asyncio.to_thread(
                    _company_intel.enrich_with_web_research, company_name, intelligence
                )

                # Stream only the NEW enrichment facts (not already shown from site)
                enrichment_keys = ["employees", "headquarters",
                                   "funding"]
                for key in enrichment_keys:
                    fact_data = _format_fact(key, enriched.get(key), source="research")
                    if fact_data:
                        yield sse_event("fact", fact_data)
                        fact_count += 1
                        await asyncio.sleep(0.06)

                # Stream key_people as individual contact facts
                for person in enriched.get("key_people", []):
                    if isinstance(person, dict):
                        value = "%s — %s" % (person.get("name", ""), person.get("title", ""))
                        if person.get("linkedin"):
                            value += " · %s" % person["linkedin"]
                        fact_data = {"label": "Key Person", "value": value, "icon": "Users", "source": "research"}
                    else:
                        # Backward compat: string format "Jane Doe, CEO"
                        fact_data = {"label": "Key Person", "value": str(person), "icon": "Users", "source": "research"}
                    yield sse_event("fact", fact_data)
                    fact_count += 1
                    await asyncio.sleep(0.06)

                # Stream tech_stack as single fact
                tech_stack = enriched.get("tech_stack")
                if tech_stack and isinstance(tech_stack, list) and len(tech_stack) > 0:
                    fact_data = {"label": "Tech Stack", "value": ", ".join(str(t) for t in tech_stack), "icon": "Code", "source": "research"}
                    yield sse_event("fact", fact_data)
                    fact_count += 1
                    await asyncio.sleep(0.06)

                # Stream social_accounts as single fact
                social = enriched.get("social_accounts")
                if social and isinstance(social, dict):
                    social_parts = ["%s: %s" % (k, v) for k, v in social.items() if v]
                    if social_parts:
                        fact_data = {"label": "Social", "value": ", ".join(social_parts), "icon": "Share2", "source": "research"}
                        yield sse_event("fact", fact_data)
                        fact_count += 1
                        await asyncio.sleep(0.06)

                # Stream recent_news and recent_press as individual facts
                news_items = enriched.get("recent_news", []) + enriched.get("recent_press", [])
                for item in news_items:
                    if isinstance(item, dict):
                        value = item.get("title", "")
                        if item.get("date"):
                            value += " (%s)" % item["date"]
                    else:
                        value = str(item)
                    if value:
                        fact_data = {"label": "Recent News", "value": value, "icon": "Newspaper", "source": "research"}
                        yield sse_event("fact", fact_data)
                        fact_count += 1
                        await asyncio.sleep(0.06)

                # Also stream competitors if enrichment added new ones
                site_competitors = intelligence.get("competitors", [])
                enriched_competitors = enriched.get("competitors", [])
                if isinstance(enriched_competitors, list) and len(enriched_competitors) > len(site_competitors or []):
                    # Only show if we actually added new competitors beyond what site had
                    new_comps = enriched_competitors[len(site_competitors or []):]
                    if new_comps:
                        fact_data = _format_fact("competitors", new_comps, source="research")
                        if fact_data:
                            fact_data["label"] = "More Competitors"
                            yield sse_event("fact", fact_data)
                            fact_count += 1
                            await asyncio.sleep(0.06)

                # Use enriched intelligence for the profile
                intelligence = enriched

            except Exception as e:
                # Enrichment failure is non-blocking -- log and continue with site data
                logger.warning("Web research enrichment failed: %s", e)

        # ---------------------------------------------------------------
        # Phase 4: Build profile
        # ---------------------------------------------------------------
        yield sse_event("stage", {"label": "Building your profile...", "phase": "profile", "url": url})

        # Emit full profile
        yield sse_event("profile", intelligence)

        # Store in onboarding session
        ob_session_id = secrets.token_urlsafe(16)
        _onboarding_sessions[ob_session_id] = {
            "company_name": company_name,
            "company_url": url,
            "intelligence": intelligence,
            "pages_crawled": crawl_result.get("pages_crawled", 0),
        }

        # Write to context store
        try:
            _company_intel.write_company_intelligence(intelligence, agent_id="web")
        except Exception as e:
            logger.warning("Failed to write company intelligence: %s", e)

        # Done
        yield sse_event("done", {
            "status": "complete",
            "session_id": ob_session_id,
            "fact_count": fact_count,
        })

    return StreamingResponse(_generate(), media_type="text/event-stream")


@app.post("/onboarding/upload", response_class=HTMLResponse)
def onboarding_upload(request: Request, file: UploadFile = File(...)):
    """Tier 2: Upload a document for company intelligence extraction.

    Uses sync def (consistent with all other routes).
    """
    if _company_intel is None:
        return HTMLResponse(
            '<div class="card error-card"><p>Company intelligence module not available.</p></div>'
        )

    try:
        content_bytes = file.file.read()

        # Detect mimetype from content type or filename
        mimetype = file.content_type or "application/octet-stream"

        # Extract text from document
        extracted_text = _company_intel.extract_from_document(content_bytes, mimetype)

        if not extracted_text.strip():
            return templates.TemplateResponse(
                "onboarding_result.html",
                _template_context(
                    request,
                    error="No text could be extracted from the uploaded file.",
                ),
            )

        # Structure the intelligence
        intelligence = _company_intel.structure_intelligence(
            extracted_text, "uploaded-document"
        )

        # Write to context store
        write_results = _company_intel.write_company_intelligence(
            intelligence, agent_id="web"
        )

        # Build attribution data
        attribution = _build_attribution(write_results)

        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                intelligence=intelligence,
                attribution=attribution,
                source="Uploaded document: %s" % (file.filename or "unknown"),
            ),
        )

    except ValueError as e:
        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                error="Unsupported file type: %s" % str(e),
            ),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                error="Error processing upload: %s" % str(e),
            ),
        )


@app.get("/onboarding/guided", response_class=HTMLResponse)
def onboarding_guided_form(request: Request):
    """Tier 3: Show guided questions form (no auth required)."""
    if _company_intel is None:
        return templates.TemplateResponse(
            "onboarding.html",
            _template_context(request, error="Company intelligence module not available."),
        )

    questions = _company_intel.build_guided_questions()
    return templates.TemplateResponse(
        "onboarding.html",
        _template_context(request, questions=questions, show_guided=True),
    )


@app.post("/onboarding/guided", response_class=HTMLResponse)
async def onboarding_guided_submit(request: Request):
    """Tier 3: Process guided question answers.

    Uses async def to access request.form() (an awaitable). The actual
    blocking work (write_company_intelligence) is minimal and runs inline.
    """
    if _company_intel is None:
        return HTMLResponse(
            '<div class="card error-card"><p>Company intelligence module not available.</p></div>'
        )

    try:
        # Read form data (must await in async route)
        form_data = await request.form()

        # Collect answers keyed by question ID
        questions = _company_intel.build_guided_questions()
        answers = {}
        for q in questions:
            val = form_data.get(q["id"], "")
            if val:
                answers[q["id"]] = val

        if not answers:
            return templates.TemplateResponse(
                "onboarding_result.html",
                _template_context(
                    request,
                    error="Please answer at least one question.",
                ),
            )

        # Structure from answers (no LLM call needed)
        intelligence = _company_intel.structure_from_answers(answers)

        # Write to context store
        write_results = _company_intel.write_company_intelligence(
            intelligence, agent_id="web"
        )

        # Build attribution data
        attribution = _build_attribution(write_results)

        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                intelligence=intelligence,
                attribution=attribution,
                source="Guided questions",
            ),
        )

    except Exception as e:
        return templates.TemplateResponse(
            "onboarding_result.html",
            _template_context(
                request,
                error="Error processing answers: %s" % str(e),
            ),
        )


# ---------------------------------------------------------------------------
# Onboarding flow: work picker and per-type input
# ---------------------------------------------------------------------------


@app.get("/onboarding/work-picker", response_class=HTMLResponse)
def onboarding_work_picker(request: Request, session: str = ""):
    """Work type selection page. Shows 6 work types with availability status.

    Available skills (in ENGINE_REGISTRY) are clickable; unavailable show
    'Coming Soon' badge. Requires session param from crawl step.
    """
    # Load onboarding session data
    ob_data = _onboarding_sessions.get(session, {})
    company_name = ob_data.get("company_name", "")

    # Build available_skills set from ENGINE_REGISTRY
    available_skills = set(_ENGINE_REGISTRY.keys())

    return templates.TemplateResponse(
        "onboarding_work_picker.html",
        _template_context(
            request,
            session_id=session,
            company_name=company_name,
            available_skills=available_skills,
        ),
    )


@app.get("/onboarding/input/{work_type}", response_class=HTMLResponse)
def onboarding_input(request: Request, work_type: str, session: str = ""):
    """Per-work-type input form. Pre-fills data from crawl session.

    Guard: returns 404 if the skill for this work type is not in
    ENGINE_REGISTRY (prevents submitting a form for an unavailable skill).
    """
    if work_type not in ONBOARDING_WORK_TYPES:
        raise HTTPException(status_code=404, detail="Unknown work type: %s" % work_type)

    wt = ONBOARDING_WORK_TYPES[work_type]
    skill_name = wt["skill"]

    # Guard: check ENGINE_REGISTRY
    if skill_name not in _ENGINE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail="This work type is coming soon. %s is not yet available." % wt["label"],
        )

    # Load session data for pre-fill
    ob_data = _onboarding_sessions.get(session, {})
    company_name = ob_data.get("company_name", "")

    return templates.TemplateResponse(
        "onboarding_skill_input.html",
        _template_context(
            request,
            work_type=work_type,
            work_label=wt["label"],
            skill_name=skill_name,
            session_id=session,
            company_name=company_name,
        ),
    )


@app.get("/skills", response_class=HTMLResponse)
def skills(request: Request):
    """Skills page (requires auth). Lists available skills from ENGINE_REGISTRY."""
    user = require_auth(request)
    skill_list = _build_skill_list()
    ctx = _page_context(request, active_page="skills", skills=skill_list)
    tpl = "partials/skills_content.html" if _is_htmx(request) else "skills.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/companies", response_class=HTMLResponse)
def companies(request: Request):
    """Companies page (requires auth). Lists companies from context store."""
    user = require_auth(request)
    companies_list = []
    try:
        if _context_utils is not None:
            raw = _context_utils.read_context("company-core.md", "web-app")
            if raw:
                # Parse entries from company-core.md
                lines = raw.strip().split("\n")
                seen = set()
                current_name = ""
                current_date = ""
                for line in lines:
                    line = line.strip()
                    # Entry header: [date | source: xxx | detail]
                    if line.startswith("[") and "|" in line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            current_date = parts[0].strip(" [")
                            detail = parts[2].split("]")[0].strip()
                            if detail and detail not in seen:
                                seen.add(detail)
                                current_name = detail
                                companies_list.append({
                                    "name": detail,
                                    "date": current_date,
                                    "source": "context-store",
                                })
    except Exception as e:
        logger.warning("Failed to read companies: %s", e)

    ctx = _page_context(request, active_page="companies", companies=companies_list)
    tpl = "partials/companies_content.html" if _is_htmx(request) else "companies.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/integrations", response_class=HTMLResponse)
def integrations(request: Request):
    """Integration status page (requires auth).

    Shows all integrations with enabled/disabled status, last run time,
    error count, toggle controls, and a cost dashboard.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    # Get integration settings (enabled/disabled per integration)
    settings = {}
    if _integration_framework is not None:
        try:
            settings = _integration_framework.get_integration_settings(user_id)
        except Exception as e:
            logger.warning("Failed to get integration settings: %s", e)

    # Get watcher status from IntegrationManager (if running)
    watcher_status = {}

    # Get cost summary
    cost_summary = {}
    if _integration_framework is not None:
        try:
            cost_summary = _integration_framework.get_cost_summary(user_id)
        except Exception as e:
            logger.warning("Failed to get cost summary: %s", e)

    ctx = _page_context(
        request,
        active_page="integrations",
        settings=settings,
        watcher_status=watcher_status,
        cost_summary=cost_summary,
    )
    tpl = "partials/integrations_content.html" if _is_htmx(request) else "integrations.html"
    return templates.TemplateResponse(tpl, ctx)


@app.post("/api/integrations/{name}/toggle")
def toggle_integration_api(request: Request, name: str):
    """Toggle an integration on/off for the current user.

    Args:
        name: Integration key (e.g., 'calendar', 'email').

    Returns:
        JSON with new enabled status.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _integration_framework is None:
        raise HTTPException(status_code=503, detail="Integration framework not available")

    try:
        current = _integration_framework.is_integration_enabled(user_id, name)
        _integration_framework.toggle_integration(user_id, name, not current)
        return JSONResponse(content={
            "integration": name,
            "enabled": not current,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/export", response_class=HTMLResponse)
def export(request: Request):
    """Export page (requires auth).

    Shows available export formats with file/entry counts and estimated size.
    """
    user = require_auth(request)

    file_count = 0
    total_entries = 0
    estimated_size = 0

    if _context_utils is not None:
        root = _context_utils.CONTEXT_ROOT
        try:
            if root.is_dir():
                for p in sorted(root.iterdir()):
                    if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                        file_count += 1
                        try:
                            estimated_size += p.stat().st_size
                        except OSError:
                            pass
                        try:
                            raw = _context_utils.read_context(p.name, agent_id="web")
                            entries = _context_utils.parse_context_file(raw)
                            total_entries += len(entries)
                        except Exception:
                            pass
        except (PermissionError, OSError):
            pass

    # Format size for display
    if estimated_size < 1024:
        size_display = "%d B" % estimated_size
    elif estimated_size < 1024 * 1024:
        size_display = "%.1f KB" % (estimated_size / 1024)
    else:
        size_display = "%.1f MB" % (estimated_size / (1024 * 1024))

    ctx = _page_context(
        request,
        active_page="export",
        file_count=file_count,
        total_entries=total_entries,
        estimated_size=size_display,
    )
    tpl = "partials/export_content.html" if _is_htmx(request) else "export.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/export/markdown")
def export_markdown(request: Request):
    """Download entire context store as a ZIP of markdown files.

    Excludes system files (prefixed with _). Returns ZIP with
    Content-Disposition header containing current date.
    """
    require_auth(request)

    buf = io.BytesIO()
    date_str = datetime.now().strftime("%Y-%m-%d")

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        file_count = 0
        if _context_utils is not None:
            root = _context_utils.CONTEXT_ROOT
            try:
                if root.is_dir():
                    for p in sorted(root.iterdir()):
                        if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                            try:
                                zf.writestr(p.name, p.read_text(encoding="utf-8"))
                                file_count += 1
                            except Exception:
                                pass
            except (PermissionError, OSError):
                pass

        if file_count == 0:
            zf.writestr(
                "README.txt",
                "Flywheel Export - %s\n\n"
                "No context data found. Your context store is empty.\n"
                "Use the onboarding flow to add your first data.\n" % date_str,
            )

    buf.seek(0)
    filename = "flywheel-export-%s.zip" % date_str
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=%s" % filename},
    )


@app.get("/export/json")
def export_json(request: Request):
    """Download entire context store as structured JSON.

    Each file becomes a key with parsed entries. Includes _metadata
    with export timestamp, file count, and total entries.
    Excludes system files (prefixed with _).
    """
    require_auth(request)

    date_str = datetime.now().strftime("%Y-%m-%d")
    result = {}
    total_entries = 0
    file_count = 0

    if _context_utils is not None:
        root = _context_utils.CONTEXT_ROOT
        try:
            if root.is_dir():
                for p in sorted(root.iterdir()):
                    if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                        try:
                            raw = _context_utils.read_context(p.name, agent_id="web")
                            entries = _context_utils.parse_context_file(raw)
                            file_count += 1
                            entry_dicts = []
                            for e in entries:
                                entry_dicts.append({
                                    "date": e.date.strftime("%Y-%m-%d"),
                                    "source": e.source,
                                    "detail": e.detail,
                                    "confidence": e.confidence,
                                    "evidence": e.evidence_count,
                                    "content": e.content,
                                })
                            total_entries += len(entry_dicts)
                            result[p.name] = entry_dicts
                        except Exception:
                            pass
        except (PermissionError, OSError):
            pass

    result["_metadata"] = {
        "exported_at": datetime.now().isoformat(),
        "file_count": file_count,
        "total_entries": total_entries,
        "version": "flywheel-1.0",
    }

    import json as json_mod
    json_bytes = json_mod.dumps(result, indent=2, default=str).encode("utf-8")
    buf = io.BytesIO(json_bytes)
    filename = "flywheel-export-%s.json" % date_str
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=%s" % filename},
    )


# ---------------------------------------------------------------------------
# API routes (JSON endpoints for HTMX)
# ---------------------------------------------------------------------------

@app.get("/api/health")
def api_health():
    """Return health dashboard as JSON."""
    return JSONResponse(content=_get_health_dashboard())


@app.get("/api/health/summary", response_class=HTMLResponse)
def api_health_summary(request: Request):
    """Return HTML fragment for HTMX partial swap."""
    health = _get_health_dashboard()
    return templates.TemplateResponse(
        "components/health_summary.html",
        _template_context(request, health=health),
    )


@app.get("/api/skills")
def api_skills():
    """Return skill list as JSON."""
    return JSONResponse(content=_build_skill_list())


@app.get("/api/search")
def api_search(q: str = ""):
    """Search across skills, work items, and actions.

    Combines results from ENGINE_REGISTRY, work_items, and static actions.
    If query is empty, returns all skills + all actions (no work items).
    """
    query = q.strip().lower()
    results = []

    # 1. Skills from ENGINE_REGISTRY
    seen_skills = set()
    for skill_name in sorted(_ENGINE_REGISTRY):
        canonical = skill_name.replace("ctx-", "")
        if canonical in seen_skills:
            continue
        seen_skills.add(canonical)
        display = canonical.replace("-", " ").title()
        if not query or query in display.lower() or query in canonical.lower():
            results.append({
                "type": "skill",
                "label": display,
                "url": f"/skills/{canonical}/run",
                "icon": "play",
            })

    # 2. Work items (only when query is non-empty to avoid noise)
    if query and _work_items is not None:
        try:
            items = _work_items.list_work_items("default")
            for item in items:
                title = item.get("title", "")
                if query in title.lower():
                    item_id = item.get("id", "")
                    results.append({
                        "type": "work",
                        "label": title,
                        "url": f"/agenda#{item_id}",
                        "icon": "calendar",
                    })
        except Exception:
            pass

    # 3. Static actions
    static_actions = [
        {"type": "action", "label": "Add Meeting", "url": "/agenda?action=add-meeting", "icon": "lightning"},
        {"type": "action", "label": "Upload Document", "url": "/onboarding", "icon": "lightning"},
        {"type": "action", "label": "Export Data", "url": "/export", "icon": "lightning"},
        {"type": "action", "label": "View Dashboard", "url": "/dashboard", "icon": "lightning"},
    ]
    for action in static_actions:
        if not query or query in action["label"].lower():
            results.append(action)

    return JSONResponse(content=results)


@app.get("/api/context/files")
def api_context_files():
    """Return list of context files with entry counts as JSON.

    Lists all .md files in CONTEXT_ROOT (excluding _ prefixed system files).
    """
    if _context_utils is None:
        return JSONResponse(content=[])

    root = _context_utils.CONTEXT_ROOT
    result = []
    try:
        if not root.is_dir():
            return JSONResponse(content=[])
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                entry_count = 0
                try:
                    raw = _context_utils.read_context(p.name, agent_id="web")
                    entries = _context_utils.parse_context_file(raw)
                    entry_count = len(entries)
                except Exception:
                    pass
                # Last modified from file stat
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                except Exception:
                    mtime = None
                result.append({
                    "name": p.name,
                    "entry_count": entry_count,
                    "last_modified": mtime,
                })
    except (PermissionError, OSError):
        pass
    return JSONResponse(content=result)


@app.get("/api/context/{filename}")
def api_context_file(filename: str):
    """Return entries of a specific context file as JSON.

    Validates filename to prevent path traversal.
    """
    # Path traversal prevention
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if _context_utils is None:
        raise HTTPException(status_code=404, detail="Context store not available")

    try:
        raw = _context_utils.read_context(filename, agent_id="web")
        if not raw:
            raise HTTPException(status_code=404, detail="File not found")
        entries = _context_utils.parse_context_file(raw)
        entry_dicts = []
        for e in entries:
            entry_dicts.append({
                "date": e.date.strftime("%Y-%m-%d"),
                "source": e.source,
                "detail": e.detail,
                "confidence": e.confidence,
                "evidence": e.evidence_count,
                "content": e.content,
            })
        return JSONResponse(content=entry_dicts)
    except HTTPException:
        raise
    except ValueError as ve:
        # Path traversal blocked by context_utils._enforce_containment
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error reading file: %s" % str(exc))


# ---------------------------------------------------------------------------
# Schedule Routes
# ---------------------------------------------------------------------------


@app.post("/api/schedules")
async def create_schedule_route(request: Request):
    """Create a new recurring schedule."""
    user = require_auth(request)
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not available")

    body = await request.json()
    skill_name = body.get("skill_name", "")
    frequency = body.get("frequency", "daily")
    if not skill_name:
        raise HTTPException(400, "skill_name is required")

    kwargs = {}
    if "time" in body:
        kwargs["time"] = body["time"]
    if "day_of_week" in body and body["day_of_week"] is not None:
        try:
            kwargs["day_of_week"] = int(body["day_of_week"])
        except (ValueError, TypeError):
            pass
    if "description" in body:
        kwargs["description"] = body["description"]
    if "params" in body:
        kwargs["params"] = body["params"]

    user_id = user.get("user_id", "")
    schedule = _scheduler.create_schedule(user_id, skill_name, frequency, **kwargs)

    # If request is HTMX, return the updated schedules section
    if request.headers.get("HX-Request"):
        return _render_schedules_section(request, user_id)

    return JSONResponse(schedule.model_dump(), status_code=201)


@app.get("/api/schedules")
def list_schedules_route(request: Request):
    """List user's schedules."""
    user = require_auth(request)
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not available")

    user_id = user.get("user_id", "")
    schedules = _scheduler.list_schedules(user_id)
    return JSONResponse([s.model_dump() for s in schedules])


@app.patch("/api/schedules/{schedule_id}")
async def update_schedule_route(request: Request, schedule_id: str):
    """Update a schedule (toggle enabled, change time, etc.)."""
    user = require_auth(request)
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not available")

    body = await request.json()
    user_id = user.get("user_id", "")

    # Convert string booleans from HTMX
    if "enabled" in body:
        if isinstance(body["enabled"], str):
            body["enabled"] = body["enabled"].lower() == "true"

    updated = _scheduler.update_schedule(user_id, schedule_id, **body)
    if updated is None:
        raise HTTPException(404, "Schedule not found")

    if request.headers.get("HX-Request"):
        return _render_schedules_section(request, user_id)

    return JSONResponse(updated.model_dump())


@app.delete("/api/schedules/{schedule_id}")
def delete_schedule_route(request: Request, schedule_id: str):
    """Delete a schedule."""
    user = require_auth(request)
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not available")

    user_id = user.get("user_id", "")
    deleted = _scheduler.delete_schedule(user_id, schedule_id)
    if not deleted:
        raise HTTPException(404, "Schedule not found")

    # Return empty content for HTMX swap (removes the card)
    if request.headers.get("HX-Request"):
        return HTMLResponse("")

    return JSONResponse(None, status_code=204)


@app.get("/api/schedules/suggestions")
def schedule_suggestions_route(request: Request):
    """Return suggested schedules filtered by what user already has."""
    user = require_auth(request)
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not available")

    user_id = user.get("user_id", "")
    existing = _scheduler.list_schedules(user_id)
    existing_skills = {s.skill_name for s in existing}
    suggestions = [
        s for s in _scheduler.SUGGESTED_SCHEDULES
        if s["skill_name"] not in existing_skills
    ]
    return JSONResponse(suggestions)


def _render_schedules_section(request: Request, user_id: str):
    """Helper to render the schedules section as HTML for HTMX responses."""
    user_schedules = []
    suggested_schedules = []
    available_skills = []

    if _scheduler is not None:
        try:
            user_schedules = _scheduler.list_schedules(user_id)
        except Exception:
            pass
        existing_skills = {s.skill_name for s in user_schedules}
        suggested_schedules = [
            s for s in _scheduler.SUGGESTED_SCHEDULES
            if s["skill_name"] not in existing_skills
        ]

    if _ENGINE_REGISTRY:
        available_skills = sorted(set(
            k.replace("ctx-", "") for k in _ENGINE_REGISTRY.keys()
        ))

    return templates.TemplateResponse(
        "components/schedules.html",
        _template_context(
            request,
            schedules=user_schedules,
            suggested_schedules=suggested_schedules,
            available_skills=available_skills,
        ),
    )


# ---------------------------------------------------------------------------
# Work Item Routes
# ---------------------------------------------------------------------------


@app.post("/api/work-items")
async def create_work_item_route(request: Request):
    """Create a new work item.

    Accepts JSON body with: type, title, skill_name (optional), description,
    due_date, skill_params. If skill_name not provided, derives from type.

    Uses async def to await request.json().
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    item_type = body.get("type", "custom")
    title = body.get("title")
    if not title:
        return JSONResponse(
            status_code=400,
            content={"error": "title is required"},
        )

    # Derive skill_name from type if not provided
    skill_name = body.get("skill_name")
    if not skill_name:
        skill_name = _work_items.WORK_TYPE_SKILLS.get(item_type) or ""

    kwargs = {}
    if body.get("description"):
        kwargs["description"] = body["description"]
    if body.get("due_date"):
        kwargs["due_date"] = body["due_date"]
    if body.get("skill_params"):
        kwargs["skill_params"] = body["skill_params"]

    item = _work_items.create_work_item(
        user_id=user_id,
        type=item_type,
        title=title,
        skill_name=skill_name,
        **kwargs,
    )
    return JSONResponse(status_code=201, content=item.model_dump())


@app.get("/api/work-items")
def list_work_items_route(request: Request, status: Optional[str] = None, type: Optional[str] = None):
    """List work items with optional status and type filters."""
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    items = _work_items.list_work_items(user_id, status=status, type=type)
    return JSONResponse(content=[item.model_dump() for item in items])


@app.get("/api/work-items/{item_id}")
def get_work_item_route(request: Request, item_id: str):
    """Retrieve a single work item by ID."""
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    item = _work_items.get_work_item(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    return JSONResponse(content=item.model_dump())


@app.patch("/api/work-items/{item_id}")
async def update_work_item_route(request: Request, item_id: str):
    """Update fields on a work item.

    Accepts JSON body with fields to update. If 'status' is included,
    uses transition_status for validation.

    Uses async def to await request.json().
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # If status is being changed, use transition_status for validation
    new_status = body.pop("status", None)
    if new_status:
        try:
            item = _work_items.transition_status(user_id, item_id, new_status)
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"error": str(e)},
            )
        if item is None:
            raise HTTPException(status_code=404, detail="Work item not found")
        # Apply remaining updates if any
        if body:
            item = _work_items.update_work_item(user_id, item_id, **body)
    else:
        item = _work_items.update_work_item(user_id, item_id, **body)

    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    return JSONResponse(content=item.model_dump())


@app.delete("/api/work-items/{item_id}")
def delete_work_item_route(request: Request, item_id: str):
    """Delete a work item by ID."""
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    deleted = _work_items.delete_work_item(user_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Work item not found")

    return JSONResponse(status_code=200, content={"deleted": True})


@app.post("/api/work-items/{item_id}/run")
async def run_work_item_route(request: Request, item_id: str):
    """Trigger skill execution for a work item.

    Updates status to 'preparing', executes the skill, then updates
    status to 'ready' with skill_output_id on completion.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    item = _work_items.get_work_item(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Transition to preparing
    try:
        _work_items.transition_status(user_id, item_id, "preparing")
    except ValueError:
        # If transition fails (e.g., item already past preparing), continue anyway
        pass

    # Execute skill if gateway available
    if _execution_gateway is None:
        # No execution gateway -- mark as ready with no output
        _work_items.update_work_item(user_id, item_id, status="ready")
        return JSONResponse(content={
            "status": "completed",
            "message": "Execution gateway not available. Item marked as ready.",
            "item": _work_items.get_work_item(user_id, item_id).model_dump(),
        })

    try:
        # Build input text from item params
        input_text = item.skill_params.get("input_text", item.title)

        result = await asyncio.to_thread(
            _execution_gateway.execute_skill,
            item.skill_name,
            input_text,
            user_id,
        )

        # Store result and update status
        output_id = result.get("output_id", str(uuid.uuid4())) if isinstance(result, dict) else str(uuid.uuid4())
        _work_items.update_work_item(
            user_id, item_id,
            skill_output_id=output_id,
            status="ready",
        )

        updated_item = _work_items.get_work_item(user_id, item_id)
        return JSONResponse(content={
            "status": "completed",
            "item": updated_item.model_dump() if updated_item else {},
        })

    except Exception as e:
        # On failure, keep item in preparing state so user can retry
        return JSONResponse(
            status_code=500,
            content={"error": "Skill execution failed: %s" % str(e)},
        )


# ---------------------------------------------------------------------------
# Post-Action Capture Routes
# ---------------------------------------------------------------------------


@app.get("/api/work-items/{item_id}/capture", response_class=HTMLResponse)
def get_capture_form(request: Request, item_id: str):
    """Return the capture form partial for a work item (HTMX loading).

    Form type depends on work item type: meeting, outreach, or generic.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    item = _work_items.get_work_item(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    return templates.TemplateResponse(
        "components/capture_form.html",
        {
            "request": request,
            "item_id": item_id,
            "item_type": item.type,
            "captured": item.captured,
            "entries_created": 0,
            "files_updated": [],
        },
    )


@app.post("/api/work-items/{item_id}/capture")
async def submit_capture(request: Request, item_id: str):
    """Process captured data and write to context store.

    For meetings: processes notes and writes insights to context store.
    For outreach: writes outcome to context store.
    For all: updates work item with captured=True, transitions to done.

    Uses async def to read form data.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _work_items is None:
        raise HTTPException(status_code=503, detail="Work items module not available")

    item = _work_items.get_work_item(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    try:
        form = await request.form()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form data")

    notes = form.get("notes", "")
    outcome = form.get("outcome", "")

    entries_created = 0
    files_updated = []

    # Write to context store based on item type
    if _context_utils is not None and (notes or outcome):
        try:
            from datetime import date
            today = date.today().isoformat()

            if item.type == "meeting":
                # Write meeting notes to context store
                content_lines = []
                if notes:
                    content_lines.append("Meeting notes: %s" % notes.strip()[:2000])
                if outcome:
                    content_lines.append("Outcome: %s" % outcome)

                entry = {
                    "content": content_lines,
                    "detail": "meeting-capture: %s" % item.title[:80],
                    "confidence": "medium",
                    "source": "web-capture",
                }
                try:
                    _context_utils.append_entry(
                        file="contacts.md",
                        entry=entry,
                        source="web-capture",
                        agent_id=user_id,
                    )
                    entries_created += 1
                    files_updated.append("contacts.md")
                except Exception as e:
                    logger.warning("Failed to write meeting capture to contacts.md: %s", e)

            elif item.type == "outreach":
                # Write outreach outcome to context store
                content_lines = ["Outreach outcome: %s" % outcome]
                if notes:
                    content_lines.append("Notes: %s" % notes.strip()[:2000])

                entry = {
                    "content": content_lines,
                    "detail": "outreach-capture: %s" % item.title[:80],
                    "confidence": "low",
                    "source": "web-capture",
                }
                try:
                    _context_utils.append_entry(
                        file="outreach-leads.md",
                        entry=entry,
                        source="web-capture",
                        agent_id=user_id,
                    )
                    entries_created += 1
                    files_updated.append("outreach-leads.md")
                except Exception as e:
                    logger.warning("Failed to write outreach capture: %s", e)

            else:
                # Generic capture
                if notes:
                    entry = {
                        "content": ["Note: %s" % notes.strip()[:2000]],
                        "detail": "capture: %s" % item.title[:80],
                        "confidence": "low",
                        "source": "web-capture",
                    }
                    try:
                        _context_utils.append_entry(
                            file="contacts.md",
                            entry=entry,
                            source="web-capture",
                            agent_id=user_id,
                        )
                        entries_created += 1
                        files_updated.append("contacts.md")
                    except Exception as e:
                        logger.warning("Failed to write generic capture: %s", e)

        except Exception as e:
            logger.error("Capture context store write failed: %s", e)

    # Update work item with capture metadata
    capture_data = {
        "notes": notes,
        "outcome": outcome,
        "entries_created": entries_created,
        "files_updated": files_updated,
        "captured_at": datetime.now().isoformat(),
    }
    _work_items.update_work_item(
        user_id, item_id,
        captured=True,
        capture_data=capture_data,
    )

    # Transition to done
    try:
        _work_items.transition_status(user_id, item_id, "done")
    except ValueError:
        pass  # May already be done or in a state that cannot transition

    # Return success form partial (HTMX replaces the form)
    return templates.TemplateResponse(
        "components/capture_form.html",
        {
            "request": request,
            "item_id": item_id,
            "item_type": item.type,
            "captured": True,
            "entries_created": entries_created,
            "files_updated": files_updated,
        },
    )


# ---------------------------------------------------------------------------
# Skill Execution Routes
# ---------------------------------------------------------------------------


@app.get("/skills/{name}/run", response_class=HTMLResponse)
def skill_run_page(request: Request, name: str):
    """Render the skill execution page for a specific skill.

    Shows skill info, input form, and SSE-connected results area.
    """
    user = require_auth(request)

    # Look up skill info
    canonical = name.replace("ctx-", "")
    skill_info = None
    for skill_name in _ENGINE_REGISTRY:
        if skill_name.replace("ctx-", "") == canonical:
            skill_info = {
                "name": canonical,
                "display_name": canonical.replace("-", " ").title(),
                "description": _get_skill_description(canonical),
            }
            break

    if skill_info is None:
        raise HTTPException(status_code=404, detail="Skill not found: %s" % name)

    ctx = _page_context(request, active_page="skills", skill=skill_info)
    tpl = "partials/skill_run_content.html" if _is_htmx(request) else "skill_run.html"
    return templates.TemplateResponse(tpl, ctx)


@app.get("/api/skills/{name}/stream")
async def skill_stream(request: Request, name: str, input_text: str = ""):
    """SSE streaming endpoint for skill execution.

    Returns a StreamingResponse with SSE events for real-time progress.
    Uses async def because the SSE generator is an async generator.
    Allows unauthenticated access for onboarding flow (uses 'onboarding' as user_id).
    """
    user = get_current_user(request)
    user_id = user.get("user_id", "") if user else "onboarding"

    if _skill_runner_web is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Skill runner not available"},
        )

    # Collect additional params from query string
    params = {}
    for key, value in request.query_params.items():
        if key not in ("input_text",):
            params[key] = value

    generator = _skill_runner_web.skill_sse_generator(
        skill_name=name,
        input_text=input_text,
        user_id=user_id,
        params=params,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/outputs/{run_id}")
def get_output(request: Request, run_id: str):
    """Load a stored skill output by run_id. Returns JSON."""
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _skill_runner_web is None:
        raise HTTPException(status_code=503, detail="Skill runner not available")

    try:
        result = _skill_runner_web.load_result(user_id, run_id)
        return JSONResponse(content=result)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Output not found: %s" % run_id)


@app.get("/api/outputs/{run_id}/rendered", response_class=HTMLResponse)
def get_output_rendered(request: Request, run_id: str):
    """Load a stored skill output and return rendered HTML fragment.

    Used by output_viewer.html for lazy-loading rendered outputs via hx-get.
    Falls back to raw output in <pre> tags if output_renderer unavailable.
    """
    user = require_auth(request)
    user_id = user.get("user_id", "")

    if _skill_runner_web is None:
        raise HTTPException(status_code=503, detail="Skill runner not available")

    try:
        result = _skill_runner_web.load_result(user_id, run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Output not found: %s" % run_id)

    if _output_renderer is not None:
        try:
            templates_dir = os.path.join(_DIR, "templates")
            rendered = _output_renderer.render_output(
                result.get("skill_name", ""),
                result.get("output", ""),
                result.get("context_attribution", {}),
                templates_dir,
            )
            return HTMLResponse(content=rendered)
        except Exception as e:
            logger.warning("render_output failed for %s: %s", run_id, e)

    # Fallback: raw output in <pre> tags
    raw = result.get("output", "")
    escaped = (
        raw.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return HTMLResponse(content=f"<pre>{escaped}</pre>")


@app.get("/api/skills")
def list_skills(request: Request):
    """List available skills as JSON.

    Deduplicates ctx- prefixed names (same as 11A.5-02 pattern).
    Returns list of {name, display_name, engine_type, has_engine}.
    """
    user = require_auth(request)
    seen = set()
    skills = []

    for skill_name, module_name in sorted(_ENGINE_REGISTRY.items()):
        canonical = skill_name.replace("ctx-", "")
        if canonical in seen:
            continue
        seen.add(canonical)

        skills.append({
            "name": canonical,
            "display_name": canonical.replace("-", " ").title(),
            "engine_type": "Python Engine",
            "has_engine": True,
        })

    return JSONResponse(content=skills)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _compute_growth_data() -> list:
    """Compute entries added per day over the last 7 days.

    Returns list of dicts with day_name, date, count -- one per day,
    ordered oldest to newest.
    """
    if _context_utils is None:
        return []

    try:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = _context_utils.read_event_log(since=since)
    except Exception:
        return []

    # Count entry_appended and evidence_incremented events per day
    day_counts = defaultdict(int)
    for event in events:
        etype = event.get("event_type", "")
        if etype in ("entry_appended", "evidence_incremented"):
            ts = event.get("timestamp", "")
            if ts:
                day_key = ts[:10]  # YYYY-MM-DD
                day_counts[day_key] += 1

    # Build 7-day list
    result = []
    today = datetime.now().date()
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_name = d.strftime("%a")  # Mon, Tue, etc.
        result.append({
            "day_name": day_name,
            "date": date_str,
            "count": day_counts.get(date_str, 0),
        })

    return result


def _compute_attribution_summary() -> list:
    """Compute top knowledge sources from recent events.

    Groups events by agent_id to show which skills contributed most.
    Returns top 5 sources sorted by count descending.
    """
    if _context_utils is None:
        return []

    try:
        since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = _context_utils.read_event_log(since=since)
    except Exception:
        return []

    agent_stats = defaultdict(lambda: {"count": 0, "last_seen": ""})
    for event in events:
        etype = event.get("event_type", "")
        if etype in ("entry_appended", "evidence_incremented"):
            agent = event.get("agent_id", "unknown")
            agent_stats[agent]["count"] += 1
            ts = event.get("timestamp", "")
            if ts > agent_stats[agent]["last_seen"]:
                agent_stats[agent]["last_seen"] = ts

    # Sort by count descending, take top 5
    sorted_agents = sorted(
        agent_stats.items(), key=lambda x: x[1]["count"], reverse=True
    )[:5]

    result = []
    for agent_id, stats in sorted_agents:
        result.append({
            "source": agent_id,
            "count": stats["count"],
            "last_seen": stats["last_seen"][:10] if stats["last_seen"] else "",
        })

    return result


def _compute_file_stats() -> list:
    """Compute per-file stats for the context file listing.

    Returns list of dicts with name, entry_count, last_modified, display_name.
    """
    if _context_utils is None:
        return []

    root = _context_utils.CONTEXT_ROOT
    result = []
    try:
        if not root.is_dir():
            return []
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                entry_count = 0
                try:
                    raw = _context_utils.read_context(p.name, agent_id="web")
                    entries = _context_utils.parse_context_file(raw)
                    entry_count = len(entries)
                except Exception:
                    pass
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
                except Exception:
                    mtime = "unknown"
                display_name = p.name.replace(".md", "").replace("-", " ").title()
                result.append({
                    "name": p.name,
                    "display_name": display_name,
                    "entry_count": entry_count,
                    "last_modified": mtime,
                })
    except (PermissionError, OSError):
        pass
    return result


def _build_attribution(write_results: dict) -> list:
    """Convert write_company_intelligence results into template-friendly attribution list.

    Args:
        write_results: Dict of {filename: result_string}.

    Returns:
        List of dicts with file, status, timestamp for each written file.
    """
    attribution = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for filename, result in write_results.items():
        status = "written"
        if isinstance(result, str):
            if result.startswith("ERROR"):
                status = "error"
            elif result == "DEDUP":
                status = "duplicate (skipped)"
        attribution.append({
            "file": filename,
            "status": status,
            "timestamp": now,
        })
    return attribution


def _build_skill_list() -> list:
    """Build a list of available skills from ENGINE_REGISTRY.

    Returns:
        List of dicts with name, display_name, engine_type, module_name, description.
    """
    seen = set()
    skill_list = []

    for skill_name, module_name in sorted(_ENGINE_REGISTRY.items()):
        # Skip ctx- duplicates (show canonical name only)
        canonical = skill_name.replace("ctx-", "")
        if canonical in seen:
            continue
        seen.add(canonical)

        # Format display name: dashes to spaces, title case
        display_name = canonical.replace("-", " ").title()

        # Determine engine type
        engine_type = "Python Engine"

        # Try to get description from SKILL.md
        description = _get_skill_description(canonical)

        skill_list.append({
            "name": canonical,
            "display_name": display_name,
            "engine_type": engine_type,
            "module_name": module_name,
            "description": description,
        })

    return skill_list


def _get_skill_description(skill_name: str) -> str:
    """Try to read a skill description from its SKILL.md.

    Falls back to 'No description available' if SKILL.md not found.
    """
    if _skill_converter is None:
        return "No description available"

    try:
        spec = _skill_converter.convert_skill(skill_name)
        desc = getattr(spec, "description", "") or ""
        if desc:
            return desc
    except Exception:
        pass

    return "No description available"
