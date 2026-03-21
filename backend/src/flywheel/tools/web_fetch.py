"""Web fetch tool handler using httpx + readability-lxml.

Extracts readable text content from URLs for skill execution.
Budget-tracked via RunBudget (max 30 fetches per run).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flywheel.tools.registry import RunContext

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_MAX_CHARS = 8000
_MIN_QUALITY_CHARS = 500


async def handle_web_fetch(tool_input: dict, context: RunContext) -> str:
    """Fetch a URL and extract readable text content.

    Uses httpx for async HTTP + readability-lxml for article extraction.
    Falls back to BeautifulSoup-only extraction if readability-lxml
    is not installed. Truncates output to 8000 chars.
    """
    url = tool_input.get("url")
    if not url:
        return "Error: url is required"

    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        title, text = _extract_content(html)

        if not text:
            return "No readable content found at URL"

        # Quality heuristic
        quality_note = ""
        if len(text) < _MIN_QUALITY_CHARS:
            quality_note = (
                "\n\nNote: This page may require JavaScript rendering. "
                "Content may be incomplete. Connect your local agent "
                "for full extraction."
            )

        # Truncate
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS] + "\n\n[Content truncated]"

        result = f"# {title}\n\n{text}"
        if quality_note:
            result += quality_note

        return result

    except Exception as e:
        return f"Fetch failed: {e}"


def _extract_content(html: str) -> tuple[str, str]:
    """Extract title and readable text from HTML.

    Tries readability-lxml first for article extraction,
    falls back to BeautifulSoup-only if readability is not installed.

    Returns:
        Tuple of (title, plain_text).
    """
    try:
        from readability import Document

        doc = Document(html)
        title = doc.title()
        summary_html = doc.summary()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return title, text

    except ImportError:
        # readability-lxml not installed -- fall back to BS4 only
        return _extract_with_bs4(html)


def _extract_with_bs4(html: str) -> tuple[str, str]:
    """Fallback extraction using BeautifulSoup only."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Clean up multiple blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    return title, clean_text
