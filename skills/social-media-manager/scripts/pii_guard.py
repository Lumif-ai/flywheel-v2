#!/usr/bin/env python3
"""PII Guard & Reputation Layer for Social Media Manager.

Scans draft posts for PII, regulatory claims, competitor mentions,
forward-looking statements, and emotional sentiment. Returns structured
flags for human review.

Usage:
    python3 pii_guard.py --draft "post text here" [--blocklist path/to/blocklist.md]
    python3 pii_guard.py --draft-file path/to/draft.txt [--blocklist path/to/blocklist.md]
    python3 pii_guard.py --smoke-test
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


# --- Blocklist Loading ---

def load_blocklist(blocklist_path):
    """Load entities from blocklist file."""
    blocklist = {"companies": [], "people": [], "metrics": []}
    if not os.path.exists(blocklist_path):
        return blocklist

    current_section = None
    with open(blocklist_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Companies"):
                current_section = "companies"
            elif line.startswith("## People"):
                current_section = "people"
            elif line.startswith("## Metrics"):
                current_section = "metrics"
            elif line.startswith("- ") and current_section:
                entity = line[2:].strip()
                if entity:
                    blocklist[current_section].append(entity)
    return blocklist


# --- PII Detection ---

EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_RE = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
# Matches dollar amounts like $127K, $1.5M, $450,000
MONEY_RE = re.compile(r'\$[\d,]+(?:\.\d+)?[KkMmBb]?\b|\$[\d,]+(?:\.\d+)?')
# Matches specific headcount: "23 employees", "150 people", "team of 45"
HEADCOUNT_RE = re.compile(r'\b(\d+)\s+(?:employees?|people|team members?|engineers?|staff)\b', re.I)
HEADCOUNT_OF_RE = re.compile(r'\bteam of\s+(\d+)\b', re.I)


def detect_pii(text):
    """Detect PII patterns in text. Returns list of findings."""
    findings = []

    for match in EMAIL_RE.finditer(text):
        findings.append({
            "type": "email",
            "value": match.group(),
            "severity": "high",
            "suggestion": "Remove email address entirely"
        })

    for match in PHONE_RE.finditer(text):
        findings.append({
            "type": "phone",
            "value": match.group(),
            "severity": "high",
            "suggestion": "Remove phone number entirely"
        })

    for match in MONEY_RE.finditer(text):
        val = match.group()
        findings.append({
            "type": "financial_figure",
            "value": val,
            "severity": "medium",
            "suggestion": f"Consider replacing '{val}' with a range (e.g., 'six-figure', 'mid-six-figure')"
        })

    for pattern in [HEADCOUNT_RE, HEADCOUNT_OF_RE]:
        for match in pattern.finditer(text):
            findings.append({
                "type": "headcount",
                "value": match.group(),
                "severity": "low",
                "suggestion": f"Consider replacing with approximate: '~{round(int(match.group(1)), -1)}+'"
            })

    return findings


def check_blocklist(text, blocklist):
    """Check text against blocklist entities."""
    findings = []
    text_lower = text.lower()

    for section, entities in blocklist.items():
        for entity in entities:
            if entity.lower() in text_lower:
                findings.append({
                    "type": f"blocklist_{section}",
                    "value": entity,
                    "severity": "high",
                    "suggestion": f"Blocklisted {section[:-1]}: '{entity}' must be anonymized"
                })
    return findings


# --- Reputation Layer ---

CLAIM_PATTERNS = [
    (r'\b(?:ensures?|guarantees?)\s+compliance\b', "Could be read as a legal guarantee. Suggest: 'helps manage compliance workflows'"),
    (r'\bguarantees?\b', "Guarantee language — suggest: 'designed to support' or 'built to help'"),
    (r'\beliminates?\s+risk\b', "Suggest: 'reduces risk exposure'"),
    (r'\b100%\s+(?:accurate|reliable|secure|compliant)\b', "Absolute claim — consider qualifying with context"),
    (r'\bcertified\b(?!\s+by)', "Are you actually certified? If not, remove or qualify"),
    (r'\bapproved\b(?!\s+by)', "Approved by whom? Qualify or remove"),
    (r'\bno\s+(?:risk|errors?|failures?|downtime)\b', "Absolute negative claim — consider softening"),
]

FORWARD_LOOKING_PATTERNS = [
    r"we'?re\s+launching",
    r"coming\s+soon",
    r"our\s+roadmap\s+includes",
    r"we\s+plan\s+to",
    r"next\s+(?:month|quarter|week|year)\s+we",
    r"by\s+(?:Q[1-4]|end\s+of\s+(?:year|quarter))",
    r"we\s+will\s+(?:be\s+)?(?:launching|releasing|shipping|announcing)",
]

NEGATIVE_SENTIMENT_PATTERNS = [
    r"sick\s+of", r"tired\s+of", r"can'?t\s+believe",
    r"ridiculous", r"what\s+a\s+joke", r"absolutely\s+(?:terrible|awful|insane)",
    r"incompetent", r"worst\s+(?:experience|decision|mistake)",
]

COMPETITOR_INDICATORS = [
    # Generic — actual competitors come from blocklist or context
    r"unlike\s+\w+", r"better\s+than\s+\w+", r"compared\s+to\s+\w+",
    r"switched?\s+from\s+\w+", r"replaced?\s+\w+\s+with",
]


def check_claims(text):
    """Check for regulatory/legal claim language."""
    findings = []
    for pattern, suggestion in CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            findings.append({
                "type": "regulatory_claim",
                "value": match.group(),
                "severity": "medium",
                "suggestion": suggestion
            })
    return findings


def check_forward_looking(text):
    """Check for forward-looking statements."""
    findings = []
    for pattern in FORWARD_LOOKING_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            findings.append({
                "type": "forward_looking",
                "value": match.group(),
                "severity": "low",
                "suggestion": "Forward-looking statement. Are you comfortable with this public commitment?"
            })
    return findings


def check_sentiment(text):
    """Detect emotionally charged content."""
    findings = []
    negative_count = 0

    for pattern in NEGATIVE_SENTIMENT_PATTERNS:
        matches = re.findall(pattern, text, re.I)
        negative_count += len(matches)
        for m in matches:
            findings.append({
                "type": "negative_sentiment",
                "value": m if isinstance(m, str) else m,
                "severity": "medium",
                "suggestion": "Emotionally charged language detected"
            })

    # Check for excessive caps or exclamation marks
    caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
    exclamation_count = text.count('!')

    if len(caps_words) > 2:
        findings.append({
            "type": "excessive_caps",
            "value": ", ".join(caps_words[:3]),
            "severity": "low",
            "suggestion": "Multiple ALL-CAPS words suggest strong emotion. Intentional?"
        })

    if exclamation_count > 3:
        findings.append({
            "type": "excessive_exclamation",
            "value": f"{exclamation_count} exclamation marks",
            "severity": "low",
            "suggestion": "Many exclamation marks can read as emotional. Review tone."
        })

    return findings, negative_count >= 2


# --- AI Smell Detector ---

AI_TELL_PATTERNS = [
    (r'\b[Hh]ere\'?s\s+(?:the\s+thing|what\s+I\s+learned|what\s+happened)\b', "AI tell: 'Here's the thing/what I learned'"),
    (r'\b[Ii]n\s+today\'?s\s+(?:fast-paced|rapidly\s+evolving|ever-changing)\b', "AI tell: generic opening"),
    (r'\b[Ll]et\s+me\s+break\s+(?:it|this)\s+down\b', "AI tell: 'Let me break it down'"),
    (r'\b[Tt]he\s+truth\s+is\b', "AI tell: 'The truth is'"),
    (r'\b[Ee]xcited\s+to\s+announce\b', "Corporate tell: 'Excited to announce'"),
    (r'\b[Tt]hrilled\s+to\s+share\b', "Corporate tell: 'Thrilled to share'"),
    (r'\b[Ii]\'?m\s+humbled\b', "Corporate tell: 'I'm humbled'"),
    (r'\bleverage\b', "Buzzword: 'leverage'"),
    (r'\bsynergy\b', "Buzzword: 'synergy'"),
    (r'\bparadigm\b', "Buzzword: 'paradigm'"),
    (r'\bdisrupt(?:ion|ive)?\b', "Buzzword: 'disruption'"),
    (r'\btransformative\b', "Buzzword: 'transformative'"),
    (r'\b[Aa]nd\s+that\'?s\s+why\s+I\s+believe\b', "LinkedIn-bro tell: motivational closer"),
    (r'\b[Ii]f\s+this\s+resonated\b', "Engagement bait tell"),
    (r'\b[Dd]rop\s+a\s+comment\b', "Engagement bait tell"),
    (r'\b[Ll]ike\s+if\s+you\s+agree\b', "Engagement bait tell"),
]


def check_ai_smell(text):
    """Detect AI-generated content patterns."""
    findings = []

    for pattern, label in AI_TELL_PATTERNS:
        for match in re.finditer(pattern, text):
            findings.append({
                "type": "ai_tell",
                "value": match.group(),
                "severity": "medium",
                "suggestion": label
            })

    # Check for em-dash overuse
    em_dash_count = text.count('\u2014') + text.count(' -- ') + text.count(' - ')
    if em_dash_count > 1:
        findings.append({
            "type": "ai_tell",
            "value": f"{em_dash_count} em-dashes/long dashes",
            "severity": "low",
            "suggestion": "Multiple em-dashes is an AI writing tell. Use periods or commas instead."
        })

    # Check for semicolons
    semicolon_count = text.count(';')
    if semicolon_count > 0:
        findings.append({
            "type": "ai_tell",
            "value": f"{semicolon_count} semicolon(s)",
            "severity": "low",
            "suggestion": "Semicolons feel formal/AI. Nobody texts with semicolons."
        })

    return findings


# --- Main Scan ---

def scan_draft(text, blocklist_path=None):
    """Run full scan on draft text. Returns structured results."""
    default_blocklist = os.path.expanduser(
        "~/.claude/skills/social-media-manager/data/blocklist.md"
    )
    bl_path = blocklist_path or default_blocklist
    blocklist = load_blocklist(bl_path)

    all_findings = []
    all_findings.extend(detect_pii(text))
    all_findings.extend(check_blocklist(text, blocklist))
    all_findings.extend(check_claims(text))
    all_findings.extend(check_forward_looking(text))

    sentiment_findings, is_emotionally_charged = check_sentiment(text)
    all_findings.extend(sentiment_findings)

    ai_findings = check_ai_smell(text)
    all_findings.extend(ai_findings)

    # Categorize by severity
    high = [f for f in all_findings if f["severity"] == "high"]
    medium = [f for f in all_findings if f["severity"] == "medium"]
    low = [f for f in all_findings if f["severity"] == "low"]

    result = {
        "scan_time": datetime.now().isoformat(),
        "char_count": len(text),
        "word_count": len(text.split()),
        "passed": len(high) == 0,
        "emotionally_charged": is_emotionally_charged,
        "summary": {
            "high": len(high),
            "medium": len(medium),
            "low": len(low),
            "total": len(all_findings)
        },
        "findings": all_findings
    }

    return result


def format_results(result):
    """Format scan results for display."""
    lines = []

    if result["passed"] and result["summary"]["total"] == 0:
        lines.append("PII Guard: CLEAN — no issues found")
        return "\n".join(lines)

    status = "BLOCKED" if not result["passed"] else "WARNINGS"
    lines.append(f"PII Guard: {status} — {result['summary']['total']} issue(s)")
    lines.append(f"  High: {result['summary']['high']}  Medium: {result['summary']['medium']}  Low: {result['summary']['low']}")
    lines.append("")

    if result["emotionally_charged"]:
        lines.append("BAD DAY SAFEGUARD TRIGGERED")
        lines.append("This draft reads emotionally charged. Options:")
        lines.append("  (a) Post now — you know your audience best")
        lines.append("  (b) Schedule for tomorrow — review with fresh eyes (recommended)")
        lines.append("  (c) Save to private drafts — revisit later")
        lines.append("  (d) Rewrite — keep the core insight, remove the heat")
        lines.append("")

    for severity in ["high", "medium", "low"]:
        items = [f for f in result["findings"] if f["severity"] == severity]
        if items:
            lines.append(f"[{severity.upper()}]")
            for f in items:
                lines.append(f"  {f['type']}: \"{f['value']}\"")
                lines.append(f"    → {f['suggestion']}")
            lines.append("")

    return "\n".join(lines)


# --- Smoke Test ---

def smoke_test():
    """Minimal test to verify the guard works."""
    test_draft = """
    So Buildcore Inc called me today. John Smith their VP was furious.
    We guarantee compliance and ensure 100% accurate results.
    We're launching our new product next month!
    I'm sick of these VCs who can't believe how ridiculous the market is!!!
    Here's the thing: in today's fast-paced world, we need to leverage synergy.
    Contact me at john@example.com or call 555-123-4567.
    Our $127K MRR is growing with 23 employees.
    """

    # Create temp blocklist
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# PII Blocklist\n## Companies\n- Buildcore Inc\n## People\n- John Smith\n## Metrics\n")
        bl_path = f.name

    try:
        result = scan_draft(test_draft, bl_path)
        print(format_results(result))
        print(f"\nTotal findings: {result['summary']['total']}")

        # Verify we caught the key issues
        types_found = {f["type"] for f in result["findings"]}
        expected = {"email", "phone", "blocklist_companies", "blocklist_people",
                    "regulatory_claim", "forward_looking", "negative_sentiment", "ai_tell"}
        missing = expected - types_found
        if missing:
            print(f"\nWARNING: Did not detect: {missing}")
            return False
        else:
            print("\nSMOKE TEST PASSED — all expected issue types detected")
            return True
    finally:
        os.unlink(bl_path)


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="PII Guard & Reputation Layer")
    parser.add_argument("--draft", help="Draft text to scan")
    parser.add_argument("--draft-file", help="File containing draft text")
    parser.add_argument("--blocklist", help="Path to blocklist file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke test")
    args = parser.parse_args()

    if args.smoke_test:
        success = smoke_test()
        sys.exit(0 if success else 1)

    text = None
    if args.draft:
        text = args.draft
    elif args.draft_file:
        if not os.path.exists(args.draft_file):
            print(f"ERROR: File not found: {args.draft_file}")
            sys.exit(1)
        with open(args.draft_file) as f:
            text = f.read()
    else:
        parser.print_help()
        sys.exit(1)

    result = scan_draft(text, args.blocklist)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_results(result))

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
