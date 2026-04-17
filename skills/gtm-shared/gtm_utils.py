#!/usr/bin/env python3
"""
Shared utilities for the GTM Stack.

Provides:
  - backup_file(): Create timestamped backups before overwriting critical files
  - atomic_write_csv(): Write CSV files atomically (tmp + rename)
  - normalize_company_key(): Consistent company name normalization across all skills
  - sanitize_for_script_embed(): Safe JSON embedding in HTML <script> tags
  - ensure_utf8_csv(): Detect and convert CSV encoding to UTF-8
"""

import csv
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timedelta
from glob import glob


# ═══════════════════════════════════════════
# BACKUP
# ═══════════════════════════════════════════

def backup_file(filepath, max_backups=5):
    """
    Create a timestamped backup of a file before overwriting.
    Keeps at most `max_backups` recent backups. Silently returns if file doesn't exist.

    Returns:
        str: path to backup file, or None if source didn't exist
    """
    if not os.path.exists(filepath):
        return None

    backup_dir = os.path.join(os.path.dirname(filepath), ".backups")
    os.makedirs(backup_dir, exist_ok=True)

    base = os.path.basename(filepath)
    name, ext = os.path.splitext(base)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{name}_{timestamp}{ext}")

    shutil.copy2(filepath, backup_path)

    # Prune old backups — keep only the most recent `max_backups`
    pattern = os.path.join(backup_dir, f"{name}_*{ext}")
    existing = sorted(glob(pattern), reverse=True)
    for old_backup in existing[max_backups:]:
        try:
            os.remove(old_backup)
        except OSError:
            pass

    return backup_path


# ═══════════════════════════════════════════
# ATOMIC FILE WRITES
# ═══════════════════════════════════════════

def atomic_write(filepath, content, mode="w", encoding="utf-8"):
    """
    Write content to a file atomically using tmp + rename.
    Prevents corruption from interrupted writes.
    """
    dir_path = os.path.dirname(filepath) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, mode, encoding=encoding if "b" not in mode else None) as f:
            f.write(content)
        os.replace(tmp_path, filepath)  # atomic on POSIX
    except Exception:
        # Clean up temp file on failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(filepath, data, indent=2):
    """Write JSON atomically."""
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    atomic_write(filepath, content)


def atomic_write_csv(filepath, rows, fieldnames, quoting=csv.QUOTE_ALL):
    """
    Write CSV atomically. Writes to a temp file first, then renames.

    Args:
        filepath: destination path
        rows: list of dicts
        fieldnames: list of column names
        quoting: csv quoting mode (default QUOTE_ALL)
    """
    dir_path = os.path.dirname(filepath) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames,
                                    quoting=quoting, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_append_csv(filepath, record, fieldnames, quoting=csv.QUOTE_ALL):
    """
    Append a single row to a CSV file. Creates the file with headers if it doesn't exist.
    Uses file-level locking (fcntl) on Linux/macOS to prevent concurrent writes.
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    file_exists = os.path.exists(filepath)

    import fcntl
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            writer = csv.DictWriter(f, fieldnames=fieldnames,
                                    quoting=quoting, extrasaction="ignore")
            if not file_exists or os.path.getsize(filepath) == 0:
                writer.writeheader()
            writer.writerow(record)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ═══════════════════════════════════════════
# COMPANY NAME NORMALIZATION
# ═══════════════════════════════════════════

# Common suffixes to strip for matching (not for display)
_COMPANY_SUFFIXES = re.compile(
    r',?\s*\b(inc|llc|l\.l\.c|ltd|co|corp|corporation|incorporated|plc|lp|llp)\b\.?',
    re.IGNORECASE
)

def normalize_company_key(name):
    """
    Produce a stable, normalized key for company name matching.

    Rules:
      - Strip leading/trailing whitespace
      - Lowercase
      - Remove common suffixes (Inc, LLC, Ltd, etc.)
      - Collapse multiple spaces
      - Strip non-alphanumeric except spaces

    Used for dedup and cross-file matching — never for display.

    Examples:
        "Atlas Group, Inc." → "atlas group"
        "  Meridian Construction LLC  " → "meridian construction"
        "Keystone Civil" → "keystone civil"
    """
    if not name:
        return ""
    key = name.strip().lower()
    key = _COMPANY_SUFFIXES.sub("", key)
    key = re.sub(r'[^a-z0-9\s]', '', key)
    key = re.sub(r'\s+', ' ', key).strip()
    return key


# ═══════════════════════════════════════════
# XSS-SAFE JSON EMBEDDING
# ═══════════════════════════════════════════

def sanitize_for_script_embed(json_string):
    """
    Make a JSON string safe for embedding inside HTML <script> tags.

    Escapes:
      - </  → <\\/   (prevents </script> breakout)
      - <!--  → <\\!--  (prevents HTML comment injection)

    Always use this when embedding JSON in generate_dashboard.py.
    """
    # Escape closing script tags and HTML comments
    result = json_string.replace("</", "<\\/")
    result = result.replace("<!--", "<\\!--")
    return result


# ═══════════════════════════════════════════
# CSV ENCODING DETECTION
# ═══════════════════════════════════════════

def ensure_utf8_csv(filepath):
    """
    Detect CSV encoding and re-write as UTF-8 if needed.
    Handles Windows-1252, Latin-1, UTF-8 BOM, etc.

    Returns:
        str: the encoding that was detected (or 'utf-8' if already correct)
    """
    # Try UTF-8 first (fast path)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip BOM if present
        if content.startswith("\ufeff"):
            atomic_write(filepath, content[1:])
            return "utf-8-bom"
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Fall back to chardet if available, otherwise try common encodings
    detected_encoding = None
    try:
        import chardet
        with open(filepath, "rb") as f:
            raw = f.read()
        result = chardet.detect(raw)
        detected_encoding = result.get("encoding", "latin-1")
    except ImportError:
        # Try common fallbacks
        for enc in ["latin-1", "windows-1252", "iso-8859-1"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    content = f.read()
                detected_encoding = enc
                break
            except UnicodeDecodeError:
                continue

    if detected_encoding and detected_encoding.lower() != "utf-8":
        with open(filepath, "r", encoding=detected_encoding) as f:
            content = f.read()
        atomic_write(filepath, content)
        return detected_encoding

    return "unknown"


# ═══════════════════════════════════════════
# LINKEDIN RATE TRACKING
# ═══════════════════════════════════════════

_LI_RATE_PATH = os.path.expanduser("~/.claude/gtm-stack/linkedin-rate-tracker.json")
_LI_DAILY_LIMIT = 30   # ~150/week across 5 weekdays
_LI_WEEKLY_LIMIT = 150  # LinkedIn's connection request cap

def _load_linkedin_rate_data():
    """Load the LinkedIn rate tracker JSON. Returns dict with 'daily' dict of date->count."""
    data = {"daily": {}}
    if os.path.exists(_LI_RATE_PATH):
        try:
            with open(_LI_RATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    # Migrate old format (single date+count) to new format (daily dict)
    if "date" in data and "daily" not in data:
        old_date = data.get("date", "")
        old_count = data.get("count", 0)
        data = {"daily": {old_date: old_count} if old_date else {}}
    if "daily" not in data:
        data["daily"] = {}
    return data


def _prune_linkedin_rate_data(data):
    """Remove entries older than 7 days."""
    today = datetime.now()
    cutoff = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    data["daily"] = {d: c for d, c in data["daily"].items() if d >= cutoff}
    return data


def check_linkedin_rate(warn_threshold=20):
    """
    Check how many LinkedIn DMs/connection requests have been sent today and this week.

    Returns:
        tuple: (count_today, remaining_today, is_over_daily_limit,
                count_week, remaining_week, is_over_weekly_limit)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    data = _load_linkedin_rate_data()
    data = _prune_linkedin_rate_data(data)

    count_today = data["daily"].get(today, 0)
    remaining_today = max(0, _LI_DAILY_LIMIT - count_today)
    over_daily = count_today >= _LI_DAILY_LIMIT

    count_week = sum(data["daily"].values())
    remaining_week = max(0, _LI_WEEKLY_LIMIT - count_week)
    over_weekly = count_week >= _LI_WEEKLY_LIMIT

    return count_today, remaining_today, over_daily, count_week, remaining_week, over_weekly


def increment_linkedin_rate():
    """Record one LinkedIn DM/connection request sent. Returns updated rate tuple."""
    today = datetime.now().strftime("%Y-%m-%d")
    data = _load_linkedin_rate_data()
    data = _prune_linkedin_rate_data(data)

    data["daily"][today] = data["daily"].get(today, 0) + 1

    os.makedirs(os.path.dirname(_LI_RATE_PATH), exist_ok=True)
    atomic_write_json(_LI_RATE_PATH, data)

    return check_linkedin_rate()


# ===============================================
# EMAIL RATE TRACKING
# ===============================================

_EMAIL_RATE_PATH = os.path.expanduser("~/.claude/gtm-stack/email-rate-tracker.json")
_EMAIL_DAILY_LIMIT = 40  # Per-inbox daily limit to protect sender reputation

def check_email_rate():
    """
    Check how many emails have been sent today from the current inbox.

    Returns:
        tuple: (count_today, remaining, is_over_limit)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}

    if os.path.exists(_EMAIL_RATE_PATH):
        try:
            with open(_EMAIL_RATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if data.get("date") != today:
        data = {"date": today, "count": 0}

    count = data.get("count", 0)
    remaining = max(0, _EMAIL_DAILY_LIMIT - count)
    over_limit = count >= _EMAIL_DAILY_LIMIT

    return count, remaining, over_limit


def increment_email_rate():
    """Record one email sent. Returns updated (count, remaining, over_limit)."""
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "count": 0}

    if os.path.exists(_EMAIL_RATE_PATH):
        try:
            with open(_EMAIL_RATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if data.get("date") != today:
        data = {"date": today, "count": 0}

    data["count"] = data.get("count", 0) + 1

    os.makedirs(os.path.dirname(_EMAIL_RATE_PATH), exist_ok=True)
    atomic_write_json(_EMAIL_RATE_PATH, data)

    return check_email_rate()


# ===============================================
# TEAM EMAIL DETECTION
# ===============================================

_TEAM_EMAIL_PREFIXES = {
    'info', 'contact', 'admin', 'hello', 'support', 'team', 'office',
    'sales', 'general', 'enquiries', 'inquiries', 'risk', 'hr',
    'finance', 'billing', 'help', 'service', 'reception', 'mail',
    'department', 'dept', 'operations', 'marketing', 'communications',
}

def detect_team_email(email, contact_name=""):
    """
    Detect whether an email address belongs to a team/department rather than an individual.

    Returns:
        bool: True if the email appears to be a team/department address
    """
    if not email:
        return False
    local_part = email.split("@")[0].lower().strip()
    # Check against known team prefixes
    if local_part in _TEAM_EMAIL_PREFIXES:
        return True
    # No personal name associated + generic-looking local part
    if not contact_name.strip() and not any(c.isupper() for c in email.split("@")[0]):
        # Check if local part looks like a name (has dots/underscores separating parts)
        if "." not in local_part and "_" not in local_part:
            return True
    return False


# ═══════════════════════════════════════════
# RUN ID GENERATION
# ═══════════════════════════════════════════

def generate_run_id():
    """
    Generate a collision-resistant run ID based on timestamp.
    Format: run_20260304_143022

    Unlike sequential IDs (run_001), these won't collide if pipeline-runs.json
    is recreated or corrupted.
    """
    return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
