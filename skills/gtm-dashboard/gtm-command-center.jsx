import { useState, useMemo, useCallback, useEffect } from "react";

// ══════════════════════════════════════════════════════
// DATA LOADING — loads from persistent storage if available,
// falls back to sample data for demo/preview mode.
//
// In production, generate_dashboard.py writes JSON data to
// persistent storage keys. This React component reads them.
//
// To populate: run /dashboard or /leads-pipeline. The Python
// scripts call window.storage.set() or write to the master XLSX
// which generate_dashboard.py reads and pushes to storage.
//
// Storage keys:
//   gtm:pipeline_runs   — array of run objects
//   gtm:scored_companies — array of company objects
//   gtm:outreach_log    — array of outreach records
//   gtm:last_updated    — ISO timestamp of last data refresh
// ══════════════════════════════════════════════════════

const SAMPLE_PIPELINE_RUNS = [
  { id: "run_001", date: "2026-03-03", source: "MIT Alumni Directory", source_url: "https://alum.mit.edu/directory", filters: "Industry: Construction, Location: US", people_scraped: 312, duplicates_removed: 18, unique_companies: 87, scored: 87, strong_fit: 9, moderate_fit: 14, low_fit: 38, no_fit: 26, contacted: 19, replied: 2, meetings: 1, csv_path: "~/Downloads/leads_scored_2026-03-03.csv", status: "complete", duration_min: 185 },
  { id: "run_002", date: "2026-02-28", source: "ENR Top 400 Contractors", source_url: "https://enr.com/toplists/2026-top-400", filters: "Revenue: $10M-$200M", people_scraped: 156, duplicates_removed: 4, unique_companies: 52, scored: 52, strong_fit: 6, moderate_fit: 11, low_fit: 22, no_fit: 13, contacted: 14, replied: 3, meetings: 1, csv_path: "~/Downloads/leads_scored_2026-02-28.csv", status: "complete", duration_min: 112 },
  { id: "run_003", date: "2026-02-20", source: "LinkedIn Sales Nav Export", source_url: "https://linkedin.com/sales", filters: "Title: VP Operations, Industry: Construction", people_scraped: 89, duplicates_removed: 7, unique_companies: 34, scored: 34, strong_fit: 3, moderate_fit: 8, low_fit: 15, no_fit: 8, contacted: 9, replied: 1, meetings: 1, csv_path: "~/Downloads/leads_scored_2026-02-20.csv", status: "complete", duration_min: 78 },
];

const SAMPLE_SCORED_COMPANIES = [
  { company: "Meridian Construction", score: 92, tier: "Strong Fit", employees: "45", location: "Boston, MA", contacted: true, replied: false, meeting: false, dm_name: "Sarah Chen", dm_title: "VP Operations", run_id: "run_001", reasoning: "45-person GC in Boston running 12 simultaneous commercial projects. Team page shows 8 PMs and no field trade staff — confirms they coordinate subs. Hiring 3 PMs on LinkedIn suggests manual admin strain.", website: "meridian-construction.com" },
  { company: "Atlas Group", score: 87, tier: "Strong Fit", employees: "120", location: "Chicago, IL", contacted: true, replied: false, meeting: false, dm_name: "Mike Torres", dm_title: "Director of Risk", run_id: "run_001", reasoning: "120-person GC expanding to 3 new markets this year. Risk management team of 4 people managing 200+ subs. No compliance software mentioned anywhere on site.", website: "atlasgroup.com" },
  { company: "Keystone Civil", score: 89, tier: "Strong Fit", employees: "80", location: "Dallas, TX", contacted: true, replied: true, meeting: true, dm_name: "Amanda Price", dm_title: "COO", run_id: "run_002", reasoning: "Fast-growing civil contractor, 80 employees. Recently won $45M highway project requiring 60+ subs. Blog post mentions 'compliance headaches' directly.", website: "keystonecivil.com" },
  { company: "Pacific Builders", score: 83, tier: "Strong Fit", employees: "45", location: "San Francisco, CA", contacted: true, replied: false, meeting: false, dm_name: "James Liu", dm_title: "CEO", run_id: "run_001", reasoning: "Owner-led GC, grew from 20 to 45 this year. Portfolio shows 6 active mixed-use projects. No tech stack visible — likely still on spreadsheets.", website: "pacificbuilders.com" },
  { company: "Titan Works", score: 91, tier: "Strong Fit", employees: "95", location: "Atlanta, GA", contacted: true, replied: true, meeting: false, dm_name: "Brian Foster", dm_title: "VP Operations", run_id: "run_002", reasoning: "95-person GC with DOT certification. Manages 150+ subs across Southeast. Careers page shows 'compliance coordinator' role open — clear pain signal.", website: "titanworks.com" },
  { company: "Clearpath GC", score: 85, tier: "Strong Fit", employees: "50", location: "Charlotte, NC", contacted: true, replied: true, meeting: true, dm_name: "Sarah Kim", dm_title: "Director of Ops", run_id: "run_003", reasoning: "50-person GC specializing in healthcare construction. HIPAA + insurance compliance overlap creates double burden. Currently tracking COIs in Excel per their LinkedIn post.", website: "clearpathgc.com" },
  { company: "Summit Infrastructure", score: 76, tier: "Strong Fit", employees: "65", location: "Seattle, WA", contacted: true, replied: false, meeting: false, dm_name: "Rachel Ward", dm_title: "Operations Manager", run_id: "run_001", reasoning: "Infrastructure-focused GC, 65 employees. 6 open PM roles on LinkedIn signal rapid growth. No vendor management page on site.", website: "summitinfra.com" },
  { company: "Bridgepoint Construction", score: 78, tier: "Strong Fit", employees: "70", location: "Houston, TX", contacted: true, replied: false, meeting: false, dm_name: "Carlos Ruiz", dm_title: "COO", run_id: "run_003", reasoning: "70-person GC in Houston, heavy industrial + commercial mix. Manages 100+ subs. Recent expansion to Austin market.", website: "bridgepointconstruction.com" },
  { company: "Cornerstone Development", score: 71, tier: "Moderate Fit", employees: "30", location: "Denver, CO", contacted: true, replied: true, meeting: true, dm_name: "David Park", dm_title: "VP Construction", run_id: "run_001", reasoning: "30-person developer-builder doing both residential and commercial. Interesting because they self-perform some trades and sub the rest.", website: "cornerstonedev.com" },
  { company: "Redwood Construction", score: 68, tier: "Moderate Fit", employees: "25", location: "Portland, OR", contacted: true, replied: false, meeting: false, dm_name: "Lisa Chang", dm_title: "Safety Director", run_id: "run_002", reasoning: "25-person GC with excellent safety record. Compliance is split between safety (Lisa) and admin. Likely under-tooled on insurance side.", website: "redwoodconst.com" },
  { company: "Ironclad Contractors", score: 58, tier: "Moderate Fit", employees: "40", location: "Miami, FL", contacted: true, replied: true, meeting: false, dm_name: "Nina Patel", dm_title: "Project Director", run_id: "run_002", reasoning: "40-person GC in South Florida. Good size fit but currently using Procore for project management. May see compliance as 'solved' even if it's not.", website: "ironclad.com" },
  { company: "Apex Engineering", score: 63, tier: "Moderate Fit", employees: "55", location: "Austin, TX", contacted: true, replied: false, meeting: false, dm_name: "Tom Martinez", dm_title: "COO", run_id: "run_002", reasoning: "Engineering-first firm, 55 employees. Works with 50+ subs. Good fit signals but email bounced — need to find correct contact.", website: "apexeng.com" },
  { company: "Beacon Properties", score: 54, tier: "Moderate Fit", employees: "20", location: "Phoenix, AZ", contacted: true, replied: false, meeting: false, dm_name: "Alex Rivera", dm_title: "Head of Construction", run_id: "run_002", reasoning: "Property developer with in-house construction arm, 20 people. Smaller than ideal but recent hotel project suggests growing complexity.", website: "beaconprop.com" },
  { company: "NorthStar Builders", score: 66, tier: "Moderate Fit", employees: "28", location: "Minneapolis, MN", contacted: true, replied: false, meeting: false, dm_name: "Julie Adams", dm_title: "Project Manager", run_id: "run_003", reasoning: "28-person residential/light commercial GC. Growing fast in Twin Cities market. May outgrow current manual processes soon.", website: "northstarbuilders.com" },
  { company: "Zenith Builders", score: 52, tier: "Moderate Fit", employees: "35", location: "Nashville, TN", contacted: false, replied: false, meeting: false, dm_name: "Karen O'Brien", dm_title: "Compliance Manager", run_id: "run_002", reasoning: "35-person GC, but already has a dedicated compliance manager. May already have a system in place. Skipped — competitor confirmed.", website: "zenithbuilders.com" },
  { company: "Vanguard Civil", score: 42, tier: "Low Fit", employees: "15", location: "Richmond, VA", contacted: false, replied: false, meeting: false, dm_name: "", dm_title: "", run_id: "run_001", reasoning: "15-person civil contractor. Too small for our minimum viable customer size.", website: "" },
  { company: "Prism Development", score: 38, tier: "Low Fit", employees: "12", location: "Tampa, FL", contacted: false, replied: false, meeting: false, dm_name: "", dm_title: "", run_id: "run_001", reasoning: "12-person developer. Primarily residential. Not enough sub complexity.", website: "" },
  { company: "Granite Solutions", score: 22, tier: "No Fit", employees: "8", location: "Boise, ID", contacted: false, replied: false, meeting: false, dm_name: "", dm_title: "", run_id: "run_002", reasoning: "8-person firm. Sole proprietor with mostly W2 employees. No sub management need.", website: "" },
];

const SAMPLE_OUTREACH_LOG = [
  { date: "2026-03-04", company: "Meridian Construction", contact: "Sarah Chen", title: "VP Operations", email: "schen@meridian.com", linkedin: "linkedin.com/in/sarachen", channel: "gmail", status: "Sent", follow_up_date: "2026-03-11", follow_up_status: "Pending", notes: "", email_subject: "Quick question about Meridian's sub compliance", email_body: "Hi Sarah,\n\nNoticed Meridian is running 12 simultaneous commercial projects with 8 PMs and growing — that's impressive scale.\n\nAt that volume, most GCs I talk to say tracking sub insurance certificates becomes a full-time job nobody wants. We built a tool that automates COI collection, tracks expirations, and flags gaps before they become project delays.\n\nWould it make sense to chat for 15 minutes this week?\n\n— Sharan, Lumif.ai", linkedin_dm: "Hi Sarah — saw Meridian is scaling fast with 12 active projects. We help GCs automate sub compliance tracking so your PMs aren't buried in COI spreadsheets. Curious if this resonates?", score: 92, tier: "Strong Fit" },
  { date: "2026-03-04", company: "Meridian Construction", contact: "Sarah Chen", title: "VP Operations", email: "", linkedin: "linkedin.com/in/sarachen", channel: "linkedin", status: "Sent", follow_up_date: "2026-03-11", follow_up_status: "Pending", notes: "", email_subject: "", email_body: "", linkedin_dm: "Hi Sarah — saw Meridian is scaling fast with 12 active projects. We help GCs automate sub compliance tracking so your PMs aren't buried in COI spreadsheets. Curious if this resonates?", score: 92, tier: "Strong Fit" },
  { date: "2026-03-04", company: "Atlas Group", contact: "Mike Torres", title: "Director of Risk", email: "mtorres@atlasgroup.com", linkedin: "linkedin.com/in/miketorres", channel: "gmail", status: "Sent", follow_up_date: "2026-03-11", follow_up_status: "Pending", notes: "", email_subject: "Atlas Group's expansion + compliance automation", email_body: "Hi Mike,\n\nYour recent expansion to 3 new markets caught my eye — managing sub compliance across regions is one of the hardest things to scale.\n\nWith 200+ subs and a 4-person risk team, I'd guess a good chunk of time goes to chasing certificates and checking expirations. We've helped similar-sized GCs cut that by 80%.\n\nWorth a quick conversation?\n\n— Sharan, Lumif.ai", linkedin_dm: "Hi Mike — noticed Atlas just expanded to 3 new markets. Managing sub compliance across regions with 200+ subs is brutal. We automate the COI tracking piece. Worth chatting?", score: 87, tier: "Strong Fit" },
  { date: "2026-03-04", company: "Atlas Group", contact: "Mike Torres", title: "Director of Risk", email: "", linkedin: "linkedin.com/in/miketorres", channel: "linkedin", status: "Sent", follow_up_date: "2026-03-11", follow_up_status: "Pending", notes: "", email_subject: "", email_body: "", linkedin_dm: "Hi Mike — noticed Atlas just expanded to 3 new markets. Managing sub compliance across regions with 200+ subs is brutal. We automate the COI tracking piece. Worth chatting?", score: 87, tier: "Strong Fit" },
  { date: "2026-03-03", company: "Pacific Builders", contact: "James Liu", title: "CEO", email: "jliu@pacificbuilders.com", linkedin: "", channel: "gmail", status: "Sent", follow_up_date: "2026-03-10", follow_up_status: "Pending", notes: "", email_subject: "Pacific Builders + automated COI tracking", email_body: "Hi James,\n\nSaw your team grew from 20 to 45 this year — congrats. That kind of growth usually means the manual spreadsheet for tracking sub insurance breaks around project #4.\n\nWe built an AI tool that handles COI collection, renewal tracking, and compliance gaps automatically. Saves most GCs about 15 hours/week.\n\nCurious if this is a pain you're feeling yet?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 83, tier: "Strong Fit" },
  { date: "2026-03-03", company: "Summit Infrastructure", contact: "Rachel Ward", title: "Operations Manager", email: "rward@summitinfra.com", linkedin: "linkedin.com/in/rachelward", channel: "gmail", status: "Sent", follow_up_date: "2026-03-10", follow_up_status: "Pending", notes: "", email_subject: "Sub compliance at Summit's scale", email_body: "Hi Rachel,\n\nYour careers page shows 6 open PM roles — that growth pace is exciting but usually means compliance processes need to scale too.\n\nWe help infrastructure GCs automate sub insurance tracking so your ops team doesn't become the bottleneck. Would love to hear how you're handling it today.\n\n15 min this week?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 76, tier: "Strong Fit" },
  { date: "2026-03-03", company: "Cornerstone Development", contact: "David Park", title: "VP Construction", email: "dpark@cornerstonedev.com", linkedin: "linkedin.com/in/davidpark", channel: "gmail", status: "Sent", follow_up_date: "2026-03-10", follow_up_status: "Done", notes: "Replied — interested, booked demo for 3/14", email_subject: "Quick question for David", email_body: "Hi David,\n\nNoticed Cornerstone manages both residential and commercial projects — curious if your sub compliance process differs between the two?\n\nMost builder-developers I talk to end up with two different tracking systems and twice the headache. We consolidate that into one automated workflow.\n\nWorth exploring?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 71, tier: "Moderate Fit" },
  { date: "2026-03-02", company: "Redwood Construction", contact: "Lisa Chang", title: "Safety Director", email: "lchang@redwoodconst.com", linkedin: "", channel: "gmail", status: "Sent", follow_up_date: "2026-03-09", follow_up_status: "Pending", notes: "", email_subject: "Redwood's safety compliance process", email_body: "Hi Lisa,\n\nYour safety record is impressive — wondering if the insurance compliance side gets the same attention or if it's still running on manual processes?\n\nWe see a lot of safety-first GCs where the COI tracking hasn't caught up with the safety protocols. Happy to share what we're seeing.\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 68, tier: "Moderate Fit" },
  { date: "2026-03-02", company: "Apex Engineering", contact: "Tom Martinez", title: "COO", email: "tmartinez@apexeng.com", linkedin: "linkedin.com/in/tommartinez", channel: "gmail", status: "Failed", follow_up_date: "", follow_up_status: "Not Needed", notes: "Email bounced — try LinkedIn instead", email_subject: "Apex's subcontractor management", email_body: "Hi Tom,\n\nSaw Apex works with 50+ subs across your projects — that's a lot of COIs to track. Curious how your team handles renewals and expiration gaps?\n\nWe automate that entire workflow for engineering firms your size.\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 63, tier: "Moderate Fit" },
  { date: "2026-03-02", company: "Ironclad Contractors", contact: "Nina Patel", title: "Project Director", email: "npatel@ironclad.com", linkedin: "linkedin.com/in/ninapatel", channel: "gmail", status: "Sent", follow_up_date: "2026-03-09", follow_up_status: "Not Needed", notes: "Replied — not interested right now, using Procore for everything", email_subject: "Ironclad + compliance automation", email_body: "Hi Nina,\n\nYour portfolio shows impressive large-scale commercial work in South Florida. At that project size, sub compliance usually becomes a bottleneck around the 30-sub mark.\n\nWe built a purpose-built compliance tool that goes deeper than what project management platforms offer. Worth a look?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 58, tier: "Moderate Fit" },
  { date: "2026-03-01", company: "Beacon Properties", contact: "Alex Rivera", title: "Head of Construction", email: "arivera@beacon.com", linkedin: "", channel: "gmail", status: "Sent", follow_up_date: "2026-03-07", follow_up_status: "Pending", notes: "", email_subject: "Beacon's sub tracking process", email_body: "Hi Alex,\n\nYour recent hotel project in downtown looks great — managing sub compliance across hospitality builds has some unique insurance requirements.\n\nWe help construction teams automate the entire COI lifecycle. Happy to share how it works for developer-builders.\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 54, tier: "Moderate Fit" },
  { date: "2026-02-28", company: "Keystone Civil", contact: "Amanda Price", title: "COO", email: "aprice@keystonecivil.com", linkedin: "linkedin.com/in/amandaprice", channel: "gmail", status: "Sent", follow_up_date: "2026-03-06", follow_up_status: "Done", notes: "Replied instantly — demo done, proposal sent. Very interested.", email_subject: "Keystone's $45M highway project + sub compliance", email_body: "Hi Amanda,\n\nCongrats on the $45M highway win — that's going to mean 60+ subs to manage. Your blog mentioned 'compliance headaches' and that's literally what we solve.\n\nWe automate COI tracking, flag gaps before they delay the project, and give you a real-time compliance dashboard.\n\n15 min this week to show you?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 89, tier: "Strong Fit" },
  { date: "2026-02-28", company: "Titan Works", contact: "Brian Foster", title: "VP Operations", email: "bfoster@titanworks.com", linkedin: "linkedin.com/in/brianfoster", channel: "gmail", status: "Sent", follow_up_date: "2026-03-06", follow_up_status: "Done", notes: "Replied — interested but wants to revisit in Q2 after current project wraps", email_subject: "Titan Works + compliance at DOT scale", email_body: "Hi Brian,\n\nWith 150+ subs and DOT certification requirements, I'd guess your compliance coordinator spends most of their time chasing certificates rather than actually managing risk.\n\nWe automate that collection and tracking process. Most similar-sized GCs save 20+ hours per week.\n\nWorth a quick conversation?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 91, tier: "Strong Fit" },
  { date: "2026-02-22", company: "Clearpath GC", contact: "Sarah Kim", title: "Director of Ops", email: "skim@clearpathgc.com", linkedin: "linkedin.com/in/sarahkim", channel: "gmail", status: "Sent", follow_up_date: "2026-02-28", follow_up_status: "Done", notes: "Replied — booked call, now in pilot program", email_subject: "Healthcare construction + COI compliance", email_body: "Hi Sarah,\n\nSaw your LinkedIn post about tracking COIs in Excel for your healthcare projects — that resonated. The HIPAA + insurance compliance overlap makes it especially painful.\n\nWe built a tool specifically for this. Would love to show you how it handles the healthcare construction use case.\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 85, tier: "Strong Fit" },
  { date: "2026-02-22", company: "Bridgepoint Construction", contact: "Carlos Ruiz", title: "COO", email: "cruiz@bridgepoint.com", linkedin: "linkedin.com/in/carlosruiz", channel: "gmail", status: "Sent", follow_up_date: "2026-02-28", follow_up_status: "Pending", notes: "", email_subject: "Bridgepoint's multi-market expansion", email_body: "Hi Carlos,\n\nBridgepoint's expansion from Houston to Austin is exciting — but managing sub compliance across markets adds a layer of complexity most teams underestimate.\n\nWe help GCs centralize their COI tracking across locations. Happy to share how.\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 78, tier: "Strong Fit" },
  { date: "2026-02-22", company: "NorthStar Builders", contact: "Julie Adams", title: "Project Manager", email: "jadams@northstarbuilders.com", linkedin: "linkedin.com/in/julieadams", channel: "gmail", status: "Sent", follow_up_date: "2026-02-28", follow_up_status: "Pending", notes: "", email_subject: "NorthStar's growth in Twin Cities", email_body: "Hi Julie,\n\nNorthStar's growth in the Twin Cities market is impressive. As you scale past 30 employees, the sub compliance tracking usually becomes the first thing that breaks.\n\nWe automate that before it becomes a problem. Worth exploring?\n\n— Sharan, Lumif.ai", linkedin_dm: "", score: 66, tier: "Moderate Fit" },
];

const TODAY = "2026-03-04";
const parseD = d => new Date(d + "T00:00:00");
const dAgo = d => Math.floor((parseD(TODAY) - parseD(d)) / 86400000);
const overdue = d => d && d <= TODAY;
const pct = (n, d) => d > 0 ? Math.round(n / d * 100) : 0;

const TIER = {
  "Strong Fit":   { bar: "#EF4444", bg: "#FEE2E2", text: "#991B1B" },
  "Moderate Fit":  { bar: "#F59E0B", bg: "#FEF3C7", text: "#92400E" },
  "Low Fit":      { bar: "#3B82F6", bg: "#DBEAFE", text: "#1E40AF" },
  "No Fit":       { bar: "#D1D5DB", bg: "#F3F4F6", text: "#6B7280" },
  "Unscored":     { bar: "#9CA3AF", bg: "#F9FAFB", text: "#9CA3AF" },
};

const M = { fontFamily: "'JetBrains Mono','Fira Code','SF Mono',monospace" };
const Sf = { fontFamily: "'Instrument Sans','Satoshi',system-ui,sans-serif" };

function Badge({ children, bg, color }) {
  return <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 3, background: bg, color, ...M, display: "inline-block" }}>{children}</span>;
}

function StatusBadge({ contacted, replied, meeting }) {
  if (meeting) return <Badge bg="#064E3B" color="#34D399">Meeting</Badge>;
  if (replied) return <Badge bg="#1E1B4B" color="#A78BFA">Replied</Badge>;
  if (contacted) return <Badge bg="#172554" color="#60A5FA">Sent</Badge>;
  return <Badge bg="#1F1F1F" color="#666">Not sent</Badge>;
}

function TierDot({ tier, score }) {
  const t = TIER[tier] || TIER.Pass;
  return (
    <div style={{ width: 34, height: 34, borderRadius: "50%", background: "#0D0D0D", border: `2px solid ${t.bar}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: t.bar, ...M, flexShrink: 0 }}>{score}</div>
  );
}

function MessageBlock({ label, icon, content, subject }) {
  if (!content) return null;
  return (
    <div style={{ background: "#0A0A0A", border: "1px solid #1F1F1F", borderRadius: 8, padding: "12px 16px", marginTop: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8, ...M }}>{icon} {label}</div>
      {subject && <div style={{ fontSize: 12, fontWeight: 600, color: "#CCC", marginBottom: 6 }}>Subject: {subject}</div>}
      <div style={{ fontSize: 12, color: "#999", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{content}</div>
    </div>
  );
}

export default function GTMDashboard() {
  const [tab, setTab] = useState("overview");
  const [runFilter, setRunFilter] = useState(null);
  const [tierFilter, setTierFilter] = useState("all");
  const [expandedRow, setExpandedRow] = useState(null);
  const [peopleSortBy, setPeopleSortBy] = useState("date");
  const [peopleSortDir, setPeopleSortDir] = useState("desc");
  const [dataSource, setDataSource] = useState("loading"); // "loading" | "live" | "sample"
  const [lastUpdated, setLastUpdated] = useState(null);

  // ── Live data state (loaded from persistent storage) ──
  const [PIPELINE_RUNS, setPipelineRuns] = useState(SAMPLE_PIPELINE_RUNS);
  const [SCORED_COMPANIES, setScoredCompanies] = useState(SAMPLE_SCORED_COMPANIES);
  const [OUTREACH_LOG, setOutreachLog] = useState(SAMPLE_OUTREACH_LOG);

  // ── Load from JSON data file (primary) or persistent storage (secondary) ──
  useEffect(() => {
    async function loadData() {
      // Strategy 1: Try JSON file produced by generate_dashboard.py
      //   Located at ~/.claude/gtm-stack/gtm-dashboard-data.json
      //   When running as an artifact, this is fetched via relative path or absolute URL
      const jsonPaths = [
        "./gtm-dashboard-data.json",
        "../gtm-dashboard-data.json",
        "/gtm-dashboard-data.json",
      ];

      for (const path of jsonPaths) {
        try {
          const resp = await fetch(path);
          if (resp.ok) {
            const data = await resp.json();
            if (data.pipeline_runs) setPipelineRuns(data.pipeline_runs);
            if (data.scored_companies) setScoredCompanies(data.scored_companies);
            if (data.outreach_log) setOutreachLog(data.outreach_log);
            if (data.last_updated) setLastUpdated(data.last_updated);
            setDataSource("live");
            return; // Success — stop trying other sources
          }
        } catch (e) {
          // File not found at this path, try next
        }
      }

      // Strategy 2: Try window.storage (Claude artifact persistent storage)
      if (window.storage) {
        try {
          const [runsResult, companiesResult, outreachResult, updatedResult] = await Promise.all([
            window.storage.get("gtm:pipeline_runs").catch(() => null),
            window.storage.get("gtm:scored_companies").catch(() => null),
            window.storage.get("gtm:outreach_log").catch(() => null),
            window.storage.get("gtm:last_updated").catch(() => null),
          ]);

          const hasData = runsResult?.value || companiesResult?.value || outreachResult?.value;

          if (hasData) {
            if (runsResult?.value) setPipelineRuns(JSON.parse(runsResult.value));
            if (companiesResult?.value) setScoredCompanies(JSON.parse(companiesResult.value));
            if (outreachResult?.value) setOutreachLog(JSON.parse(outreachResult.value));
            if (updatedResult?.value) setLastUpdated(updatedResult.value);
            setDataSource("live");
            return;
          }
        } catch (err) {
          console.error("Storage load failed:", err);
        }
      }

      // Strategy 3: Fall back to sample data
      setDataSource("sample");
    }
    loadData();
  }, []);

  const stats = useMemo(() => {
    const totalPeople = PIPELINE_RUNS.reduce((s, r) => s + r.people_scraped, 0);
    const hot = SCORED_COMPANIES.filter(c => c.tier === "Strong Fit");
    const warm = SCORED_COMPANIES.filter(c => c.tier === "Moderate Fit");
    const cool = SCORED_COMPANIES.filter(c => c.tier === "Low Fit");
    const pass = SCORED_COMPANIES.filter(c => c.tier === "No Fit");
    const contacted = SCORED_COMPANIES.filter(c => c.contacted);
    const replied = SCORED_COMPANIES.filter(c => c.replied);
    const meetings = SCORED_COMPANIES.filter(c => c.meeting);
    const sentMsgs = OUTREACH_LOG.filter(o => o.status === "Sent");
    const failedMsgs = OUTREACH_LOG.filter(o => o.status === "Failed");
    const fuDueMap = new Map();
    OUTREACH_LOG.filter(o => o.follow_up_status === "Pending" && overdue(o.follow_up_date))
      .forEach(o => { const k = o.contact + "|" + o.company; if (!fuDueMap.has(k)) fuDueMap.set(k, o); });
    const actions = [];
    SCORED_COMPANIES.filter(c => c.tier === "Strong Fit" && !c.contacted).forEach(c => actions.push({ type: "strong", p: 0, d: c }));
    [...fuDueMap.values()].forEach(o => actions.push({ type: "fu", p: 1, d: o }));
    failedMsgs.forEach(o => actions.push({ type: "fail", p: 2, d: o }));
    SCORED_COMPANIES.filter(c => c.tier === "Moderate Fit" && !c.contacted).forEach(c => actions.push({ type: "moderate", p: 3, d: c }));
    actions.sort((a, b) => a.p - b.p);
    return { totalPeople, totalCo: SCORED_COMPANIES.length, hot, warm, cool, pass, contacted, replied, meetings, sentMsgs, failedMsgs, followUpsDue: [...fuDueMap.values()], actions };
  }, []);

  const people = useMemo(() => {
    const map = new Map();
    OUTREACH_LOG.forEach(o => {
      const key = `${o.contact}|${o.company}`;
      if (!map.has(key)) {
        const co = SCORED_COMPANIES.find(c => c.company === o.company);
        map.set(key, { contact: o.contact, title: o.title || co?.dm_title || "", company: o.company, email: o.email, linkedin: o.linkedin, score: o.score || co?.score || 0, tier: o.tier || co?.tier || "Moderate Fit", location: co?.location || "", employees: co?.employees || "", reasoning: co?.reasoning || "", firstDate: o.date, messages: [], status: "Sent", hasReply: false, hasMeeting: co?.meeting || false, followUpDue: false });
      }
      const p = map.get(key);
      p.messages.push(o);
      if (o.date < p.firstDate) p.firstDate = o.date;
      if (o.notes && /replied|booked|demo|meeting|interested|pilot/i.test(o.notes)) p.hasReply = true;
      if (o.notes && /booked|demo|meeting|pilot|call scheduled/i.test(o.notes)) p.hasMeeting = true;
      if (o.status === "Failed") p.status = "Failed";
      if (o.follow_up_status === "Pending" && overdue(o.follow_up_date)) p.followUpDue = true;
    });
    return [...map.values()];
  }, []);

  const sortedPeople = useMemo(() => {
    const list = [...people];
    const dir = peopleSortDir === "desc" ? -1 : 1;
    list.sort((a, b) => {
      if (peopleSortBy === "date") return dir * (a.firstDate > b.firstDate ? 1 : -1);
      if (peopleSortBy === "score") return dir * (a.score - b.score);
      if (peopleSortBy === "company") return dir * a.company.localeCompare(b.company);
      if (peopleSortBy === "status") {
        const sa = a.hasMeeting ? 0 : a.hasReply ? 1 : a.followUpDue ? 2 : 3;
        const sb = b.hasMeeting ? 0 : b.hasReply ? 1 : b.followUpDue ? 2 : 3;
        return dir * (sa - sb);
      }
      return 0;
    });
    return list;
  }, [people, peopleSortBy, peopleSortDir]);

  const toggleSort = useCallback((col) => {
    if (peopleSortBy === col) setPeopleSortDir(d => d === "desc" ? "asc" : "desc");
    else { setPeopleSortBy(col); setPeopleSortDir("desc"); }
  }, [peopleSortBy]);

  const funnel = [
    { label: "People Scraped", value: stats.totalPeople, color: "#6B7280" },
    { label: "Companies", value: stats.totalCo, color: "#374151" },
    { label: "Strong + Moderate Fit", value: stats.hot.length + stats.warm.length, color: "#F59E0B" },
    { label: "Contacted", value: stats.contacted.length, color: "#3B82F6" },
    { label: "Replied", value: stats.replied.length, color: "#8B5CF6" },
    { label: "Meetings", value: stats.meetings.length, color: "#059669" },
  ];
  const maxF = funnel[0].value || 1;

  const filteredCo = useMemo(() => {
    let list = [...SCORED_COMPANIES];
    if (tierFilter !== "all") list = list.filter(c => c.tier === tierFilter);
    if (runFilter) list = list.filter(c => c.run_id === runFilter);
    return list.sort((a, b) => b.score - a.score);
  }, [tierFilter, runFilter]);

  const SA = ({ col }) => {
    if (peopleSortBy !== col) return <span style={{ color: "#333", marginLeft: 2 }}>↕</span>;
    return <span style={{ color: "#EF4444", marginLeft: 2 }}>{peopleSortDir === "desc" ? "↓" : "↑"}</span>;
  };

  return (
    <div style={{ ...Sf, background: "#0A0A0A", minHeight: "100vh", color: "#E5E5E5" }}>
      <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ background: "#111", borderBottom: "1px solid #222", padding: "20px 28px" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#EF4444", letterSpacing: "0.12em", textTransform: "uppercase", ...M }}>GTM Stack</div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: "#FAFAFA", margin: "4px 0 0", letterSpacing: "-0.02em" }}>Command Center</h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {dataSource === "sample" && (
              <span style={{ fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 4, background: "#332A10", color: "#F59E0B", ...M }}>SAMPLE DATA</span>
            )}
            {dataSource === "live" && lastUpdated && (
              <span style={{ fontSize: 10, color: "#555", ...M }}>updated {lastUpdated}</span>
            )}
            {stats.actions.length > 0 && (
              <button onClick={() => setTab("actions")} style={{ background: "#EF4444", color: "white", padding: "6px 16px", borderRadius: 6, fontSize: 12, fontWeight: 700, border: "none", ...M, cursor: "pointer" }}>
                {stats.actions.length} action{stats.actions.length !== 1 ? "s" : ""}
              </button>
            )}
            <span style={{ fontSize: 12, color: "#666", ...M }}>{TODAY}</span>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "0 28px 60px" }}>
        {/* Tabs */}
        <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #222", margin: "0 0 28px", overflowX: "auto" }}>
          {[
            { id: "overview", label: "Overview" },
            { id: "actions", label: "Actions", count: stats.actions.length },
            { id: "people", label: "People" },
            { id: "pipeline", label: "Runs" },
            { id: "companies", label: "Companies" },
          ].map(t => (
            <button key={t.id} onClick={() => { setTab(t.id); if (t.id !== "companies") setRunFilter(null); }} style={{
              padding: "14px 18px", fontSize: 13, fontWeight: tab === t.id ? 700 : 400,
              color: tab === t.id ? "#FAFAFA" : "#666", background: "none", border: "none",
              borderBottom: `2px solid ${tab === t.id ? "#EF4444" : "transparent"}`,
              ...Sf, display: "flex", alignItems: "center", gap: 6, marginBottom: -1, whiteSpace: "nowrap", cursor: "pointer",
            }}>
              {t.label}
              {t.count > 0 && <span style={{ background: "#EF4444", color: "white", fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 8, ...M }}>{t.count}</span>}
            </button>
          ))}
        </div>

        {/* ═══ OVERVIEW ═══ */}
        {tab === "overview" && (
          <div>
            <div style={{ marginBottom: 32 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 16, ...M }}>Pipeline Funnel</div>
              {funnel.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
                  <div style={{ width: 120, fontSize: 12, color: "#888", textAlign: "right", flexShrink: 0 }}>{s.label}</div>
                  <div style={{ flex: 1, height: 28, background: "#1A1A1A", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ width: `${Math.max(pct(s.value, maxF), 2)}%`, height: "100%", background: s.color, borderRadius: 4, opacity: 0.85 }} />
                  </div>
                  <div style={{ width: 50, fontSize: 14, fontWeight: 700, color: s.color, textAlign: "right", ...M }}>{s.value}</div>
                  <div style={{ width: 44, fontSize: 10, color: "#555", textAlign: "right", ...M }}>{i > 0 ? pct(s.value, funnel[i - 1].value) + "%" : ""}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(155px, 1fr))", gap: 10, marginBottom: 32 }}>
              {[
                { l: "Pipeline Runs", v: PIPELINE_RUNS.length, s: `${stats.totalPeople} people scraped`, c: "#666" },
                { l: "Companies Scored", v: stats.totalCo, s: `${stats.hot.length} strong · ${stats.warm.length} moderate`, c: "#F59E0B" },
                { l: "Contacted", v: stats.contacted.length, s: `${stats.sentMsgs.length} messages sent`, c: "#3B82F6" },
                { l: "Reply Rate", v: `${pct(stats.replied.length, stats.contacted.length)}%`, s: `${stats.replied.length} of ${stats.contacted.length}`, c: "#8B5CF6" },
                { l: "Meetings", v: stats.meetings.length, s: `${pct(stats.meetings.length, stats.contacted.length)}% conversion`, c: "#059669" },
                { l: "Needs Action", v: stats.actions.length, s: stats.actions.length ? "tap Actions tab" : "all clear", c: stats.actions.length ? "#EF4444" : "#333" },
              ].map((s, i) => (
                <div key={i} style={{ background: "#111", border: "1px solid #1F1F1F", borderRadius: 8, padding: "16px 18px", position: "relative" }}>
                  <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: s.c, borderRadius: "8px 0 0 8px" }} />
                  <div style={{ fontSize: 26, fontWeight: 700, color: s.c, lineHeight: 1, ...M }}>{s.v}</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#CCC", marginTop: 6 }}>{s.l}</div>
                  <div style={{ fontSize: 11, color: "#555", marginTop: 2, ...M }}>{s.s}</div>
                </div>
              ))}
            </div>

            <div style={{ marginBottom: 32 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 14, ...M }}>Score Distribution</div>
              <div style={{ display: "flex", gap: 8 }}>
                {[{ t: "Strong Fit", n: stats.hot.length }, { t: "Moderate Fit", n: stats.warm.length }, { t: "Low Fit", n: stats.cool.length }, { t: "No Fit", n: stats.pass.length }].map(d => (
                  <div key={d.t} onClick={() => { setTab("companies"); setTierFilter(d.t); }} style={{
                    flex: Math.max(pct(d.n, stats.totalCo), 8), background: "#111", border: "1px solid #1F1F1F", borderRadius: 8,
                    padding: "14px 16px", textAlign: "center", position: "relative", overflow: "hidden", minWidth: 60, cursor: "pointer",
                  }}>
                    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 3, background: TIER[d.t].bar }} />
                    <div style={{ fontSize: 22, fontWeight: 700, color: TIER[d.t].bar, ...M }}>{d.n}</div>
                    <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{d.t}</div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", ...M }}>Recent Runs</div>
                <button onClick={() => setTab("pipeline")} style={{ fontSize: 12, color: "#EF4444", background: "none", border: "none", cursor: "pointer", ...Sf }}>View all →</button>
              </div>
              {PIPELINE_RUNS.slice(0, 3).map(r => (
                <div key={r.id} onClick={() => { setTab("companies"); setRunFilter(r.id); setTierFilter("all"); }}
                  style={{ background: "#111", border: "1px solid #1F1F1F", borderRadius: 8, padding: "14px 18px", cursor: "pointer", display: "flex", alignItems: "center", gap: 16, marginBottom: 8 }}>
                  <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#1A1A1A", border: "1px solid #333", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#059669", ...M, flexShrink: 0 }}>{r.strong_fit}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#E5E5E5" }}>{r.source}</div>
                    <div style={{ fontSize: 11, color: "#555", marginTop: 2, ...M }}>{r.date} · {r.people_scraped} people → {r.unique_companies} co → {r.strong_fit} strong fit</div>
                  </div>
                  <div style={{ display: "flex", gap: 12, flexShrink: 0 }}>
                    {[["sent", r.contacted, "#3B82F6"], ["replied", r.replied, "#8B5CF6"], ["mtg", r.meetings, "#059669"]].map(([l, v, c]) => (
                      <div key={l} style={{ textAlign: "center" }}><div style={{ fontSize: 14, fontWeight: 700, color: c, ...M }}>{v}</div><div style={{ fontSize: 9, color: "#555" }}>{l}</div></div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ ACTIONS ═══ */}
        {tab === "actions" && (
          <div>
            {stats.actions.length === 0 ? (
              <div style={{ textAlign: "center", padding: "60px 20px" }}>
                <div style={{ fontSize: 40, opacity: 0.3, marginBottom: 12 }}>✓</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#888" }}>All clear</div>
              </div>
            ) : stats.actions.map((a, i) => {
              const isCo = a.type === "strong" || a.type === "moderate";
              const d = a.d;
              const cfg = { strong: { icon: "🔥", bg: "#1C0A0A", bd: "#3B1111" }, fu: { icon: "⏰", bg: "#1A1208", bd: "#332A10" }, fail: { icon: "⚠", bg: "#1A1005", bd: "#33200A" }, moderate: { icon: "☀", bg: "#1A1508", bd: "#332A10" } }[a.type];
              return (
                <div key={i} style={{ background: cfg.bg, border: `1px solid ${cfg.bd}`, borderRadius: 8, padding: "14px 18px", display: "flex", gap: 14, alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ fontSize: 18, marginTop: 2, flexShrink: 0 }}>{cfg.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: "#E5E5E5" }}>{d.company}</span>
                      {isCo && <span style={{ fontSize: 12, fontWeight: 700, color: TIER[d.tier]?.bar, ...M }}>{d.score}</span>}
                    </div>
                    <div style={{ fontSize: 12, color: "#888", marginTop: 3 }}>{isCo ? `${d.dm_name}, ${d.dm_title} · ${d.location}` : `${d.contact} · ${d.channel}`}</div>
                    <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                      {a.type === "strong" ? "Strong Fit — not yet contacted" : a.type === "moderate" ? "Moderate Fit — not yet contacted" :
                        a.type === "fu" ? `Follow-up overdue ${dAgo(d.follow_up_date)}d` : `Failed: ${d.notes || "unknown"}`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ═══ PEOPLE ═══ */}
        {tab === "people" && (
          <div>
            <div style={{ fontSize: 11, color: "#555", marginBottom: 16, ...M }}>{people.length} contacts reached · click any row to see full emails + DMs sent</div>

            <div style={{ overflowX: "auto" }}>
              {/* Table header */}
              <div style={{ display: "grid", gridTemplateColumns: "38px 1.2fr 1fr 52px 82px 76px 1.3fr", gap: 8, padding: "10px 16px", background: "#111", borderRadius: "8px 8px 0 0", border: "1px solid #1F1F1F", alignItems: "center", minWidth: 700 }}>
                {[
                  { col: null, label: "" },
                  { col: "contact", label: "Contact" },
                  { col: "company", label: "Company" },
                  { col: "score", label: "Score" },
                  { col: "status", label: "Status" },
                  { col: "date", label: "Sent" },
                  { col: null, label: "Subject / Channel" },
                ].map((h, i) => (
                  <div key={i} onClick={h.col ? () => toggleSort(h.col) : undefined}
                    style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.06em", textTransform: "uppercase", cursor: h.col ? "pointer" : "default", userSelect: "none", ...M }}>
                    {h.label}{h.col && <SA col={h.col} />}
                  </div>
                ))}
              </div>

              {/* Rows */}
              {sortedPeople.map((p, i) => {
                const isExp = expandedRow === `${p.contact}|${p.company}`;
                const key = `${p.contact}|${p.company}`;
                const channels = [...new Set(p.messages.map(m => m.channel))];
                const latestSubject = p.messages.find(m => m.email_subject)?.email_subject || "";
                const latestNote = p.messages.find(m => m.notes)?.notes || "";

                return (
                  <div key={key}>
                    <div onClick={() => setExpandedRow(isExp ? null : key)} style={{
                      display: "grid", gridTemplateColumns: "38px 1.2fr 1fr 52px 82px 76px 1.3fr", gap: 8, padding: "11px 16px",
                      background: isExp ? "#151515" : i % 2 === 0 ? "#0D0D0D" : "#111",
                      border: "1px solid #1F1F1F", borderTop: "none", cursor: "pointer", alignItems: "center", minWidth: 700,
                    }}>
                      <TierDot tier={p.tier} score={p.score} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#E5E5E5", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.contact}</div>
                        <div style={{ fontSize: 11, color: "#555", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.title}</div>
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 12, color: "#CCC", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.company}</div>
                        <div style={{ fontSize: 10, color: "#444", ...M }}>{p.location}</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: (TIER[p.tier] || TIER.Pass).bar, ...M }}>{p.score}</span>
                      </div>
                      <div>
                        {p.hasMeeting ? <Badge bg="#064E3B" color="#34D399">Meeting</Badge> :
                          p.hasReply ? <Badge bg="#1E1B4B" color="#A78BFA">Replied</Badge> :
                            p.followUpDue ? <Badge bg="#3B1111" color="#F87171">Follow up</Badge> :
                              p.status === "Failed" ? <Badge bg="#3B1111" color="#F87171">Failed</Badge> :
                                <Badge bg="#172554" color="#60A5FA">Sent</Badge>}
                      </div>
                      <div style={{ fontSize: 11, color: "#555", ...M }}>{p.firstDate}</div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 11, color: "#888", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{latestSubject}</div>
                        <div style={{ display: "flex", gap: 4, marginTop: 3 }}>
                          {channels.map(ch => (
                            <span key={ch} style={{ fontSize: 9, background: "#1A1A1A", color: "#666", padding: "1px 6px", borderRadius: 3, ...M }}>
                              {ch === "linkedin" ? "in" : "✉"} {ch}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Expanded: full messages */}
                    {isExp && (
                      <div style={{ background: "#0D0D0D", border: "1px solid #333", borderTop: "none", padding: "16px 20px" }}>
                        {/* Contact details bar */}
                        <div style={{ display: "flex", gap: 20, marginBottom: 14, flexWrap: "wrap", fontSize: 11, color: "#666" }}>
                          {p.email && <span>✉ <span style={{ color: "#999", ...M }}>{p.email}</span></span>}
                          {p.linkedin && <span>in <span style={{ color: "#999", ...M }}>{p.linkedin}</span></span>}
                          {p.employees && <span>👥 {p.employees} emp</span>}
                        </div>

                        {/* Fit reasoning */}
                        {p.reasoning && (
                          <div style={{ background: "#111", border: "1px solid #1F1F1F", borderRadius: 8, padding: "12px 16px", marginBottom: 12 }}>
                            <div style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6, ...M }}>Why {p.company} scored {p.score}</div>
                            <div style={{ fontSize: 12, color: "#888", lineHeight: 1.5 }}>{p.reasoning}</div>
                          </div>
                        )}

                        {/* Outcome note */}
                        {latestNote && (
                          <div style={{ background: "#0A1A0A", border: "1px solid #1A331A", borderRadius: 8, padding: "10px 16px", marginBottom: 12 }}>
                            <div style={{ fontSize: 12, color: "#34D399", fontWeight: 600 }}>📝 {latestNote}</div>
                          </div>
                        )}

                        {/* Each message */}
                        <div style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 10, ...M }}>Messages Sent ({p.messages.length})</div>
                        {p.messages.map((msg, mi) => (
                          <div key={mi} style={{ marginBottom: 14 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                              <span style={{
                                width: 18, height: 18, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center",
                                fontSize: 10, fontWeight: 700,
                                background: msg.status === "Sent" ? "#064E3B" : "#3B1111", color: msg.status === "Sent" ? "#34D399" : "#F87171",
                              }}>{msg.status === "Sent" ? "✓" : "✕"}</span>
                              <span style={{ fontSize: 11, color: "#888", ...M }}>{msg.channel}</span>
                              <span style={{ fontSize: 11, color: "#333" }}>·</span>
                              <span style={{ fontSize: 11, color: "#555", ...M }}>{msg.date}</span>
                              <span style={{ fontSize: 11, color: msg.status === "Sent" ? "#34D399" : "#F87171", fontWeight: 600 }}>{msg.status}</span>
                              {msg.follow_up_status === "Pending" && msg.follow_up_date && (
                                <span style={{ fontSize: 10, color: overdue(msg.follow_up_date) ? "#F87171" : "#555", ...M }}>
                                  {overdue(msg.follow_up_date) ? "⚠ " : ""}f/u: {msg.follow_up_date}
                                </span>
                              )}
                            </div>
                            {msg.email_body && <MessageBlock label="Email" icon="✉" content={msg.email_body} subject={msg.email_subject} />}
                            {msg.linkedin_dm && <MessageBlock label="LinkedIn DM" icon="in" content={msg.linkedin_dm} />}
                            {msg.notes && <div style={{ fontSize: 11, color: "#059669", marginTop: 6, fontStyle: "italic" }}>📝 {msg.notes}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {people.length === 0 && (
              <div style={{ textAlign: "center", padding: "40px", background: "#111", border: "1px solid #1F1F1F", borderRadius: "0 0 8px 8px", color: "#444", fontSize: 13 }}>
                No outreach sent yet. Run /outbound-messenger to start.
              </div>
            )}
          </div>
        )}

        {/* ═══ PIPELINE RUNS ═══ */}
        {tab === "pipeline" && (
          <div>
            {PIPELINE_RUNS.map(r => (
              <div key={r.id} style={{ background: "#111", border: "1px solid #1F1F1F", borderRadius: 10, overflow: "hidden", marginBottom: 12 }}>
                <div onClick={() => { setTab("companies"); setRunFilter(r.id); setTierFilter("all"); }}
                  style={{ padding: "18px 20px", display: "flex", gap: 16, alignItems: "flex-start", cursor: "pointer" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#E5E5E5" }}>{r.source}</div>
                    <div style={{ fontSize: 11, color: "#555", marginTop: 4, ...M }}>{r.date} · {r.filters}</div>
                    <div style={{ fontSize: 12, color: "#888", marginTop: 8 }}>{r.csv_path}</div>
                  </div>
                  <div style={{ fontSize: 11, color: "#444", ...M }}>{r.duration_min}m</div>
                </div>
                <div style={{ background: "#0D0D0D", padding: "14px 20px", borderTop: "1px solid #1A1A1A", display: "flex", gap: 20, flexWrap: "wrap" }}>
                  {[["Scraped", r.people_scraped, "#666"], ["Companies", r.unique_companies, "#888"], ["Strong Fit", r.strong_fit, "#EF4444"], ["Moderate Fit", r.moderate_fit, "#F59E0B"], ["Low Fit", r.low_fit, "#3B82F6"], ["No Fit", r.no_fit, "#555"], ["Contacted", r.contacted, "#3B82F6"], ["Replied", r.replied, "#8B5CF6"], ["Meetings", r.meetings, "#059669"]].map(([l, v, c]) => (
                    <div key={l} style={{ textAlign: "center", minWidth: 48 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: c, ...M }}>{v || 0}</div>
                      <div style={{ fontSize: 9, color: "#444", marginTop: 1 }}>{l}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ═══ COMPANIES ═══ */}
        {tab === "companies" && (
          <div>
            {runFilter && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <span style={{ fontSize: 12, color: "#888" }}>Showing: <strong style={{ color: "#E5E5E5" }}>{PIPELINE_RUNS.find(r => r.id === runFilter)?.source}</strong></span>
                <button onClick={() => setRunFilter(null)} style={{ fontSize: 11, color: "#EF4444", background: "none", border: "1px solid #333", borderRadius: 4, padding: "2px 8px", cursor: "pointer", ...M }}>× clear</button>
              </div>
            )}
            <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
              {["all", "Strong Fit", "Moderate Fit", "Low Fit", "No Fit"].map(t => (
                <button key={t} onClick={() => setTierFilter(t)} style={{
                  padding: "5px 14px", fontSize: 11, fontWeight: tierFilter === t ? 700 : 400,
                  background: tierFilter === t ? "#222" : "transparent", color: tierFilter === t ? "#E5E5E5" : "#555",
                  border: `1px solid ${tierFilter === t ? "#444" : "#222"}`, borderRadius: 5, cursor: "pointer", ...M,
                }}>{t === "all" ? "All" : t}</button>
              ))}
              <button onClick={() => {
                const headers = ["Company","Score","Tier","DM Name","DM Title","Location","Employees","Contacted","Replied","Meeting"];
                const csvRows = [headers.join(",")];
                filteredCo.forEach(c => {
                  csvRows.push([c.company, c.score, c.tier, c.dm_name, c.dm_title, c.location, c.employees,
                    c.contacted ? "Yes" : "No", c.replied ? "Yes" : "No", c.meeting ? "Yes" : "No"
                  ].map(v => `"${String(v || "").replace(/"/g, '""')}"`).join(","));
                });
                const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url;
                a.download = `gtm_companies_${tierFilter.replace(/\s+/g, "_").toLowerCase()}_${new Date().toISOString().slice(0,10)}.csv`;
                a.click(); URL.revokeObjectURL(url);
              }} style={{
                marginLeft: "auto", padding: "5px 14px", fontSize: 11, fontWeight: 600,
                background: "transparent", color: "#3B82F6", border: "1px solid #222", borderRadius: 5, cursor: "pointer", ...M,
              }}>↓ Export CSV</button>
            </div>

            {filteredCo.map(c => {
              const ts = TIER[c.tier] || TIER.Pass;
              const isExp = expandedRow === `co_${c.company}`;
              const ors = OUTREACH_LOG.filter(o => o.company === c.company);
              return (
                <div key={c.company} style={{ background: "#111", border: `1px solid ${isExp ? "#333" : "#1F1F1F"}`, borderRadius: 8, overflow: "hidden", marginBottom: 6 }}>
                  <div onClick={() => setExpandedRow(isExp ? null : `co_${c.company}`)}
                    style={{ padding: "12px 18px", display: "flex", alignItems: "center", gap: 14, cursor: "pointer" }}>
                    <TierDot tier={c.tier} score={c.score} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: "#E5E5E5" }}>{c.company}</span>
                        <StatusBadge contacted={c.contacted} replied={c.replied} meeting={c.meeting} />
                      </div>
                      <div style={{ fontSize: 11, color: "#555", marginTop: 3 }}>{c.dm_name ? `${c.dm_name}, ${c.dm_title}` : "No DM"} · {c.employees || "?"} emp · {c.location}</div>
                    </div>
                    <span style={{ fontSize: 12, color: "#444", transform: isExp ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▾</span>
                  </div>
                  {isExp && (
                    <div style={{ borderTop: "1px solid #1A1A1A", padding: "14px 18px", background: "#0D0D0D" }}>
                      {c.reasoning && (
                        <div style={{ fontSize: 12, color: "#888", lineHeight: 1.5, marginBottom: 12, padding: "10px 14px", background: "#111", borderRadius: 6, border: "1px solid #1F1F1F" }}>
                          <span style={{ fontSize: 10, fontWeight: 600, color: "#555", ...M }}>FIT REASONING: </span>{c.reasoning}
                        </div>
                      )}
                      {ors.length > 0 ? ors.map((o, oi) => (
                        <div key={oi} style={{ marginBottom: 12 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, ...M, marginBottom: 4 }}>
                            <span style={{
                              width: 18, height: 18, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 700,
                              background: o.status === "Sent" ? "#064E3B" : "#3B1111", color: o.status === "Sent" ? "#34D399" : "#F87171",
                            }}>{o.status === "Sent" ? "✓" : "✕"}</span>
                            <span style={{ color: "#888" }}>{o.channel}</span>
                            <span style={{ color: "#333" }}>·</span>
                            <span style={{ color: "#555" }}>{o.date}</span>
                          </div>
                          {o.email_body && <MessageBlock label="Email" icon="✉" content={o.email_body} subject={o.email_subject} />}
                          {o.linkedin_dm && <MessageBlock label="LinkedIn DM" icon="in" content={o.linkedin_dm} />}
                          {o.notes && <div style={{ fontSize: 11, color: "#059669", marginTop: 4, fontStyle: "italic" }}>📝 {o.notes}</div>}
                        </div>
                      )) : <div style={{ fontSize: 12, color: "#444" }}>No outreach sent yet.</div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div style={{ textAlign: "center", padding: "40px 0 0", fontSize: 11, color: "#333", ...M }}>
          GTM Stack · {PIPELINE_RUNS.length} runs · {SCORED_COMPANIES.length} companies · {OUTREACH_LOG.length} messages · {people.length} contacts
        </div>
      </div>
      <style>{`* { box-sizing: border-box; } button:hover { opacity: 0.85; }`}</style>
    </div>
  );
}
