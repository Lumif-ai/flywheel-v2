"""
company_intel.py - Company intelligence engine for onboarding.

Standalone module that crawls a URL, extracts company data, and writes
structured entries to the context store. Includes Tier 2 (document upload
text extraction) and Tier 3 (guided questions) fallbacks for when crawling
fails.

Functions:
  1. crawl_company(url) - async crawl up to 5 pages
  2. extract_from_document(content_bytes, mimetype) - extract text from uploads
  3. build_guided_questions() - Tier 3 fallback question set
  4. structure_intelligence(raw_text, source_label) - LLM structuring
  5. structure_from_answers(answers) - map guided answers to intelligence dict
  6. write_company_intelligence(intelligence, agent_id) - write to context store
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import html2text
import httpx
from bs4 import BeautifulSoup

from flywheel.storage_backend import append_entry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRAWL_PAGES = ["", "/about", "/pricing", "/products", "/customers"]

ACCEPTED_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

AGENT_ID = "company-intel"

MAX_LLM_RETRIES = 2
LLM_TIMEOUT = 120  # seconds – document extraction can process 50-100K+ chars

# Intelligence output keys (shared schema across all tiers)
INTELLIGENCE_KEYS = [
    "company_name",
    "tagline",
    "what_they_do",
    "products",
    "target_customers",
    "industries",
    "competitors",
    "pricing_model",
    "key_differentiators",
]

# Keys that enrichment can add or improve
ENRICHMENT_KEYS = [
    "competitors",
    "employees",
    "headquarters",
    "key_people",
    "funding",
    "recent_news",
    "tech_stack",
    "social_accounts",
    "recent_press",
    "blog_topics",
]


# ---------------------------------------------------------------------------
# Gap-aware enrichment helper
# ---------------------------------------------------------------------------


async def _get_existing_profile_keys(
    factory,  # async_sessionmaker
    tenant_id,  # UUID
) -> set:
    """Return file_names that already have non-empty content in the tenant's profile.

    Used by gap-aware enrichment to skip researching already-populated categories.
    """
    from sqlalchemy import select, text as sa_text
    from flywheel.db.models import ContextEntry

    async with factory() as session:
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        rows = (await session.execute(
            select(ContextEntry.file_name).where(
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.source == "company-intel-onboarding",
                ContextEntry.deleted_at.is_(None),
                ContextEntry.content.isnot(None),
                ContextEntry.content != "",
            )
        )).scalars().all()
    return set(rows)


# ---------------------------------------------------------------------------
# 1. crawl_company (async)
# ---------------------------------------------------------------------------


async def crawl_company(url: str, max_pages: int = 5) -> dict:
    """Crawl up to max_pages pages from a company website.

    Attempts homepage, /about, /pricing, /products, /customers.
    Strips script/style/nav/footer tags, converts to plain text.

    Args:
        url: Base URL of the company website (e.g. "https://example.com").
        max_pages: Maximum number of pages to crawl. Defaults to 5.

    Returns:
        Dict with keys: url, pages_crawled, raw_pages, success.
    """
    result = {
        "url": url,
        "pages_crawled": 0,
        "raw_pages": {},
        "success": False,
    }

    # Normalize URL: strip trailing slash
    base_url = url.rstrip("/")

    import asyncio as _asyncio

    pages_to_crawl = CRAWL_PAGES[:max_pages]

    async def _fetch_page(client, base, path):
        """Fetch and parse a single page. Returns (path, text) or None."""
        page_url = base + path
        try:
            resp = await client.get(page_url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            meta_parts = []
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                meta_parts.append("Title: %s" % title_tag.string.strip())
            for meta in soup.find_all("meta"):
                name = meta.get("name", "") or meta.get("property", "")
                content = meta.get("content", "")
                if content and name in (
                    "description", "og:description", "og:title",
                    "og:site_name", "keywords", "author",
                    "twitter:description", "twitter:title",
                ):
                    meta_parts.append("%s: %s" % (name, content))

            for tag in soup.find_all(["script", "style", "nav", "footer"]):
                tag.decompose()

            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            converter.body_width = 0
            body_text = converter.handle(str(soup)).strip()

            text = "\n".join(meta_parts)
            if body_text:
                text = text + "\n\n" + body_text if text else body_text

            if text.strip():
                return (path or "/", text.strip())
        except (httpx.HTTPError, httpx.HTTPStatusError):
            pass
        return None

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    ) as client:
        results = await _asyncio.gather(
            *[_fetch_page(client, base_url, path) for path in pages_to_crawl]
        )
        for r in results:
            if r is not None:
                result["raw_pages"][r[0]] = r[1]
                result["pages_crawled"] += 1

    result["success"] = result["pages_crawled"] > 0
    return result


# ---------------------------------------------------------------------------
# 2. extract_from_document
# ---------------------------------------------------------------------------


def extract_from_document(content_bytes: bytes, mimetype: str) -> str:
    """Extract text from an uploaded document.

    Supports PDF, DOCX, plain text, and markdown.

    Args:
        content_bytes: Raw file bytes.
        mimetype: MIME type of the file.

    Returns:
        Extracted text string.

    Raises:
        ValueError: If mimetype is not supported.
    """
    if mimetype not in ACCEPTED_MIMETYPES:
        raise ValueError(
            "Unsupported mimetype: '%s'. Accepted: %s"
            % (mimetype, ", ".join(sorted(ACCEPTED_MIMETYPES)))
        )

    if mimetype == "application/pdf":
        import io
        import pdfplumber

        pages_text = []
        with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
        return "\n\n".join(pages_text)

    if mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        import io
        import docx

        doc = docx.Document(io.BytesIO(content_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    # text/plain or text/markdown
    return content_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# 3. build_guided_questions
# ---------------------------------------------------------------------------


def build_guided_questions() -> list:
    """Return Tier 3 fallback questions for manual company intelligence input.

    Returns:
        List of 5 question dicts, each with id, question, and context_key.
    """
    return [
        {
            "id": "company_name",
            "question": "What is the name of your company?",
            "context_key": "company_name",
        },
        {
            "id": "what_they_do",
            "question": "What does your company do? (1-2 sentences)",
            "context_key": "what_they_do",
        },
        {
            "id": "target_customers",
            "question": "Who are your target customers?",
            "context_key": "target_customers",
        },
        {
            "id": "products",
            "question": "What are your main products or services?",
            "context_key": "products",
        },
        {
            "id": "competitors",
            "question": "Who are your key competitors?",
            "context_key": "competitors",
        },
    ]


# ---------------------------------------------------------------------------
# 4. structure_intelligence
# ---------------------------------------------------------------------------


def structure_intelligence(raw_text: str, source_label: str, *, api_key: str | None = None) -> dict:
    """Use LLM to structure raw text into company intelligence dict.

    Falls back to returning raw text if anthropic SDK is unavailable.

    Args:
        raw_text: Raw crawled or uploaded text.
        source_label: Label describing the source (e.g. "website-crawl").
        api_key: Optional explicit API key. If None, reads from env.

    Returns:
        Dict with intelligence keys (company_name, tagline, etc.)
        or {"raw_text": raw_text, "structured": False} on SDK failure.
    """
    try:
        import anthropic
    except ImportError:
        return {"raw_text": raw_text, "structured": False}

    import json
    import logging
    import time

    _log = logging.getLogger(__name__)

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    system_prompt = (
        "You are extracting company intelligence from raw text. "
        "Extract ONLY information that is explicitly present in the text. "
        "Do NOT invent or assume any information. "
        "Return a JSON object with these keys:\n"
        "- company_name: string\n"
        "- tagline: string (or null)\n"
        "- what_they_do: string (1-2 sentence summary)\n"
        "- products: list of objects, each with:\n"
        "    - name: string (product name)\n"
        "    - description: string (1-2 sentence summary of the product)\n"
        "    - target_customers: list of strings (ICP specific to this product)\n"
        "    - pain_points: list of strings (problems this product solves)\n"
        "    - competitors: list of strings (direct alternatives to this product)\n"
        "    - value_proposition: string (moat/differentiator for this product)\n"
        "- target_customers: list of strings (company-wide ICP)\n"
        "- industries: list of strings\n"
        "- competitors: list of strings (company-level competitors, or empty list)\n"
        "- pricing_model: string (or null)\n"
        "- key_differentiators: list of strings\n\n"
        "Return ONLY valid JSON. No markdown fencing."
    )

    last_error = None
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            # Soft cap at 100K chars to avoid extreme token usage
            input_text = raw_text
            if len(input_text) > 100_000:
                _log.warning("structure_intelligence: input text is %d chars, capping at 100K", len(input_text))
                input_text = input_text[:100_000]

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                timeout=LLM_TIMEOUT,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Extract company intelligence from this text (source: %s):\n\n%s"
                        % (source_label, input_text),
                    }
                ],
            )

            if not message.content:
                raise ValueError("Empty response from LLM")
            # Find the first text block
            response_text = ""
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    response_text = block.text.strip()
                    break
            if not response_text:
                raise ValueError(f"No text in LLM response, blocks: {[type(b).__name__ for b in message.content]}")
            _log.info("structure_intelligence raw response length: %d chars, first 100: %s",
                      len(response_text), repr(response_text[:100]))
            # Strip markdown fencing if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                response_text = "\n".join(lines).strip()
            intelligence = json.loads(response_text)

            # Basic structural validation
            if "company_name" not in intelligence:
                raise ValueError("Missing company_name in LLM response")

            intelligence["structured"] = True
            return intelligence

        except json.JSONDecodeError as exc:
            last_error = exc
            _log.warning("structure_intelligence attempt %d/%d: JSON decode error: %s", attempt + 1, MAX_LLM_RETRIES + 1, exc)
        except anthropic.APITimeoutError as exc:
            last_error = exc
            _log.warning("structure_intelligence attempt %d/%d: timeout: %s", attempt + 1, MAX_LLM_RETRIES + 1, exc)
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                # 4xx errors won't improve with retry
                _log.error("structure_intelligence failed with client error (%d): %s", exc.status_code, exc)
                return {"raw_text": raw_text, "structured": False}
            last_error = exc
            _log.warning("structure_intelligence attempt %d/%d: server error (%d): %s", attempt + 1, MAX_LLM_RETRIES + 1, exc.status_code, exc)
        except ValueError as exc:
            last_error = exc
            _log.warning("structure_intelligence attempt %d/%d: validation error: %s", attempt + 1, MAX_LLM_RETRIES + 1, exc)
        except Exception as exc:
            _log.error("structure_intelligence failed: %s: %s", type(exc).__name__, exc)
            return {"raw_text": raw_text, "structured": False}

        # Exponential backoff before retry
        if attempt < MAX_LLM_RETRIES:
            time.sleep(2 ** attempt)

    _log.error("structure_intelligence exhausted %d retries. Last error: %s", MAX_LLM_RETRIES + 1, last_error)
    return {"raw_text": raw_text, "structured": False}


# ---------------------------------------------------------------------------
# 5. structure_from_answers
# ---------------------------------------------------------------------------


def structure_from_answers(answers: dict) -> dict:
    """Convert Tier 3 guided question answers into intelligence dict.

    Pure mapping, no LLM call needed.

    Args:
        answers: Dict keyed by question id (company_name, what_they_do, etc.)

    Returns:
        Dict with same keys as structure_intelligence output.
    """
    def _to_list(val):
        """Convert a string answer to a list by splitting on commas."""
        if isinstance(val, list):
            return val
        if isinstance(val, str) and val.strip():
            return [item.strip() for item in val.split(",") if item.strip()]
        return []

    return {
        "company_name": answers.get("company_name", ""),
        "tagline": None,
        "what_they_do": answers.get("what_they_do", ""),
        "products": _to_list(answers.get("products", "")),
        "target_customers": _to_list(answers.get("target_customers", "")),
        "industries": [],
        "competitors": _to_list(answers.get("competitors", "")),
        "pricing_model": None,
        "key_differentiators": [],
        "structured": True,
    }


# ---------------------------------------------------------------------------
# 5b. enrich_with_web_research
# ---------------------------------------------------------------------------


def enrich_with_web_research(
    company_name: str,
    intelligence: dict,
    *,
    api_key: str | None = None,
    existing_profile_keys: set | None = None,
) -> dict:
    """Enrich intelligence using Anthropic's server-side web search.

    Uses Claude's built-in web_search_20250305 tool which performs real web
    searches server-side — same quality as Claude Code's research. The LLM
    searches iteratively, follows leads, and synthesizes deep intelligence.

    Args:
        company_name: Company name for research queries.
        intelligence: Existing intelligence dict from site crawl.
        api_key: Anthropic API key (optional; falls back to environment).
        existing_profile_keys: Set of file_names already populated in the tenant's
            context store. When provided, the prompt skips already-filled categories
            and reduces web search budget accordingly.

    Returns:
        Enriched intelligence dict. On any failure, returns the original
        intelligence dict unchanged.
    """
    try:
        import anthropic
    except ImportError:
        return intelligence

    # Build a summary of what we already know
    known_parts = []
    for key in ["what_they_do", "products", "industries", "target_customers",
                "competitors", "pricing_model", "key_differentiators"]:
        val = intelligence.get(key)
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            known_parts.append("- %s: %s" % (key.replace("_", " ").title(), val))
    known_summary = "\n".join(known_parts) if known_parts else "Very little is known."

    company_url = intelligence.get("_source_url", "")

    # Build gap-aware skip markers for search items
    epk = existing_profile_keys or set()

    def _skip(key: str) -> str:
        return "(SKIP - already have) " if key in epk else ""

    item1_prefix = _skip("leadership.md")       # key people / executives
    item2_prefix = _skip("company-details.md")   # company size / HQ
    item4_prefix = _skip("company-details.md")   # headquarters
    item5_prefix = _skip("competitive-intel.md") # competitors
    item6_prefix = _skip("tech-stack.md")        # tech stack
    item10_prefix = _skip("leadership.md")       # people LinkedIn

    # Build gap notice when profile already has populated categories
    gap_notice = ""
    if epk:
        gap_notice = (
            "The company profile already has data for these categories: %s\n"
            "Focus your research ONLY on categories that are missing or sparse. "
            "Do NOT research categories that are already well-populated.\n\n"
        ) % ", ".join(sorted(epk))

    user_message = (
        "Research this company deeply using web search:\n\n"
        "Company: %s\n"
        "Website: %s\n\n"
        "What we already know from their website:\n%s\n\n"
        "%s"
        "Search for ALL of these:\n"
        "1. %sLeadership team — ONLY C-suite (CEO, CTO, CFO, COO, CPO), founders, and VP/SVP-level executives. Do NOT include junior employees, managers, or individual contributors.\n"
        "2. %sCompany size — employee count, offices, global presence\n"
        "3. Funding — investors, rounds, amounts raised\n"
        "4. %sHeadquarters location\n"
        "5. %sCompetitors in their space\n"
        "6. %sTech stack — from job postings or engineering blog\n"
        "7. Recent news, press releases, announcements\n"
        "8. Social accounts — LinkedIn company page, Twitter/X, GitHub\n"
        "9. Blog topics — what they write about\n"
        "10. %sKey people's LinkedIn profiles\n\n"
        "After researching, return ONLY a JSON object (no markdown fencing) with these keys "
        "(omit any you couldn't find evidence for):\n"
        "- competitors: list of 3-5 competitors\n"
        "- employees: string estimate (e.g. '150+', '~200')\n"
        "- headquarters: string (city, country)\n"
        "- key_people: list of C-suite/founder/VP+ leaders ONLY, each as {name, title, linkedin (real URL or null), "
        "email_pattern (or null)}. Exclude anyone below VP level.\n"
        "- funding: string summary (e.g. 'Series B, $50M' or 'Bootstrapped')\n"
        "- recent_news: list of {title, date} objects\n"
        "- tech_stack: list of technologies\n"
        "- social_accounts: {twitter, linkedin_company, github} with real URLs\n"
        "- recent_press: list of {title, date} objects\n"
        "- blog_topics: list of recent blog topics\n\n"
        "CRITICAL: Only include information you actually found in search results. "
        "LinkedIn URLs must be REAL URLs from search results, never guessed."
    ) % (
        company_name, company_url, known_summary,
        gap_notice,
        item1_prefix, item2_prefix, item4_prefix,
        item5_prefix, item6_prefix, item10_prefix,
    )

    # Always use full web search budget — refresh means the user wants fresh data
    max_web_searches = 5

    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            timeout=60,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_web_searches,
            }],
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract all text blocks from the response (interleaved with search results)
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        full_text = "\n".join(text_parts).strip()

        # The response may contain markdown explanation followed by JSON,
        # or just JSON. Try to extract JSON.
        import json
        import re

        # Try to find a JSON block in the response
        json_match = re.search(r'\{[\s\S]*\}', full_text)
        if not json_match:
            # No JSON found — ask for structured output in a follow-up
            follow_up = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": (
                        "Now return ONLY the JSON object with the structured data. "
                        "No markdown fencing, no explanation — just the JSON."
                    )},
                ],
            )
            follow_text = ""
            for block in follow_up.content:
                if hasattr(block, "text"):
                    follow_text += block.text
            json_match = re.search(r'\{[\s\S]*\}', follow_text.strip())

        if not json_match:
            return intelligence

        enrichment = json.loads(json_match.group())

        # Merge enrichment into a copy of intelligence
        enriched = dict(intelligence)
        for key in ENRICHMENT_KEYS:
            new_val = enrichment.get(key)
            if not new_val:
                continue
            existing = enriched.get(key)
            if not existing or (isinstance(existing, list) and len(existing) == 0):
                enriched[key] = new_val
            elif key == "key_people" and isinstance(new_val, list) and new_val:
                if any(isinstance(p, dict) for p in new_val) and all(
                    isinstance(p, str) for p in (existing if isinstance(existing, list) else [])
                ):
                    enriched[key] = new_val
            elif key == "competitors" and isinstance(existing, list) and isinstance(new_val, list):
                combined = list(existing)
                existing_lower = {c.lower() for c in existing}
                for comp in new_val:
                    if comp.lower() not in existing_lower:
                        combined.append(comp)
                enriched[key] = combined[:8]

        enriched["_enriched"] = True
        return enriched

    except anthropic.APITimeoutError as exc:
        import logging
        logging.getLogger(__name__).warning("Web search enrichment timed out (60s): %s", exc)
        return intelligence
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Web search enrichment failed: %s", exc)
        return intelligence


# ---------------------------------------------------------------------------
# 6. write_company_intelligence
# ---------------------------------------------------------------------------


def write_company_intelligence(
    intelligence: dict,
    agent_id: str = AGENT_ID,
) -> dict:
    """DEPRECATED: Use skill_executor's async write loop instead.

    This function uses the v1 flatfile API signature which is incompatible
    with the Postgres backend. The skill executor (_execute_company_intel)
    has its own async write loop that properly sets RLS context and uses
    the correct append_entry signature.

    Kept for backward compatibility with the flatfile backend only.
    """
    import logging
    logging.getLogger(__name__).warning(
        "write_company_intelligence() called — this is deprecated. "
        "Use the skill executor's async write loop instead."
    )

    import os
    if os.environ.get("FLYWHEEL_BACKEND", "flatfile").lower() != "flatfile":
        return {"error": "write_company_intelligence() only works with flatfile backend"}

    today = datetime.now().strftime("%Y-%m-%d")
    source = "company-intel-onboarding"
    results = {}

    section_map = {
        "positioning.md": _build_positioning_content(intelligence),
        "icp-profiles.md": _build_list_content(
            intelligence.get("target_customers", []),
            "target-customer-profiles",
        ),
        "competitive-intel.md": _build_list_content(
            intelligence.get("competitors", []),
            "competitive-landscape",
        ),
        "product-modules.md": _build_list_content(
            intelligence.get("products", []),
            "product-inventory",
        ),
        "market-taxonomy.md": _build_list_content(
            intelligence.get("industries", []),
            "industry-verticals",
        ),
    }

    for filename, (content_lines, detail) in section_map.items():
        if not content_lines:
            continue

        entry = {
            "date": today,
            "source": source,
            "detail": detail,
            "content": content_lines,
            "confidence": "medium",
            "evidence_count": 1,
        }

        try:
            result = append_entry(
                file=filename,
                entry=entry,
                source=source,
                agent_id=agent_id,
            )
            results[filename] = result
        except Exception as e:
            results[filename] = "ERROR: %s" % str(e)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_positioning_content(intelligence: dict) -> tuple:
    """Build positioning content lines from intelligence dict.

    Returns:
        Tuple of (content_lines, detail_string).
    """
    lines = []

    company_name = intelligence.get("company_name", "")
    if company_name:
        lines.append("Company: %s" % company_name)

    tagline = intelligence.get("tagline")
    if tagline:
        lines.append("Tagline: %s" % tagline)

    what_they_do = intelligence.get("what_they_do", "")
    if what_they_do:
        lines.append("Description: %s" % what_they_do)

    differentiators = intelligence.get("key_differentiators", [])
    if differentiators:
        for d in differentiators:
            lines.append("Differentiator: %s" % d)

    pricing = intelligence.get("pricing_model")
    if pricing:
        lines.append("Pricing model: %s" % pricing)

    return (lines, "company-positioning-update")


def _build_list_content(items: list, detail: str) -> tuple:
    """Build content lines from a list of items.

    Returns:
        Tuple of (content_lines, detail_string). Empty list if no items.
    """
    if not items:
        return ([], detail)
    return ([str(item) for item in items], detail)
