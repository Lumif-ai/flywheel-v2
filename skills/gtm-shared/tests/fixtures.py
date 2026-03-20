"""
Test fixtures for GTM Stack smoke tests.

Creates a complete set of test data matching the real pipeline output format.
Used by test_smoke.py to validate merge_master.py and generate_dashboard.py
without needing a live browser or real scraping.
"""

import csv
import json
import os


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixture_data")


def create_fixtures():
    """Create all fixture files. Returns the fixture directory path."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    # ── Pipeline Runs ──
    runs = [
        {
            "id": "run_20260301_100000",
            "date": "2026-03-01",
            "source": "Test Alumni Directory",
            "source_url": "https://example.com/alumni",
            "filters": "Industry: Construction",
            "people_scraped": 50,
            "duplicates_removed": 5,
            "unique_companies": 20,
            "scored": 20,
            "strong_fit": 3,
            "moderate_fit": 5,
            "low_fit": 8,
            "no_fit": 4,
            "contacted": 6,
            "replied": 2,
            "meetings": 1,
            "csv_path": os.path.join(FIXTURE_DIR, "scored_run1.csv"),
            "status": "complete",
            "duration_min": 45,
        },
        {
            "id": "run_20260302_140000",
            "date": "2026-03-02",
            "source": "Test Industry List",
            "source_url": "https://example.com/industry",
            "filters": "Revenue: $5M-$50M",
            "people_scraped": 30,
            "duplicates_removed": 2,
            "unique_companies": 10,
            "scored": 10,
            "strong_fit": 2,
            "moderate_fit": 3,
            "low_fit": 3,
            "no_fit": 2,
            "contacted": 4,
            "replied": 1,
            "meetings": 0,
            "csv_path": os.path.join(FIXTURE_DIR, "scored_run2.csv"),
            "status": "complete",
            "duration_min": 30,
        },
    ]
    with open(os.path.join(FIXTURE_DIR, "pipeline-runs.json"), "w") as f:
        json.dump(runs, f, indent=2)

    # ── Scored CSV (Run 1) — 20 companies ──
    scored_fields = [
        "Company", "Fit_Score", "Fit_Tier", "Location", "Est_Employees",
        "DM_Name", "DM_Title", "DM_LinkedIn", "Website_Found",
        "Top_Fit_Signal", "Top_Concern", "Fit_Reasoning",
        "Email_Subject", "Email_Body", "LinkedIn_DM",
    ]
    scored_run1 = [
        {"Company": "Acme Builders", "Fit_Score": "92", "Fit_Tier": "Strong Fit",
         "Location": "Boston, MA", "Est_Employees": "55",
         "DM_Name": "Jane Smith", "DM_Title": "VP Operations",
         "DM_LinkedIn": "linkedin.com/in/janesmith", "Website_Found": "acmebuilders.com",
         "Top_Fit_Signal": "Hiring 4 PMs", "Top_Concern": "",
         "Fit_Reasoning": "55-person GC, 4 open PM roles signal growth.",
         "Email_Subject": "Acme + compliance automation",
         "Email_Body": "Hi Jane, saw your growth...",
         "LinkedIn_DM": "Hi Jane — noticed Acme is hiring PMs..."},
        {"Company": "Beta Construction", "Fit_Score": "85", "Fit_Tier": "Strong Fit",
         "Location": "Chicago, IL", "Est_Employees": "80",
         "DM_Name": "Bob Jones", "DM_Title": "COO",
         "DM_LinkedIn": "linkedin.com/in/bjones", "Website_Found": "betaconstruction.com",
         "Top_Fit_Signal": "120+ subs managed", "Top_Concern": "",
         "Fit_Reasoning": "80-person GC managing 120 subs across Midwest.",
         "Email_Subject": "Beta's sub management at scale",
         "Email_Body": "Hi Bob, managing 120 subs...",
         "LinkedIn_DM": "Hi Bob — 120 subs is a lot of COIs..."},
        {"Company": "Gamma Group, Inc.", "Fit_Score": "78", "Fit_Tier": "Strong Fit",
         "Location": "Dallas, TX", "Est_Employees": "40",
         "DM_Name": "Carol Lee", "DM_Title": "Director of Ops",
         "DM_LinkedIn": "", "Website_Found": "gammagroup.com",
         "Top_Fit_Signal": "Recent $30M project win", "Top_Concern": "Small team",
         "Fit_Reasoning": "Growing fast after $30M project win.",
         "Email_Subject": "Gamma Group + compliance", "Email_Body": "Hi Carol...",
         "LinkedIn_DM": ""},
        {"Company": "Delta Services LLC", "Fit_Score": "68", "Fit_Tier": "Moderate Fit",
         "Location": "Denver, CO", "Est_Employees": "25",
         "DM_Name": "Dan Park", "DM_Title": "CEO",
         "DM_LinkedIn": "linkedin.com/in/danpark", "Website_Found": "deltaservices.com",
         "Top_Fit_Signal": "Blog mentions compliance pain",
         "Top_Concern": "Small company", "Fit_Reasoning": "25-person firm...",
         "Email_Subject": "Delta + automation", "Email_Body": "Hi Dan...",
         "LinkedIn_DM": "Hi Dan — saw your blog post..."},
        {"Company": "Epsilon Corp", "Fit_Score": "62", "Fit_Tier": "Moderate Fit",
         "Location": "Miami, FL", "Est_Employees": "35",
         "DM_Name": "Eve Wilson", "DM_Title": "Project Director",
         "DM_LinkedIn": "", "Website_Found": "epsiloncorp.com",
         "Top_Fit_Signal": "50+ subs", "Top_Concern": "Uses Procore",
         "Fit_Reasoning": "35-person GC, good size but uses Procore.",
         "Email_Subject": "Epsilon + compliance", "Email_Body": "Hi Eve...",
         "LinkedIn_DM": ""},
    ]
    # Add some Low Fit and No Fit companies to fill out the 20
    for i in range(5):
        scored_run1.append({
            "Company": f"LowFit Co {i+1}", "Fit_Score": str(35 + i * 3),
            "Fit_Tier": "Low Fit", "Location": f"City {i+1}, ST",
            "Est_Employees": str(10 + i * 5), "DM_Name": "", "DM_Title": "",
            "DM_LinkedIn": "", "Website_Found": f"lowfit{i+1}.com",
            "Top_Fit_Signal": "", "Top_Concern": "Too small",
            "Fit_Reasoning": "Below threshold.", "Email_Subject": "",
            "Email_Body": "", "LinkedIn_DM": "",
        })
    for i in range(5):
        scored_run1.append({
            "Company": f"NoFit Inc {i+1}", "Fit_Score": str(10 + i * 3),
            "Fit_Tier": "No Fit", "Location": f"Town {i+1}, ST",
            "Est_Employees": str(5 + i * 2), "DM_Name": "", "DM_Title": "",
            "DM_LinkedIn": "", "Website_Found": "",
            "Top_Fit_Signal": "", "Top_Concern": "Wrong industry",
            "Fit_Reasoning": "Not a fit.", "Email_Subject": "",
            "Email_Body": "", "LinkedIn_DM": "",
        })
    # 5 more Moderate Fit to reach 20
    for i in range(5):
        scored_run1.append({
            "Company": f"ModFit LLC {i+1}", "Fit_Score": str(55 + i * 3),
            "Fit_Tier": "Moderate Fit", "Location": f"Metro {i+1}, ST",
            "Est_Employees": str(20 + i * 10), "DM_Name": f"Contact {i+1}",
            "DM_Title": "Manager", "DM_LinkedIn": "",
            "Website_Found": f"modfit{i+1}.com", "Top_Fit_Signal": "Some potential",
            "Top_Concern": "Unverified", "Fit_Reasoning": "Moderate signals.",
            "Email_Subject": f"ModFit {i+1} + compliance",
            "Email_Body": f"Hi Contact {i+1}...", "LinkedIn_DM": "",
        })

    with open(os.path.join(FIXTURE_DIR, "scored_run1.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=scored_fields)
        w.writeheader()
        w.writerows(scored_run1)

    # ── Scored CSV (Run 2) — 10 companies, some overlap with Run 1 ──
    scored_run2 = [
        # Duplicate of Acme Builders with HIGHER score (should keep this one)
        {"Company": "Acme Builders", "Fit_Score": "95", "Fit_Tier": "Strong Fit",
         "Location": "Boston, MA", "Est_Employees": "55",
         "DM_Name": "Jane Smith", "DM_Title": "VP Operations",
         "DM_LinkedIn": "linkedin.com/in/janesmith", "Website_Found": "acmebuilders.com",
         "Top_Fit_Signal": "Hiring 4 PMs + new office", "Top_Concern": "",
         "Fit_Reasoning": "Updated: 55-person GC opening new office.",
         "Email_Subject": "Acme + compliance automation",
         "Email_Body": "Hi Jane, saw your growth...", "LinkedIn_DM": ""},
        # Duplicate of Acme with trailing space (tests normalization)
        {"Company": "Acme Builders ", "Fit_Score": "88", "Fit_Tier": "Strong Fit",
         "Location": "Boston, MA", "Est_Employees": "55",
         "DM_Name": "Jane Smith", "DM_Title": "VP Operations",
         "DM_LinkedIn": "", "Website_Found": "acmebuilders.com",
         "Top_Fit_Signal": "Hiring PMs", "Top_Concern": "",
         "Fit_Reasoning": "Duplicate with space.", "Email_Subject": "",
         "Email_Body": "", "LinkedIn_DM": ""},
        {"Company": "Zeta Engineering", "Fit_Score": "76", "Fit_Tier": "Strong Fit",
         "Location": "Austin, TX", "Est_Employees": "60",
         "DM_Name": "Frank Chen", "DM_Title": "VP Engineering",
         "DM_LinkedIn": "linkedin.com/in/frankchen", "Website_Found": "zetaeng.com",
         "Top_Fit_Signal": "DOT certified", "Top_Concern": "",
         "Fit_Reasoning": "60-person engineering firm with DOT work.",
         "Email_Subject": "Zeta + compliance", "Email_Body": "Hi Frank...",
         "LinkedIn_DM": "Hi Frank — DOT work means compliance matters..."},
    ]
    # Fill to 10
    for i in range(7):
        scored_run2.append({
            "Company": f"Run2 Co {i+1}", "Fit_Score": str(20 + i * 8),
            "Fit_Tier": "Low Fit" if i < 4 else "No Fit",
            "Location": f"Place {i+1}, ST", "Est_Employees": str(15 + i * 5),
            "DM_Name": "", "DM_Title": "", "DM_LinkedIn": "",
            "Website_Found": f"run2co{i+1}.com", "Top_Fit_Signal": "",
            "Top_Concern": "Various", "Fit_Reasoning": "Low signals.",
            "Email_Subject": "", "Email_Body": "", "LinkedIn_DM": "",
        })

    with open(os.path.join(FIXTURE_DIR, "scored_run2.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=scored_fields)
        w.writeheader()
        w.writerows(scored_run2)

    # ── Outreach Tracker ──
    tracker_fields = [
        "Date", "Company", "Contact_Name", "Title", "Email", "LinkedIn_URL",
        "Channel", "Status", "Follow_Up_Date", "Follow_Up_Status", "Notes",
        "Email_Subject", "Email_Body", "LinkedIn_DM", "Fit_Score", "Fit_Tier",
    ]
    tracker_rows = [
        {"Date": "2026-03-01", "Company": "Acme Builders", "Contact_Name": "Jane Smith",
         "Title": "VP Operations", "Email": "jsmith@acmebuilders.com", "LinkedIn_URL": "",
         "Channel": "email", "Status": "Sent", "Follow_Up_Date": "2026-03-08",
         "Follow_Up_Status": "Pending", "Notes": "",
         "Email_Subject": "Acme + compliance", "Email_Body": "Hi Jane...",
         "LinkedIn_DM": "", "Fit_Score": "92", "Fit_Tier": "Strong Fit"},
        {"Date": "2026-03-01", "Company": "Beta Construction", "Contact_Name": "Bob Jones",
         "Title": "COO", "Email": "bjones@betaconstruction.com", "LinkedIn_URL": "",
         "Channel": "email", "Status": "Sent", "Follow_Up_Date": "2026-03-08",
         "Follow_Up_Status": "Done", "Notes": "Replied — interested",
         "Email_Subject": "Beta's sub management", "Email_Body": "Hi Bob...",
         "LinkedIn_DM": "", "Fit_Score": "85", "Fit_Tier": "Strong Fit"},
        {"Date": "2026-03-02", "Company": "Gamma Group, Inc.", "Contact_Name": "Carol Lee",
         "Title": "Director of Ops", "Email": "clee@gammagroup.com", "LinkedIn_URL": "",
         "Channel": "email", "Status": "Sent", "Follow_Up_Date": "2026-03-09",
         "Follow_Up_Status": "Pending", "Notes": "",
         "Email_Subject": "Gamma + compliance", "Email_Body": "Hi Carol...",
         "LinkedIn_DM": "", "Fit_Score": "78", "Fit_Tier": "Strong Fit"},
        # Pending row (tests idempotent sending detection)
        {"Date": "2026-03-02", "Company": "Delta Services LLC", "Contact_Name": "Dan Park",
         "Title": "CEO", "Email": "dpark@deltaservices.com", "LinkedIn_URL": "",
         "Channel": "email", "Status": "Pending", "Follow_Up_Date": "",
         "Follow_Up_Status": "", "Notes": "[pending-send]",
         "Email_Subject": "Delta + automation", "Email_Body": "Hi Dan...",
         "LinkedIn_DM": "", "Fit_Score": "68", "Fit_Tier": "Moderate Fit"},
    ]

    with open(os.path.join(FIXTURE_DIR, "outreach-tracker.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=tracker_fields)
        w.writeheader()
        w.writerows(tracker_rows)

    # ── Do Not Contact ──
    dnc_fields = ["Company", "Reason", "Date_Added"]
    dnc_rows = [
        {"Company": "NoFit Inc 1", "Reason": "Competitor customer", "Date_Added": "2026-02-15"},
        {"Company": "  nofit inc 2  ", "Reason": "Requested removal", "Date_Added": "2026-02-20"},
    ]
    with open(os.path.join(FIXTURE_DIR, "do-not-contact.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=dnc_fields)
        w.writeheader()
        w.writerows(dnc_rows)

    return FIXTURE_DIR


if __name__ == "__main__":
    path = create_fixtures()
    print(f"Fixtures created in: {path}")
    for f in sorted(os.listdir(path)):
        size = os.path.getsize(os.path.join(path, f))
        print(f"  {f} ({size:,} bytes)")
