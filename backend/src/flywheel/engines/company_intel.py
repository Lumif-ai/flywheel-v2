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

    pages_to_crawl = CRAWL_PAGES[:max_pages]

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    ) as client:
        for path in pages_to_crawl:
            page_url = base_url + path
            try:
                resp = await client.get(page_url)
                resp.raise_for_status()

                # Parse HTML
                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract meta information (works even for SPA sites)
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

                # Strip unwanted tags and extract body text
                for tag in soup.find_all(["script", "style", "nav", "footer"]):
                    tag.decompose()

                converter = html2text.HTML2Text()
                converter.ignore_links = False
                converter.ignore_images = True
                converter.body_width = 0
                body_text = converter.handle(str(soup)).strip()

                # Combine meta info + body text
                # For SPA sites, body may be empty but meta has useful info
                text = "\n".join(meta_parts)
                if body_text:
                    text = text + "\n\n" + body_text if text else body_text

                if text.strip():
                    result["raw_pages"][path or "/"] = text.strip()
                    result["pages_crawled"] += 1

            except (httpx.HTTPError, httpx.HTTPStatusError):
                # Skip failed pages, continue with others
                continue

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


def structure_intelligence(raw_text: str, source_label: str) -> dict:
    """Use LLM to structure raw text into company intelligence dict.

    Falls back to returning raw text if anthropic SDK is unavailable.

    Args:
        raw_text: Raw crawled or uploaded text.
        source_label: Label describing the source (e.g. "website-crawl").

    Returns:
        Dict with intelligence keys (company_name, tagline, etc.)
        or {"raw_text": raw_text, "structured": False} on SDK failure.
    """
    try:
        import anthropic
    except ImportError:
        return {"raw_text": raw_text, "structured": False}

    try:
        client = anthropic.Anthropic()

        system_prompt = (
            "You are extracting company intelligence from raw text. "
            "Extract ONLY information that is explicitly present in the text. "
            "Do NOT invent or assume any information. "
            "Return a JSON object with these keys:\n"
            "- company_name: string\n"
            "- tagline: string (or null)\n"
            "- what_they_do: string (1-2 sentence summary)\n"
            "- products: list of strings\n"
            "- target_customers: list of strings\n"
            "- industries: list of strings\n"
            "- competitors: list of strings (or empty list)\n"
            "- pricing_model: string (or null)\n"
            "- key_differentiators: list of strings\n\n"
            "Return ONLY valid JSON. No markdown fencing."
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": "Extract company intelligence from this text (source: %s):\n\n%s"
                    % (source_label, raw_text[:8000]),
                }
            ],
        )

        import json
        response_text = message.content[0].text.strip()
        intelligence = json.loads(response_text)
        intelligence["structured"] = True
        return intelligence

    except Exception:
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


def enrich_with_web_research(company_name: str, intelligence: dict) -> dict:
    """Enrich intelligence using Anthropic's server-side web search.

    Uses Claude's built-in web_search_20250305 tool which performs real web
    searches server-side — same quality as Claude Code's research. The LLM
    searches iteratively, follows leads, and synthesizes deep intelligence.

    Args:
        company_name: Company name for research queries.
        intelligence: Existing intelligence dict from site crawl.

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

    user_message = (
        "Research this company deeply using web search:\n\n"
        "Company: %s\n"
        "Website: %s\n\n"
        "What we already know from their website:\n%s\n\n"
        "Search for ALL of these:\n"
        "1. Leadership team — CEO, founders, key executives with their titles\n"
        "2. Company size — employee count, offices, global presence\n"
        "3. Funding — investors, rounds, amounts raised\n"
        "4. Headquarters location\n"
        "5. Competitors in their space\n"
        "6. Tech stack — from job postings or engineering blog\n"
        "7. Recent news, press releases, announcements\n"
        "8. Social accounts — LinkedIn company page, Twitter/X, GitHub\n"
        "9. Blog topics — what they write about\n"
        "10. Key people's LinkedIn profiles\n\n"
        "After researching, return ONLY a JSON object (no markdown fencing) with these keys "
        "(omit any you couldn't find evidence for):\n"
        "- competitors: list of 3-5 competitors\n"
        "- employees: string estimate (e.g. '150+', '~200')\n"
        "- headquarters: string (city, country)\n"
        "- key_people: list of leaders, each as {name, title, linkedin (real URL or null), "
        "email_pattern (or null)}\n"
        "- funding: string summary (e.g. 'Series B, $50M' or 'Bootstrapped')\n"
        "- recent_news: list of {title, date} objects\n"
        "- tech_stack: list of technologies\n"
        "- social_accounts: {twitter, linkedin_company, github} with real URLs\n"
        "- recent_press: list of {title, date} objects\n"
        "- blog_topics: list of recent blog topics\n\n"
        "CRITICAL: Only include information you actually found in search results. "
        "LinkedIn URLs must be REAL URLs from search results, never guessed."
    ) % (company_name, company_url, known_summary)

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 10,
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
    """Write structured intelligence to context store files.

    Maps intelligence fields to context store files:
      - company_name/tagline/what_they_do/key_differentiators -> positioning.md
      - target_customers -> icp-profiles.md
      - competitors -> competitive-intel.md
      - products -> product-modules.md
      - industries -> market-taxonomy.md

    Args:
        intelligence: Dict with company intelligence (from structure_intelligence
            or structure_from_answers).
        agent_id: Agent ID for context store writes. Defaults to "company-intel".

    Returns:
        Dict of {filename: "OK"|"DEDUP"|"ERROR: msg"}.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    source = "company-intel-onboarding"
    results = {}

    # Map sections to context files
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
            # Skip empty content
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
