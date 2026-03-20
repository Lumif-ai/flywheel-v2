"""
learning_engine.py - Phase 6 Learning Engine for Flywheel.

Evidence weighting with source diversity scoring and recency decay for
context store entries, contradiction detection, strategy synthesis, and
health monitoring.

Subsystems:
  1. Evidence weighting - score entries by evidence count, confidence, recency
  2. Source diversity - count distinct source types per topic
  3. Entry scoring - composite scoring combining all factors
  4. Contradiction detection - find conflicting assertions within/across files
  5. Strategy synthesizer - on-demand synthesis writing to _learning/ staging
  6. Health monitoring - overdue alerts based on last synthesis run

All functions are pure computations over ContextEntry objects from
context_utils. The learning engine reads context files but writes only
to _learning/ staging area (LRNG-07).
"""

import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import context_utils
from context_utils import (
    CONFIDENCE_ORDER,
    CONTEXT_ROOT,
    ContextEntry,
    append_entry,
    parse_context_file,
    read_context,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DECAY_THRESHOLD_DAYS = 90
STALE_THRESHOLD_DAYS = 180
AGENT_ID = "learning-engine"
LEARNING_DIR = CONTEXT_ROOT / "_learning"

# Contradiction detection thresholds (LRNG-05)
TOPIC_SIMILARITY_THRESHOLD = 0.5
CONTRADICTION_SIM_LOW = 0.2   # Below this = unrelated content
CONTRADICTION_SIM_HIGH = 0.7  # Above this = agreement, not contradiction

# Related file pairs for cross-file contradiction scanning
RELATED_FILE_PAIRS: List[Tuple[str, str]] = [
    ("pain-points.md", "positioning.md"),
    ("icp-profiles.md", "contacts.md"),
]

# Health monitoring thresholds (LRNG-08)
HEALTH_WARNING_DAYS = 7
HEALTH_CRITICAL_DAYS = 14
HEALTH_GRACE_DAYS = 14  # Grace period after first init to avoid false alarms

# Coherence-check file pairs (topics in file_a should be referenced in file_b)
COHERENCE_FILE_PAIRS: List[Tuple[str, str]] = [
    ("pain-points.md", "positioning.md"),
    ("icp-profiles.md", "contacts.md"),
]

# ---------------------------------------------------------------------------
# Effectiveness tracking (record_learning)
# ---------------------------------------------------------------------------


def record_learning(
    source: str,
    target_file: str,
    detail: str,
    operation: str = "write",
    agent_id: str = AGENT_ID,
    today: datetime = None,
) -> None:
    """Record a learning event for effectiveness tracking.

    Called from post-write workflow to track what knowledge was written where.
    Fails silently -- learning data is secondary to the actual write.

    Appends to _learning/effectiveness-log.md via context_utils.append_entry().
    """
    today = today or datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    entry_dict = {
        "date": date_str,
        "source": source,
        "detail": f"op:{operation} file:{target_file} detail:{detail}",
        "content": [
            f"- operation: {operation}",
            f"- target: {target_file}",
            f"- detail: {detail}",
            f"- timestamp: {today.isoformat()}",
        ],
        "evidence_count": 1,
        "confidence": "low",
    }

    try:
        # Ensure _learning directory exists
        learning_dir = context_utils.CONTEXT_ROOT / "_learning"
        learning_dir.mkdir(parents=True, exist_ok=True)

        append_entry(
            file="_learning/effectiveness-log.md",
            entry=entry_dict,
            source=source,
            agent_id=agent_id,
        )
    except Exception:
        pass  # Learning data is best-effort, never blocks the actual write


# ---------------------------------------------------------------------------
# Source type extraction
# ---------------------------------------------------------------------------


def extract_source_type(source: str) -> str:
    """Extract source type from a source identifier.

    Source types group skills by their data origin:
    - meeting-processor, ctx-meeting-processor -> "meeting"
    - ctx-gtm-pipeline, gtm-pipeline -> "gtm"
    - ctx-gtm-my-company -> "gtm"
    - ctx-investor-update -> "investor"
    - manual, user -> "manual"
    - anything else -> source.lower() as fallback
    """
    normalized = source.lower().replace("ctx-", "").replace("-", " ")
    if "meeting" in normalized:
        return "meeting"
    elif "gtm" in normalized:
        return "gtm"
    elif "investor" in normalized:
        return "investor"
    elif "manual" in normalized or "user" in normalized:
        return "manual"
    else:
        return source.lower()


# ---------------------------------------------------------------------------
# Evidence weighting
# ---------------------------------------------------------------------------


def compute_entry_weight(entry: ContextEntry, today: datetime = None) -> dict:
    """Score an entry based on evidence count, confidence, and recency.

    Returns a dict with all scoring components:
    - evidence_weight: min(evidence_count, 20) / 20.0 (capped)
    - conf_multiplier: high=1.0, medium=0.6, low=0.3
    - recency_factor: 1.0 (fresh), linear decay (decaying), 0.1 (stale)
    - composite_score: evidence_weight * conf_multiplier * recency_factor
    - age_days: days since entry date
    - staleness: "fresh", "decaying", or "stale"
    """
    today = today or datetime.now()
    age_days = (today - entry.date).days

    # Base weight from evidence count (capped at 20)
    evidence_weight = min(entry.evidence_count, 20) / 20.0

    # Confidence multiplier
    conf_multiplier = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(
        entry.confidence, 0.3
    )

    # Recency decay (LRNG-03)
    if age_days > STALE_THRESHOLD_DAYS:
        recency_factor = 0.1
        staleness = "stale"
    elif age_days > DECAY_THRESHOLD_DAYS:
        # Linear decay from 1.0 to 0.1 between 90 and 180 days
        decay_progress = (age_days - DECAY_THRESHOLD_DAYS) / (
            STALE_THRESHOLD_DAYS - DECAY_THRESHOLD_DAYS
        )
        recency_factor = 1.0 - (0.9 * decay_progress)
        staleness = "decaying"
    else:
        recency_factor = 1.0
        staleness = "fresh"

    composite_score = evidence_weight * conf_multiplier * recency_factor

    return {
        "entry": entry,
        "evidence_weight": evidence_weight,
        "conf_multiplier": conf_multiplier,
        "recency_factor": recency_factor,
        "composite_score": composite_score,
        "age_days": age_days,
        "staleness": staleness,
    }


# ---------------------------------------------------------------------------
# Source diversity
# ---------------------------------------------------------------------------


def compute_source_diversity(entries: List[ContextEntry], topic_detail: str) -> int:
    """Count distinct source types among entries matching a topic.

    Given a list of entries and a topic (detail string), count distinct
    source types among entries whose detail field matches the topic
    (case-insensitive).

    Returns count of unique source types.
    """
    topic_lower = topic_detail.lower().strip()
    source_types = set()
    for entry in entries:
        entry_topic = (entry.detail or "").lower().strip()
        if entry_topic == topic_lower:
            source_types.add(extract_source_type(entry.source))
    return len(source_types)


# ---------------------------------------------------------------------------
# Full entry scoring
# ---------------------------------------------------------------------------


def score_entries_in_file(
    file: str,
    agent_id: str = AGENT_ID,
    today: datetime = None,
) -> List[dict]:
    """Score all entries in a context file by evidence, diversity, and recency.

    For each entry:
    1. Compute base weight (evidence, confidence, recency)
    2. Determine source diversity for the entry's topic
    3. Apply diversity multiplier (1.0 if diversity >= 2, else 0.7)
    4. Check if entry meets high-confidence bar

    Returns list of score dicts sorted by composite_score descending.
    """
    today = today or datetime.now()
    content = read_context(file, agent_id)
    entries = parse_context_file(content)

    # Group entries by topic (detail field, lowercased) for source diversity
    topic_sources: Dict[str, set] = {}
    for entry in entries:
        topic = (entry.detail or "unknown").lower().strip()
        if topic not in topic_sources:
            topic_sources[topic] = set()
        topic_sources[topic].add(extract_source_type(entry.source))

    scored = []
    for entry in entries:
        topic = (entry.detail or "unknown").lower().strip()
        source_types = topic_sources.get(topic, set())
        source_diversity = len(source_types)

        # Diversity bonus (LRNG-02): 2+ source types for high confidence
        diversity_multiplier = 1.0 if source_diversity >= 2 else 0.7

        weight = compute_entry_weight(entry, today)
        weight["source_diversity"] = source_diversity
        weight["diversity_multiplier"] = diversity_multiplier
        weight["composite_score"] *= diversity_multiplier
        weight["meets_high_confidence_bar"] = (
            source_diversity >= 2
            and entry.evidence_count >= 3
            and weight["staleness"] == "fresh"
        )
        scored.append(weight)

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Contradiction detection (LRNG-05)
# ---------------------------------------------------------------------------


def find_topic_groups(
    entries: List[ContextEntry],
    threshold: float = TOPIC_SIMILARITY_THRESHOLD,
) -> Dict[str, List[ContextEntry]]:
    """Group entries by detail field similarity using SequenceMatcher.

    For each entry, find the best matching existing group key.
    If best ratio >= threshold, add to that group; else create new group.
    Skip entries with empty detail.

    Returns dict: group_key -> list of entries.
    """
    groups: Dict[str, List[ContextEntry]] = {}

    for entry in entries:
        detail = (entry.detail or "").strip()
        if not detail:
            continue

        # Find best matching existing group
        best_key = None
        best_ratio = 0.0
        for key in groups:
            ratio = SequenceMatcher(None, detail.lower(), key.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key

        if best_key is not None and best_ratio >= threshold:
            groups[best_key].append(entry)
        else:
            groups[detail] = [entry]

    return groups


def _make_entry_side(entry: ContextEntry) -> dict:
    """Build one side of a contradiction dict from a ContextEntry."""
    content_text = " ".join(entry.content)
    return {
        "date": entry.date.strftime("%Y-%m-%d"),
        "source": entry.source,
        "content_summary": content_text[:200],
        "evidence_count": entry.evidence_count,
        "confidence": entry.confidence,
    }


def _check_pair_contradiction(
    entry_a: ContextEntry,
    entry_b: ContextEntry,
    topic: str,
    file_label: str,
) -> Optional[dict]:
    """Check if two entries contradict each other.

    Returns a contradiction dict if content similarity is in the
    contradiction range (between CONTRADICTION_SIM_LOW and
    CONTRADICTION_SIM_HIGH), else None.

    Skips pairs where either entry has supersedes set.
    """
    # Skip if either has supersedes
    if entry_a.supersedes or entry_b.supersedes:
        return None

    # Compute content similarity
    content_a = " ".join(entry_a.content)
    content_b = " ".join(entry_b.content)
    similarity = SequenceMatcher(None, content_a.lower(), content_b.lower()).ratio()

    # Contradiction range: not too similar (agreement) and not too different (unrelated)
    if CONTRADICTION_SIM_LOW < similarity < CONTRADICTION_SIM_HIGH:
        return {
            "file": file_label,
            "topic": topic,
            "entry_a": _make_entry_side(entry_a),
            "entry_b": _make_entry_side(entry_b),
            "similarity": round(similarity, 3),
        }
    return None


def detect_contradictions_in_file(
    file: str,
    agent_id: str = AGENT_ID,
) -> List[dict]:
    """Detect contradictions among entries within a single context file.

    Groups entries by topic, then for each group with 2+ entries, checks
    all pairs for contradictions (content similarity in the contradiction
    range). Entries with supersedes set are excluded.

    Returns list of contradiction dicts.
    """
    content = read_context(file, agent_id)
    entries = parse_context_file(content)
    if not entries:
        return []

    groups = find_topic_groups(entries)
    contradictions = []

    for topic, group_entries in groups.items():
        if len(group_entries) < 2:
            continue
        for i in range(len(group_entries)):
            for j in range(i + 1, len(group_entries)):
                result = _check_pair_contradiction(
                    group_entries[i], group_entries[j], topic, file
                )
                if result:
                    contradictions.append(result)

    return contradictions


def detect_contradictions_across_files(
    file_pairs: List[Tuple[str, str]] = None,
    agent_id: str = AGENT_ID,
) -> List[dict]:
    """Detect contradictions across related file pairs.

    For each pair (file_a, file_b), reads both files, combines entries,
    groups by topic, then checks groups containing entries from BOTH files.

    Returns list of contradiction dicts.
    """
    if file_pairs is None:
        file_pairs = RELATED_FILE_PAIRS

    contradictions = []

    for file_a, file_b in file_pairs:
        content_a = read_context(file_a, agent_id)
        content_b = read_context(file_b, agent_id)
        entries_a = parse_context_file(content_a)
        entries_b = parse_context_file(content_b)

        if not entries_a or not entries_b:
            continue

        # Tag entries with their source file for filtering
        entries_a_set = set(id(e) for e in entries_a)

        # Combine and group by topic
        all_entries = entries_a + entries_b
        groups = find_topic_groups(all_entries)

        file_label = f"{file_a} <-> {file_b}"

        for topic, group_entries in groups.items():
            # Only check groups with entries from BOTH files
            has_a = any(id(e) in entries_a_set for e in group_entries)
            has_b = any(id(e) not in entries_a_set for e in group_entries)
            if not (has_a and has_b):
                continue

            # Check cross-file pairs only
            for i in range(len(group_entries)):
                for j in range(i + 1, len(group_entries)):
                    e_i = group_entries[i]
                    e_j = group_entries[j]
                    # Only compare if from different files
                    i_from_a = id(e_i) in entries_a_set
                    j_from_a = id(e_j) in entries_a_set
                    if i_from_a == j_from_a:
                        continue
                    result = _check_pair_contradiction(
                        e_i, e_j, topic, file_label
                    )
                    if result:
                        contradictions.append(result)

    return contradictions


# ---------------------------------------------------------------------------
# Strategy synthesizer helpers (LRNG-06, LRNG-07)
# ---------------------------------------------------------------------------


def _get_context_files() -> List[str]:
    """List context files in CONTEXT_ROOT, excluding system files (starting with _) and dirs.

    Returns list of file names (e.g. ['pain-points.md', 'icp-profiles.md']).
    """
    root = context_utils.CONTEXT_ROOT
    if not root.is_dir():
        return []
    files = []
    for p in sorted(root.iterdir()):
        if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
            files.append(p.name)
    return files


def _audit_stale_entries(
    agent_id: str = AGENT_ID, today: datetime = None
) -> List[dict]:
    """Find decaying and stale entries across all context files.

    Returns list of dicts: {file, date, source, detail, staleness, age_days}.
    """
    today = today or datetime.now()
    stale = []
    for fname in _get_context_files():
        try:
            scored = score_entries_in_file(fname, agent_id=agent_id, today=today)
        except Exception:
            continue
        for s in scored:
            if s["staleness"] in ("decaying", "stale"):
                entry = s["entry"]
                stale.append({
                    "file": fname,
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "source": entry.source,
                    "detail": entry.detail,
                    "staleness": s["staleness"],
                    "age_days": s["age_days"],
                })
    return stale


def _find_high_confidence_insights(
    agent_id: str = AGENT_ID, today: datetime = None
) -> List[dict]:
    """Find entries that meet the high-confidence bar across all context files.

    Returns list of dicts: {file, date, source, detail, composite_score,
    evidence_count, source_diversity}.
    """
    today = today or datetime.now()
    insights = []
    for fname in _get_context_files():
        try:
            scored = score_entries_in_file(fname, agent_id=agent_id, today=today)
        except Exception:
            continue
        for s in scored:
            if s.get("meets_high_confidence_bar"):
                entry = s["entry"]
                insights.append({
                    "file": fname,
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "source": entry.source,
                    "detail": entry.detail,
                    "composite_score": round(s["composite_score"], 3),
                    "evidence_count": entry.evidence_count,
                    "source_diversity": s["source_diversity"],
                })
    return insights


def _check_cross_file_coherence(
    agent_id: str = AGENT_ID,
) -> List[dict]:
    """Check if key topics in related file pairs reference each other.

    For each pair (file_a, file_b), extract detail fields from each file,
    and check for keyword overlap. If a topic in file_a has no keyword
    overlap with any entry in file_b, flag it.

    Returns list of coherence issues: {file_a, file_b, topic, issue}.
    """
    issues = []
    for file_a, file_b in COHERENCE_FILE_PAIRS:
        try:
            content_a = read_context(file_a, agent_id)
            content_b = read_context(file_b, agent_id)
        except Exception:
            continue
        entries_a = parse_context_file(content_a)
        entries_b = parse_context_file(content_b)
        if not entries_a or not entries_b:
            continue

        # Extract keywords from file_b detail+content for quick lookup
        b_keywords = set()
        for entry in entries_b:
            for word in (entry.detail or "").lower().split():
                if len(word) > 3:
                    b_keywords.add(word)
            for line in entry.content:
                for word in line.lower().split():
                    clean = word.strip("-*#>,.;:()[]")
                    if len(clean) > 3:
                        b_keywords.add(clean)

        # Check each topic in file_a
        topics_checked = set()
        for entry in entries_a:
            topic = (entry.detail or "").strip()
            if not topic or topic.lower() in topics_checked:
                continue
            topics_checked.add(topic.lower())

            # Check if any keyword from this topic appears in file_b
            topic_words = [w for w in topic.lower().split() if len(w) > 3]
            if topic_words and not any(w in b_keywords for w in topic_words):
                issues.append({
                    "file_a": file_a,
                    "file_b": file_b,
                    "topic": topic,
                    "issue": f"topic '{topic}' in {file_a} not referenced in {file_b}",
                })
    return issues


def _read_effectiveness_data(agent_id: str = AGENT_ID) -> List[dict]:
    """Read effectiveness entries from _learning/gtm-learning.md if it exists.

    Returns list of dicts: {tactic, score, sample_size, suppressed}.
    """
    learning_file = "_learning/gtm-learning.md"
    try:
        content = read_context(learning_file, agent_id)
    except Exception:
        return []
    if not content or not content.strip():
        return []

    entries = parse_context_file(content)
    results = []
    for entry in entries:
        # Parse content lines for effectiveness data
        score = entry.effectiveness_score
        suppressed = False
        sample_size = entry.evidence_count
        tactic = entry.detail or "unknown"

        # Check content for suppressed indicator
        for line in entry.content:
            lower = line.lower()
            if "suppressed" in lower or "cold-start" in lower:
                suppressed = True
            # Try to extract sample_size from content
            m = re.search(r"sample[_\s]*size[:\s]*(\d+)", lower)
            if m:
                sample_size = int(m.group(1))

        results.append({
            "tactic": tactic,
            "score": score if score is not None else 0.0,
            "sample_size": sample_size,
            "suppressed": suppressed,
        })
    return results


# ---------------------------------------------------------------------------
# Manifest management
# ---------------------------------------------------------------------------


def initialize_learning_manifest(today: datetime = None) -> None:
    """Create _learning/_learning-manifest.md if it does not exist (idempotent).

    Writes initial content with: last_synthesis_run=None, synthesis_count=0,
    initialized={today}.
    """
    today = today or datetime.now()
    manifest_path = context_utils.CONTEXT_ROOT / "_learning" / "_learning-manifest.md"
    if manifest_path.exists():
        return  # Idempotent: do nothing if already exists

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    date_str = today.strftime("%Y-%m-%d")
    content = (
        f"*Learning Engine Manifest*\n"
        f"*initialized: {date_str}*\n"
        f"*last_synthesis_run: None*\n"
        f"*synthesis_count: 0*\n"
        f"\n"
        f"## Run History\n"
        f"\n"
        f"| Date | Contradictions | Stale | High-Confidence | Coherence | Effectiveness |\n"
        f"|------|---------------|-------|-----------------|-----------|---------------|\n"
    )
    manifest_path.write_text(content)


def _update_learning_manifest(summary: dict, today: datetime = None) -> None:
    """Update _learning/_learning-manifest.md with latest run data.

    Updates last_synthesis_run, increments synthesis_count, appends row to
    run history table.
    """
    today = today or datetime.now()
    manifest_path = context_utils.CONTEXT_ROOT / "_learning" / "_learning-manifest.md"
    if not manifest_path.exists():
        initialize_learning_manifest(today)

    content = manifest_path.read_text()
    date_str = today.strftime("%Y-%m-%d")

    # Update last_synthesis_run
    content = re.sub(
        r"\*last_synthesis_run: [^*]*\*",
        f"*last_synthesis_run: {date_str}*",
        content,
    )

    # Increment synthesis_count
    m = re.search(r"\*synthesis_count: (\d+)\*", content)
    count = int(m.group(1)) + 1 if m else 1
    content = re.sub(
        r"\*synthesis_count: \d+\*",
        f"*synthesis_count: {count}*",
        content,
    )

    # Append row to history table
    row = (
        f"| {date_str} "
        f"| {summary.get('contradictions_count', 0)} "
        f"| {summary.get('stale_count', 0)} "
        f"| {summary.get('high_confidence_count', 0)} "
        f"| {summary.get('coherence_issues_count', 0)} "
        f"| {summary.get('effectiveness_entries_count', 0)} |\n"
    )
    content = content.rstrip("\n") + "\n" + row

    manifest_path.write_text(content)


# ---------------------------------------------------------------------------
# Strategy synthesizer (LRNG-06)
# ---------------------------------------------------------------------------


def run_synthesis(agent_id: str = AGENT_ID, today: datetime = None) -> dict:
    """Run on-demand strategy synthesis across all context files.

    This is the single entry point (LRNG-06: manual trigger). It:
    1. Detects contradictions within and across files
    2. Audits stale entries
    3. Identifies high-confidence insights
    4. Summarizes effectiveness data
    5. Checks cross-file coherence

    Writes all findings to _learning/synthesis-report.md via append_entry.
    Updates _learning/_learning-manifest.md with run timestamp and counts.

    CRITICAL: Never calls append_entry on any file that does not start
    with '_learning/'.

    Returns dict with counts and report file path.
    """
    today = today or datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # Ensure learning directory exists
    learning_dir = context_utils.CONTEXT_ROOT / "_learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    # 1. Contradictions (within + across files)
    all_contradictions = []
    for fname in _get_context_files():
        try:
            within = detect_contradictions_in_file(fname, agent_id=agent_id)
            all_contradictions.extend(within)
        except Exception:
            continue

    # Cross-file contradictions
    try:
        across = detect_contradictions_across_files(agent_id=agent_id)
        all_contradictions.extend(across)
    except Exception:
        pass

    # 2. Stale entries audit
    stale_entries = _audit_stale_entries(agent_id=agent_id, today=today)

    # 3. High-confidence insights
    high_conf = _find_high_confidence_insights(agent_id=agent_id, today=today)

    # 4. Effectiveness summary
    effectiveness = _read_effectiveness_data(agent_id=agent_id)

    # 5. Cross-file coherence
    coherence_issues = _check_cross_file_coherence(agent_id=agent_id)

    # Format synthesis report content
    content_lines = []

    # Section 1: Contradictions
    content_lines.append("- ## Contradictions Found")
    if all_contradictions:
        for c in all_contradictions:
            ea = c["entry_a"]
            eb = c["entry_b"]
            content_lines.append(
                f"- [{c['file']}] topic='{c['topic']}' "
                f"| A: {ea['date']}/{ea['source']} '{ea['content_summary'][:80]}' "
                f"| B: {eb['date']}/{eb['source']} '{eb['content_summary'][:80]}' "
                f"(sim={c['similarity']})"
            )
    else:
        content_lines.append("- No contradictions detected")

    # Section 2: Stale entries
    content_lines.append("- ## Stale Entries Audit")
    if stale_entries:
        for s in stale_entries:
            content_lines.append(
                f"- [{s['file']}] {s['date']}/{s['source']} "
                f"detail='{s['detail']}' status={s['staleness']} "
                f"age={s['age_days']}d"
            )
    else:
        content_lines.append("- No stale entries found")

    # Section 3: High-confidence insights
    content_lines.append("- ## High-Confidence Insights")
    if high_conf:
        for h in high_conf:
            content_lines.append(
                f"- [{h['file']}] {h['date']}/{h['source']} "
                f"detail='{h['detail']}' score={h['composite_score']} "
                f"evidence={h['evidence_count']} diversity={h['source_diversity']}"
            )
    else:
        content_lines.append("- No entries meet high-confidence bar")

    # Section 4: Effectiveness summary
    content_lines.append("- ## Effectiveness Summary")
    if effectiveness:
        for e in effectiveness:
            status = "SUPPRESSED" if e["suppressed"] else "active"
            content_lines.append(
                f"- tactic='{e['tactic']}' score={e['score']} "
                f"sample_size={e['sample_size']} status={status}"
            )
    else:
        content_lines.append("- No effectiveness data available")

    # Section 5: Cross-file coherence
    content_lines.append("- ## Cross-File Coherence")
    if coherence_issues:
        for ci in coherence_issues:
            content_lines.append(f"- {ci['issue']}")
    else:
        content_lines.append("- No coherence issues detected")

    # Write to _learning/synthesis-report.md (LRNG-07: staging area only)
    report_file = "_learning/synthesis-report.md"
    entry_dict = {
        "date": date_str,
        "source": agent_id,
        "detail": f"synthesis-run-{date_str}",
        "content": content_lines,
        "evidence_count": 1,
        "confidence": "medium",
    }
    append_entry(
        file=report_file,
        entry=entry_dict,
        source=agent_id,
        agent_id=agent_id,
    )

    # Build summary
    summary = {
        "contradictions_count": len(all_contradictions),
        "stale_count": len(stale_entries),
        "high_confidence_count": len(high_conf),
        "coherence_issues_count": len(coherence_issues),
        "effectiveness_entries_count": len(effectiveness),
        "report_file": report_file,
    }

    # Update manifest
    _update_learning_manifest(summary, today=today)

    return summary


# ---------------------------------------------------------------------------
# Health monitoring (LRNG-08)
# ---------------------------------------------------------------------------


def check_synthesizer_health(
    agent_id: str = AGENT_ID, today: datetime = None
) -> dict:
    """Check the health of the learning engine synthesizer.

    Returns a dict with:
    - status: "UNINITIALIZED", "OK", "WARNING", or "CRITICAL"
    - message: human-readable description
    - days_since: days since last synthesis run (if applicable)
    - last_run: date of last run (if applicable)
    - days_remaining: grace period days remaining (if applicable)
    """
    today = today or datetime.now()
    manifest_path = context_utils.CONTEXT_ROOT / "_learning" / "_learning-manifest.md"

    if not manifest_path.exists():
        return {
            "status": "UNINITIALIZED",
            "message": "Learning engine not yet initialized",
        }

    content = manifest_path.read_text()

    # Parse initialized date
    init_match = re.search(r"\*initialized: ([^*]+)\*", content)
    initialized = None
    if init_match:
        try:
            initialized = datetime.strptime(init_match.group(1).strip(), "%Y-%m-%d")
        except ValueError:
            pass

    # Parse last_synthesis_run
    run_match = re.search(r"\*last_synthesis_run: ([^*]+)\*", content)
    last_run = None
    if run_match:
        run_str = run_match.group(1).strip()
        if run_str != "None":
            try:
                last_run = datetime.strptime(run_str, "%Y-%m-%d")
            except ValueError:
                pass

    # No synthesis run yet
    if last_run is None:
        if initialized:
            days_since_init = (today - initialized).days
            if days_since_init <= HEALTH_GRACE_DAYS:
                remaining = HEALTH_GRACE_DAYS - days_since_init
                return {
                    "status": "OK",
                    "message": "Within initialization grace period",
                    "days_remaining": remaining,
                }
            else:
                return {
                    "status": "WARNING",
                    "message": "No synthesis run since initialization",
                }
        return {
            "status": "WARNING",
            "message": "No synthesis run since initialization",
        }

    # Compute days since last run
    days_since = (today - last_run).days
    last_run_str = last_run.strftime("%Y-%m-%d")

    if days_since > HEALTH_CRITICAL_DAYS:
        return {
            "status": "CRITICAL",
            "message": f"Synthesis overdue by {days_since - HEALTH_CRITICAL_DAYS} days",
            "days_since": days_since,
            "last_run": last_run_str,
        }
    elif days_since > HEALTH_WARNING_DAYS:
        return {
            "status": "WARNING",
            "message": f"Synthesis due ({days_since} days since last run)",
            "days_since": days_since,
            "last_run": last_run_str,
        }
    else:
        return {
            "status": "OK",
            "message": "Synthesizer healthy",
            "days_since": days_since,
            "last_run": last_run_str,
        }
