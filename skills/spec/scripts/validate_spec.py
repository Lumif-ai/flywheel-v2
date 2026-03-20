#!/usr/bin/env python3
"""
Spec Validator — Programmatic coverage and quality checking for SPEC.md files.

Parses a SPEC.md file and checks:
1. Structural completeness (required sections present)
2. Acceptance criteria coverage (every requirement has testable criteria)
3. Edge case coverage (edge cases table populated)
4. Ambiguity detection (vague language patterns)
5. Anti-requirements presence
6. Requirement ID consistency

Usage:
    python3 validate_spec.py <path-to-spec.md>
    python3 validate_spec.py <path-to-spec.md> --json     # machine-readable output
    python3 validate_spec.py <path-to-spec.md> --gaps     # also check SPEC-GAPS.md
"""

import sys
import re
import json
import os
from pathlib import Path


# Vague language patterns that signal ambiguity
VAGUE_PATTERNS = [
    (r'\bappropriate(?:ly)?\b', 'vague: "appropriately" — specify the exact behavior'),
    (r'\bshould\b', 'weak: "should" — use "must" or remove the requirement'),
    (r'\bproperly\b', 'vague: "properly" — define what proper means'),
    (r'\bgraceful(?:ly)?\b', 'vague: "gracefully" — specify what the user sees'),
    (r'\brobust\b', 'vague: "robust" — define failure modes and recovery'),
    (r'\bscalable\b', 'vague: "scalable" — specify target load/throughput'),
    (r'\bfast\b', 'vague: "fast" — specify latency target (e.g., <200ms)'),
    (r'\bsecure\b', 'vague: "secure" — specify threat model and mitigations'),
    (r'\bsimple\b', 'vague: "simple" — simple for whom? define the interaction'),
    (r'\bintuitive\b', 'vague: "intuitive" — describe the expected user flow'),
    (r'\buser[- ]friendly\b', 'vague: "user-friendly" — define specific UX criteria'),
    (r'\betc\.?\b', 'incomplete: "etc." — enumerate all items explicitly'),
    (r'\band so on\b', 'incomplete: "and so on" — enumerate all items'),
    (r'\bvarious\b', 'vague: "various" — list the specific items'),
    (r'\bhandle errors\b', 'vague: "handle errors" — specify which errors and what user sees'),
    (r'\bsupport(?:s)? multiple\b', 'vague: "support multiple" — list which ones'),
    (r'\bas needed\b', 'vague: "as needed" — define the conditions'),
    (r'\bif applicable\b', 'vague: "if applicable" — define when it applies'),
    (r'\bwhen necessary\b', 'vague: "when necessary" — define the trigger'),
    (r'\breasonable\b', 'vague: "reasonable" — specify the threshold'),
    (r'\bminimal\b', 'vague: "minimal" — quantify the minimum'),
    (r'\befficient(?:ly)?\b', 'vague: "efficiently" — specify performance target'),
]

# Required sections in a well-formed SPEC.md
REQUIRED_SECTIONS = [
    'overview',
    'core value',
    'requirements',
    'must have',
    'edge cases',
    'constraints',
]

RECOMMENDED_SECTIONS = [
    'anti-requirements',
    "won't have",
    'users & entry points',
    'open questions',
    'acceptance criteria',
]


def parse_spec(filepath):
    """Parse a SPEC.md file and extract structure."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        'filepath': filepath,
        'content': content,
        'lines': content.split('\n'),
        'sections': [],
        'requirements': [],
        'acceptance_criteria': [],
        'edge_cases': [],
        'ambiguities': [],
        'req_ids': [],
    }

    # Extract sections (h2 and h3 headings)
    for i, line in enumerate(result['lines'], 1):
        match = re.match(r'^(#{2,3})\s+(.+)', line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            result['sections'].append({
                'level': level,
                'title': title,
                'line': i,
                'title_lower': title.lower(),
            })

    # Extract requirement IDs (e.g., REQ-01, AUTH-01, etc.)
    req_pattern = re.compile(r'\*\*\[?([A-Z]+-\d+)\]?\*\*:?\s*(.+)')
    for i, line in enumerate(result['lines'], 1):
        match = req_pattern.search(line)
        if match:
            result['req_ids'].append({
                'id': match.group(1),
                'text': match.group(2).strip(),
                'line': i,
            })

    # Extract acceptance criteria (checkbox items under requirements)
    ac_pattern = re.compile(r'^\s*-\s*\[[ x]\]\s+(.+)', re.IGNORECASE)
    for i, line in enumerate(result['lines'], 1):
        match = ac_pattern.match(line)
        if match:
            result['acceptance_criteria'].append({
                'text': match.group(1).strip(),
                'line': i,
            })

    # Extract edge cases from table
    edge_pattern = re.compile(r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|')
    in_edge_section = False
    for i, line in enumerate(result['lines'], 1):
        if re.match(r'^#{2,3}\s+edge case', line, re.IGNORECASE):
            in_edge_section = True
            continue
        if in_edge_section and re.match(r'^#{2,3}\s+', line):
            in_edge_section = False
        if in_edge_section:
            match = edge_pattern.match(line)
            if match and not match.group(1).startswith('-'):
                scenario = match.group(1).strip()
                if scenario.lower() not in ('scenario', '---', ''):
                    result['edge_cases'].append({
                        'scenario': scenario,
                        'behavior': match.group(2).strip(),
                        'line': i,
                    })

    # Detect ambiguities
    for i, line in enumerate(result['lines'], 1):
        # Skip headings, code blocks, and table headers
        if line.startswith('#') or line.startswith('|--') or line.startswith('```'):
            continue
        for pattern, message in VAGUE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                result['ambiguities'].append({
                    'line': i,
                    'text': line.strip(),
                    'issue': message,
                })

    return result


def check_structure(spec):
    """Check that required sections exist."""
    findings = []
    section_titles = [s['title_lower'] for s in spec['sections']]

    for required in REQUIRED_SECTIONS:
        found = any(required in title for title in section_titles)
        if not found:
            findings.append({
                'severity': 'critical',
                'category': 'structure',
                'message': f'Missing required section: "{required}"',
                'fix': f'Add a ## {required.title()} section',
            })

    for recommended in RECOMMENDED_SECTIONS:
        found = any(recommended in title for title in section_titles)
        if not found:
            findings.append({
                'severity': 'minor',
                'category': 'structure',
                'message': f'Missing recommended section: "{recommended}"',
                'fix': f'Consider adding a ## {recommended.title()} section',
            })

    return findings


def check_acceptance_criteria(spec):
    """Check that requirements have acceptance criteria."""
    findings = []

    if not spec['req_ids']:
        findings.append({
            'severity': 'critical',
            'category': 'acceptance_criteria',
            'message': 'No requirement IDs found (expected pattern: **REQ-01**: ...)',
            'fix': 'Add structured requirement IDs to all requirements',
        })
        return findings

    # For each requirement, check if acceptance criteria follow
    for req in spec['req_ids']:
        req_line = req['line']
        # Look for checkbox items in the next 10 lines
        has_criteria = False
        for ac in spec['acceptance_criteria']:
            if req_line < ac['line'] <= req_line + 10:
                has_criteria = True
                break

        if not has_criteria:
            findings.append({
                'severity': 'major',
                'category': 'acceptance_criteria',
                'message': f'{req["id"]} (line {req_line}) has no acceptance criteria',
                'fix': f'Add testable [ ] criteria under {req["id"]}',
            })

    # Check criteria quality
    for ac in spec['acceptance_criteria']:
        text = ac['text'].lower()
        # Check for vague criteria
        for pattern, message in VAGUE_PATTERNS[:5]:  # Check most common vague patterns
            if re.search(pattern, text, re.IGNORECASE):
                findings.append({
                    'severity': 'major',
                    'category': 'acceptance_criteria',
                    'message': f'Vague acceptance criterion at line {ac["line"]}: {message}',
                    'fix': f'Make criterion testable and specific: "{ac["text"]}"',
                })
                break

    return findings


def check_edge_cases(spec):
    """Check edge case coverage."""
    findings = []

    if not spec['edge_cases']:
        findings.append({
            'severity': 'major',
            'category': 'edge_cases',
            'message': 'No edge cases defined',
            'fix': 'Add edge cases table with scenarios and expected behaviors',
        })
    elif len(spec['edge_cases']) < 3:
        findings.append({
            'severity': 'minor',
            'category': 'edge_cases',
            'message': f'Only {len(spec["edge_cases"])} edge cases defined (recommend 5+)',
            'fix': 'Consider: empty states, boundary values, concurrent access, invalid input, timeout/failure scenarios',
        })

    return findings


def check_ambiguities(spec):
    """Report detected ambiguities."""
    findings = []
    for amb in spec['ambiguities']:
        findings.append({
            'severity': 'major',
            'category': 'ambiguity',
            'message': f'Line {amb["line"]}: {amb["issue"]}',
            'fix': f'Rewrite: "{amb["text"][:80]}..."' if len(amb['text']) > 80 else f'Rewrite: "{amb["text"]}"',
        })
    return findings


def check_gaps_file(spec_path):
    """Check for SPEC-GAPS.md and report open gaps."""
    findings = []
    spec_dir = os.path.dirname(spec_path)

    # Check common locations
    gap_paths = [
        os.path.join(spec_dir, 'SPEC-GAPS.md'),
        os.path.join(spec_dir, 'specs', 'SPEC-GAPS.md'),
        os.path.join(spec_dir, '..', 'SPEC-GAPS.md'),
    ]

    gaps_file = None
    for path in gap_paths:
        if os.path.exists(path):
            gaps_file = path
            break

    if not gaps_file:
        return findings  # No gaps file, that's fine

    with open(gaps_file, 'r', encoding='utf-8') as f:
        content = f.read()

    open_gaps = re.findall(r'## (GAP-\d+) \[OPEN\]', content)
    critical_gaps = len(re.findall(r'Severity:\s*Critical.*OPEN', content, re.DOTALL))

    if open_gaps:
        findings.append({
            'severity': 'critical' if critical_gaps > 0 else 'major',
            'category': 'execution_gaps',
            'message': f'{len(open_gaps)} open execution gaps found ({critical_gaps} critical): {", ".join(open_gaps)}',
            'fix': f'Review {gaps_file} and resolve open gaps',
        })

    return findings


def compute_score(findings):
    """Compute overall spec quality score."""
    critical = sum(1 for f in findings if f['severity'] == 'critical')
    major = sum(1 for f in findings if f['severity'] == 'major')
    minor = sum(1 for f in findings if f['severity'] == 'minor')

    # Start at 10, deduct for issues
    score = 10.0
    score -= critical * 2.0
    score -= major * 0.5
    score -= minor * 0.1
    score = max(0, min(10, score))

    return round(score, 1)


def format_report(spec, findings, score, include_gaps):
    """Format findings as a readable report."""
    lines = []
    lines.append(f'# Spec Validation Report')
    lines.append(f'')
    lines.append(f'**File:** {spec["filepath"]}')
    lines.append(f'**Score:** {score}/10')
    lines.append(f'**Requirements found:** {len(spec["req_ids"])}')
    lines.append(f'**Acceptance criteria found:** {len(spec["acceptance_criteria"])}')
    lines.append(f'**Edge cases found:** {len(spec["edge_cases"])}')
    lines.append(f'**Ambiguities detected:** {sum(1 for f in findings if f["category"] == "ambiguity")}')
    lines.append(f'')

    # Group by severity
    for severity in ['critical', 'major', 'minor']:
        severity_findings = [f for f in findings if f['severity'] == severity]
        if severity_findings:
            label = {'critical': 'Critical (will cause rework)',
                     'major': 'Major (likely bugs)',
                     'minor': 'Minor (polish)'}[severity]
            lines.append(f'## {label}')
            lines.append(f'')
            for i, f in enumerate(severity_findings, 1):
                lines.append(f'{i}. **[{f["category"]}]** {f["message"]}')
                lines.append(f'   Fix: {f["fix"]}')
                lines.append(f'')

    if not findings:
        lines.append('## No issues found')
        lines.append('')
        lines.append('Spec passes all validation checks.')

    # Coverage summary
    lines.append(f'## Coverage Summary')
    lines.append(f'')
    reqs_with_ac = 0
    for req in spec['req_ids']:
        for ac in spec['acceptance_criteria']:
            if req['line'] < ac['line'] <= req['line'] + 10:
                reqs_with_ac += 1
                break

    total_reqs = len(spec['req_ids'])
    if total_reqs > 0:
        coverage = (reqs_with_ac / total_reqs) * 100
        lines.append(f'- Requirements with acceptance criteria: {reqs_with_ac}/{total_reqs} ({coverage:.0f}%)')
    else:
        lines.append(f'- Requirements with acceptance criteria: N/A (no structured requirements found)')

    lines.append(f'- Edge cases documented: {len(spec["edge_cases"])}')

    section_titles = [s['title_lower'] for s in spec['sections']]
    has_anti = any('anti' in t or "won't" in t for t in section_titles)
    lines.append(f'- Anti-requirements defined: {"Yes" if has_anti else "No"}')

    has_constraints = any('constraint' in t for t in section_titles)
    lines.append(f'- Constraints documented: {"Yes" if has_constraints else "No"}')

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 validate_spec.py <path-to-spec.md> [--json] [--gaps]')
        sys.exit(1)

    filepath = sys.argv[1]
    output_json = '--json' in sys.argv
    include_gaps = '--gaps' in sys.argv

    if not os.path.exists(filepath):
        print(f'Error: File not found: {filepath}')
        sys.exit(1)

    # Parse
    spec = parse_spec(filepath)

    # Run all checks
    findings = []
    findings.extend(check_structure(spec))
    findings.extend(check_acceptance_criteria(spec))
    findings.extend(check_edge_cases(spec))
    findings.extend(check_ambiguities(spec))

    if include_gaps:
        findings.extend(check_gaps_file(filepath))

    # Score
    score = compute_score(findings)

    if output_json:
        output = {
            'filepath': filepath,
            'score': score,
            'requirements_count': len(spec['req_ids']),
            'acceptance_criteria_count': len(spec['acceptance_criteria']),
            'edge_cases_count': len(spec['edge_cases']),
            'ambiguities_count': sum(1 for f in findings if f['category'] == 'ambiguity'),
            'findings': findings,
        }
        print(json.dumps(output, indent=2))
    else:
        report = format_report(spec, findings, score, include_gaps)
        print(report)

    # Exit code: 0 if score >= 7, 1 if below
    sys.exit(0 if score >= 7 else 1)


if __name__ == '__main__':
    main()
