---
name: flywheel
version: "1.0"
description: >
  Daily operating ritual for the founder. Shows upcoming meetings, pending tasks,
  unprocessed meetings, and outreach status. Subcommands: sync, tasks, prep, process.
  Use when user types /flywheel with or without subcommands.
allowed-tools:
  - Bash
  - Read
---

# Flywheel

Daily operating ritual. One command to see your day.

Consult @skills/flywheel/references/api-reference.md for endpoint details and response shapes.

---

## Step 0: Dependency Check and Auth

Before doing anything, verify the environment and authenticate.

### 0a. Check python3

Verify `python3` is available (used for all JSON parsing):

```bash
python3 --version 2>/dev/null || echo "MISSING"
```

If python3 is missing, stop and tell the user: "python3 is required but not found. Please install Python 3."

### 0b. Check API Token

Read the token and base URL from environment variables:

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
```

If `FLYWHEEL_API_TOKEN` is empty or not set, stop and display:

```
FLYWHEEL_API_TOKEN not set.

To get your token:
1. Open the Flywheel web app in your browser
2. Open Developer Tools (Cmd+Option+I)
3. Go to Application > Local Storage > find the sb-*-auth-token key
4. Copy the access_token value
5. Set it: export FLYWHEEL_API_TOKEN="<paste token here>"
```

### 0c. Verify Token

Call the auth endpoint to confirm the token is valid:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE/auth/me")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
```

If HTTP code is 401 or 403, stop and display: "Token expired or invalid. Please get a fresh token from the Flywheel web app (see step 0b above)."

If curl fails (non-zero exit code or no HTTP code), stop and display: "Cannot reach Flywheel API at $BASE. Is the backend running?"

---

## Error Handling

| Failure | Response |
|---------|----------|
| `FLYWHEEL_API_TOKEN` not set | Show setup instructions from Step 0b, stop |
| Token expired (401 on any call) | "Session expired. Get a fresh token from the web app." Stop all sections. |
| API unreachable (curl exit code != 0) | "Cannot reach Flywheel API at {BASE}. Is the backend running?" |
| Individual section fails (non-401) | Show "Error fetching {section} ({http_code})" for that section, continue rendering others |
| Empty section (0 items) | Show "None" -- never omit the section, never show an error |

**Critical rule:** A 401 from ANY call means the token is dead. Stop everything and show the token expiration message. Do not continue to other sections.

---

## Subcommand Routing

Parse the user's message after `/flywheel` to determine what to do:

| User says | Action |
|-----------|--------|
| `/flywheel` (no subcommand) | Show full daily brief (Section: Daily Brief below) |
| `/flywheel brief` | Show full daily brief |
| `/flywheel sync` | Granola sync flow -- see Subcommand: sync section below |
| `/flywheel tasks` | Task triage view -- see Subcommand: tasks section below |
| `/flywheel prep` | Meeting prep view -- see Subcommand: prep section below |
| `/flywheel process` | Process unprocessed meetings -- see Subcommand: process section below |

If the subcommand is not recognized, show the daily brief and list available subcommands.

---

## Daily Brief

This is the main output when the user types `/flywheel` with no subcommand (or with `brief`).

### Setup

Set auth variables for all API calls in this brief:

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
AUTH="Authorization: Bearer $TOKEN"
```

### Fetch Pattern

For EACH section below, make a separate curl call. Use this pattern for every call:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$URL")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

Then check:
1. If `HTTP_CODE` is `401` -- stop ALL sections immediately. Display: "Session expired. Get a fresh token from the web app."
2. If `HTTP_CODE` is not `200` -- display "Error fetching {section name} ({HTTP_CODE})" and continue to the next section.
3. If `HTTP_CODE` is `200` -- parse `BODY` with python3 and display the section.

### Output Format

Display the brief in this exact format:

```
== FLYWHEEL DAILY BRIEF ==
{Day of week}, {Month} {Day}, {Year}

--- UPCOMING (next 24h) ---
{upcoming meetings or "None"}

--- PENDING TASKS ({count}) ---
{tasks or "None"}

--- UNPROCESSED MEETINGS ({count}) ---
{unprocessed meetings or "None"}

--- OUTREACH ---
{outreach status or "Not configured"}

Commands: /flywheel sync | tasks | prep | process
```

### Section 1: Upcoming Meetings (next 24h)

Fetch upcoming meetings:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/meetings/?time=upcoming&limit=10")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

Parse with python3 and filter to next 24 hours. Format each meeting as:

```
{N}. [{HH:MM}] {title} - {attendee_count} attendees - {prep_or_type}
```

Where `{prep_or_type}` is:
- "Internal" if `meeting_type` is `internal`
- "Prep: {processing_status}" otherwise (e.g., "Prep: processed", "Prep: pending")

Use python3 to parse and filter:

```bash
echo "$BODY" | python3 -c "
import sys, json
from datetime import datetime, timedelta, timezone

data = json.load(sys.stdin)
meetings = data.get('meetings', [])
now = datetime.now(timezone.utc)
cutoff = now + timedelta(hours=24)

filtered = []
for m in meetings:
    md = m.get('meeting_date', '')
    if md:
        try:
            dt = datetime.fromisoformat(md.replace('Z', '+00:00'))
            if dt <= cutoff:
                filtered.append((dt, m))
        except:
            pass

filtered.sort(key=lambda x: x[0])

if not filtered:
    print('None')
else:
    for i, (dt, m) in enumerate(filtered, 1):
        time_str = dt.strftime('%H:%M')
        title = m.get('title', 'Untitled')
        attendees = m.get('attendees', [])
        att_count = len(attendees) if isinstance(attendees, list) else 0
        mtype = m.get('meeting_type', 'unknown')
        status = m.get('processing_status', 'unknown')
        if mtype == 'internal':
            prep = 'Internal'
        else:
            prep = f'Prep: {status}'
        print(f'{i}. [{time_str}] {title} - {att_count} attendees - {prep}')
"
```

If the python3 command fails or the list is empty, display "None".

### Section 2: Pending Tasks

Fetch both detected and confirmed tasks:

```bash
DETECTED_RESP=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/tasks/?status=detected&limit=20")
DETECTED_CODE=$(echo "$DETECTED_RESP" | tail -1)
DETECTED_BODY=$(echo "$DETECTED_RESP" | sed '$d')

CONFIRMED_RESP=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/tasks/?status=confirmed&limit=20")
CONFIRMED_CODE=$(echo "$CONFIRMED_RESP" | tail -1)
CONFIRMED_BODY=$(echo "$CONFIRMED_RESP" | sed '$d')
```

Check both for 401 (stop everything). If either returns non-200 (but not 401), show error for this section.

Merge detected and confirmed tasks and format each as:

```
{N}. [{PRIORITY}] {title} (from: {source}, {date}) - Skill: {suggested_skill|none}
```

For confirmed tasks, append " [Confirmed]" after the skill info.

Use python3 to merge and format:

```bash
python3 -c "
import sys, json
from datetime import datetime

detected = json.loads('''$DETECTED_BODY''')
confirmed = json.loads('''$CONFIRMED_BODY''')

tasks = []
for t in detected.get('tasks', []):
    t['_status'] = 'detected'
    tasks.append(t)
for t in confirmed.get('tasks', []):
    t['_status'] = 'confirmed'
    tasks.append(t)

if not tasks:
    print('None')
else:
    for i, t in enumerate(tasks, 1):
        priority = (t.get('priority') or 'med').upper()
        title = t.get('title', 'Untitled')
        source = t.get('source', 'unknown')
        created = t.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            date_str = dt.strftime('%b %d')
        except:
            date_str = 'unknown'
        skill = t.get('suggested_skill') or 'none'
        suffix = ' [Confirmed]' if t['_status'] == 'confirmed' else ''
        print(f'{i}. [{priority}] {title} (from: {source}, {date_str}) - Skill: {skill}{suffix}')
"
```

Display the total count in the section header: `--- PENDING TASKS ({total_detected + total_confirmed}) ---`

If no tasks, display "None".

### Section 3: Unprocessed Meetings

Fetch unprocessed (recorded) meetings:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/meetings/?processing_status=recorded&limit=10")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

Format each as:

```
{N}. {title} ({date}, {duration} min) - Status: {processing_status}
```

Use python3:

```bash
echo "$BODY" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
meetings = data.get('meetings', [])

if not meetings:
    print('None')
else:
    for i, m in enumerate(meetings, 1):
        title = m.get('title', 'Untitled')
        md = m.get('meeting_date', '')
        try:
            dt = datetime.fromisoformat(md.replace('Z', '+00:00'))
            date_str = dt.strftime('%b %d')
        except:
            date_str = 'unknown'
        duration = m.get('duration_mins', '?')
        status = m.get('processing_status', 'unknown')
        print(f'{i}. {title} ({date_str}, {duration} min) - Status: {status}')
"
```

Display the total count in the section header: `--- UNPROCESSED MEETINGS ({total}) ---`

If no meetings, display "None".

### Section 4: Outreach

Check if the outreach tracker CSV exists:

```bash
test -f ~/.claude/gtm-stack/outreach-tracker.csv && echo "EXISTS" || echo "MISSING"
```

If MISSING, display: "Not configured"

If EXISTS, display basic stats by reading the CSV with python3 (stretch goal -- "Not configured" is acceptable for v1).

### Footer

After all sections, display:

```
Commands: /flywheel sync | tasks | prep | process
```

---

## Memory

Track learned preferences to improve future briefs:

- **Time format preference:** 12h vs 24h (default: 24h HH:MM)
- **Sections of interest:** Which sections the user engages with most
- **Task priority filter:** Whether user wants to see all priorities or only high
- **Outreach tracker location:** Custom path if not at default location
- **Brief verbosity:** Whether user prefers compact or detailed output

---

## Subcommand: sync

Pull new meetings from Granola and optionally trigger processing.

### Setup

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
AUTH="Authorization: Bearer $TOKEN"
```

### Flow

**Step 1: Call sync endpoint**

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH" "$BASE/meetings/sync")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If HTTP code is 401: stop and display "Session expired. Get a fresh token from the web app."

If HTTP code is not 200: display "Sync failed ({HTTP_CODE}). Is Granola connected? Check Settings > Integrations in the web app."

**Step 2: Parse and display results**

```bash
echo "$BODY" | python3 -c "
import sys, json

data = json.load(sys.stdin)
synced = data.get('synced', 0)
skipped = data.get('skipped', 0)
already_seen = data.get('already_seen', 0)
total = data.get('total_from_provider', 0)

print('== GRANOLA SYNC ==')
print(f'Synced: {synced} new meeting(s)')
print(f'Skipped: {skipped} (rules filtered)')
print(f'Already seen: {already_seen}')
print(f'Total from Granola: {total}')

if synced > 0:
    print()
    print(f'Process {synced} new meeting(s)? Reply \"yes\" to extract intelligence.')
elif synced == 0:
    print()
    print('Already up to date.')
"
```

**Step 3: Handle user response (conversational turn)**

If the user replies yes/confirm/go/ok/sure after seeing synced > 0:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH" "$BASE/meetings/process-pending")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If HTTP code is 401: stop and display token expiration message.

If HTTP code is 200: parse and display:

```bash
echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
queued = data.get('queued', 0)
print(f'Queued {queued} meeting(s) for processing.')
"
```

If HTTP code is not 200: display "Processing failed ({HTTP_CODE})."

If the user says no/skip/cancel: display "Skipped processing." and return.

---

## Subcommand: process

Show unprocessed meetings and trigger batch or single processing.

### Setup

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
AUTH="Authorization: Bearer $TOKEN"
```

### Flow

**Step 1: Fetch unprocessed meetings**

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/meetings/?processing_status=recorded&limit=20")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If HTTP code is 401: stop and display token expiration message.
If HTTP code is not 200: display "Error fetching unprocessed meetings ({HTTP_CODE})."

**Step 2: Parse and display numbered list**

```bash
echo "$BODY" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
meetings = data.get('meetings', [])

if not meetings:
    print('No unprocessed meetings.')
    sys.exit(0)

print('== UNPROCESSED MEETINGS ==')
for i, m in enumerate(meetings, 1):
    title = m.get('title', 'Untitled')
    mid = m.get('id', '')
    md = m.get('meeting_date', '')
    try:
        dt = datetime.fromisoformat(md.replace('Z', '+00:00'))
        date_str = dt.strftime('%b %d')
    except:
        date_str = 'unknown'
    duration = m.get('duration_mins', '?')
    print(f'{i}. {title} ({date_str}, {duration} min)  [id:{mid}]')

print()
print(\"Reply 'all' to process all, or a number to process one.\")
"
```

**Important:** The `[id:{mid}]` tag at the end of each line is for Claude to track which UUID maps to which display position. Claude remembers this mapping and uses it when the user refers to items by number. Do NOT re-fetch the list when the user replies (positions might shuffle).

**Step 3: Handle user response (conversational turn)**

If user replies "all":

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH" "$BASE/meetings/process-pending")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

Parse and display:

```bash
echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
queued = data.get('queued', 0)
print(f'Queued {queued} meeting(s) for processing.')
"
```

If user replies with a number N: Map N to the meeting UUID from the displayed list (the `[id:...]` tag). Call:

```bash
MEETING_UUID="<uuid from position N>"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH" "$BASE/meetings/$MEETING_UUID/process")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If 200: display "Processing: {title}..."
If 401: token expiration message.
If not 200: display "Processing failed ({HTTP_CODE})."

---

## Subcommand: tasks

Triage detected tasks -- confirm or dismiss via conversational replies.

### Setup

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
AUTH="Authorization: Bearer $TOKEN"
```

### Flow

**Step 1: Fetch detected and confirmed tasks**

```bash
DETECTED_RESP=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/tasks/?status=detected&limit=20")
DETECTED_CODE=$(echo "$DETECTED_RESP" | tail -1)
DETECTED_BODY=$(echo "$DETECTED_RESP" | sed '$d')

CONFIRMED_RESP=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/tasks/?status=confirmed&limit=20")
CONFIRMED_CODE=$(echo "$CONFIRMED_RESP" | tail -1)
CONFIRMED_BODY=$(echo "$CONFIRMED_RESP" | sed '$d')
```

If either returns 401: stop and display token expiration message.
If either returns non-200 (but not 401): display "Error fetching tasks ({HTTP_CODE})."

**Step 2: Parse and display**

```bash
python3 -c "
import sys, json
from datetime import datetime

detected = json.loads('''$DETECTED_BODY''')
confirmed = json.loads('''$CONFIRMED_BODY''')

det_tasks = detected.get('tasks', [])
conf_tasks = confirmed.get('tasks', [])

if not det_tasks and not conf_tasks:
    print('No tasks to triage. 0 confirmed task(s) in your queue.')
    sys.exit(0)

if not det_tasks:
    conf_count = len(conf_tasks)
    print(f'No tasks to triage. {conf_count} confirmed task(s) in your queue.')
else:
    print('== TASK TRIAGE ==')
    print()
    print(f'--- Detected ({len(det_tasks)}) ---')
    for i, t in enumerate(det_tasks, 1):
        priority = (t.get('priority') or 'med').upper()
        title = t.get('title', 'Untitled')
        source = t.get('source', 'unknown')
        tid = t.get('id', '')
        created = t.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            date_str = dt.strftime('%b %d')
        except:
            date_str = 'unknown'
        skill = t.get('suggested_skill') or 'none'
        print(f'{i}. [{priority}] {title}')
        print(f'   From: {source} ({date_str})')
        print(f'   Skill: {skill}  [id:{tid}]')

if conf_tasks:
    print()
    print(f'--- Confirmed ({len(conf_tasks)}) ---')
    for i, t in enumerate(conf_tasks, 1):
        priority = (t.get('priority') or 'med').upper()
        title = t.get('title', 'Untitled')
        tid = t.get('id', '')
        created = t.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            date_str = dt.strftime('%b %d')
        except:
            date_str = 'unknown'
        print(f'{i}. [{priority}] {title} - confirmed {date_str}  [id:{tid}]')

if det_tasks:
    print()
    print(\"Reply: '{number} confirm' | '{number} dismiss' | 'all confirm' | 'all dismiss'\")
"
```

**Important:** The `[id:{tid}]` tag tracks UUID-to-position mapping. Claude remembers this and uses it when the user refers to tasks by number. Do NOT re-fetch (positions might shuffle).

**Step 3: Handle user response (conversational turn)**

Claude interprets the user's reply flexibly. All of these mean "confirm task 1":
- "1 confirm"
- "confirm 1"
- "confirm the first one"
- "yes to 1"

**For single task action:**

Parse the number and action (confirm or dismiss) from the user's reply. Map the number to the task UUID from the `[id:...]` tag in the displayed list.

```bash
TASK_UUID="<uuid from position N>"
ACTION="confirmed"  # or "dismissed"
RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"status\": \"$ACTION\"}" \
  "$BASE/tasks/$TASK_UUID/status")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If 200: display "Task '{title}' {confirmed|dismissed}."
If 422: display "Cannot {action} this task -- it may have already been {current_status}."
If 401: token expiration message.

**For bulk action ("all confirm" or "all dismiss"):**

Loop through all detected tasks and call PATCH for each:

```bash
for TASK_UUID in $DETECTED_UUIDS; do
  RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"status\": \"$ACTION\"}" \
    "$BASE/tasks/$TASK_UUID/status")
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  # Check for 401 on each call
done
```

Display summary: "Confirmed {N} tasks." or "Dismissed {N} tasks."

---

## Subcommand: prep

Show upcoming meetings and trigger prep with real-time SSE streaming.

### Setup

```bash
TOKEN="${FLYWHEEL_API_TOKEN:-}"
BASE="${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}"
AUTH="Authorization: Bearer $TOKEN"
```

### Flow

**Step 1: Fetch upcoming meetings**

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" "$BASE/meetings/?time=upcoming&limit=10")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If HTTP code is 401: stop and display token expiration message.
If HTTP code is not 200: display "Error fetching upcoming meetings ({HTTP_CODE})."

**Step 2: Filter and display**

By default, show only external meetings (meeting_type != "internal"). If the user said "prep all", include internal meetings too.

```bash
FILTER_ALL="${FILTER_ALL:-false}"  # Set to "true" if user said "prep all"

echo "$BODY" | python3 -c "
import sys, json
from datetime import datetime

filter_all = '$FILTER_ALL' == 'true'
data = json.load(sys.stdin)
meetings = data.get('meetings', [])

if not filter_all:
    meetings = [m for m in meetings if m.get('meeting_type') != 'internal']

if not meetings:
    if filter_all:
        print('No upcoming meetings to prep.')
    else:
        print('No upcoming external meetings to prep.')
    sys.exit(0)

print('== MEETING PREP ==')
print()
for i, m in enumerate(meetings, 1):
    mid = m.get('id', '')
    title = m.get('title', 'Untitled')
    md = m.get('meeting_date', '')
    status = m.get('processing_status', 'unknown')
    try:
        dt = datetime.fromisoformat(md.replace('Z', '+00:00'))
        time_str = dt.strftime('%H:%M')
    except:
        time_str = '??:??'

    # Map processing_status to prep display
    if status in ('processed', 'prepped'):
        prep = 'Ready'
    elif status in ('processing',):
        prep = 'In progress'
    else:
        prep = 'Not started'

    print(f'{i}. [{time_str}] {title} - Prep: {prep}  [id:{mid}]')

print()
print(\"Reply with a number to trigger prep, or 'all' for all unprepped.\")
"
```

**Important:** The `[id:{mid}]` tag tracks UUID-to-position mapping. Claude remembers this and uses it when the user refers to meetings by number. Do NOT re-fetch (positions might shuffle).

**Step 3: Handle user response (conversational turn)**

**For single meeting prep (user replies with a number N):**

Map N to the meeting UUID from the `[id:...]` tag.

```bash
MEETING_UUID="<uuid from position N>"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH" "$BASE/meetings/$MEETING_UUID/prep")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
```

If 401: token expiration message.
If not 200: display "Prep failed ({HTTP_CODE})."

If 200: parse the stream URL and start SSE streaming:

```bash
STREAM_URL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stream_url',''))")

curl -s -N -H "$AUTH" "http://localhost:8000$STREAM_URL" | while IFS= read -r line; do
  # Skip empty lines and event: prefix lines
  if [[ "$line" == data:* ]]; then
    JSON="${line#data: }"
    echo "$JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    event = d.get('event', '')
    data = d.get('data', {})
    if event == 'stage':
        print(f'Stage: {data.get(\"stage\", \"\")} -- {data.get(\"message\", \"\")}')
    elif event == 'done':
        print('Prep complete.')
    elif event == 'error':
        print(f'Prep failed: {data.get(\"message\", \"unknown error\")}')
except:
    pass
"
  fi
done
```

Display "Prep complete for {title}." after the stream ends with a `done` event.

**For "all" (process all unprepped):**

Loop through meetings where prep status is "Not started" and trigger prep sequentially:

```bash
for MEETING_UUID in $UNPREPPED_UUIDS; do
  echo "Prepping: {title}..."
  # Same prep + SSE flow as single meeting above
done
```

Display progress per meeting as each completes.
