# Flywheel API Reference

Quick reference for all backend API endpoints the `/flywheel` skill calls.
Consult this when you need exact endpoint paths, query parameters, or response shapes.

**Base URL:** `${FLYWHEEL_API_URL:-http://localhost:8000/api/v1}`
**Auth:** Every request requires `Authorization: Bearer ${FLYWHEEL_API_TOKEN}` header.

---

## Authentication

### Verify Token

```
GET /api/v1/auth/me
```

**Response (200):**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "tenant_id": "uuid"
}
```

**Errors:** 401 (token expired or invalid)

---

## Meetings

### List Meetings

```
GET /api/v1/meetings/
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `time` | string | Filter: `upcoming` for future meetings |
| `processing_status` | string | Filter: `recorded`, `pending`, `processed`, `skipped` |
| `limit` | int | Max results (default varies) |

**Response (200):**
```json
{
  "meetings": [
    {
      "id": "uuid",
      "title": "string",
      "meeting_date": "2026-03-28T10:00:00Z",
      "attendees": [{"name": "string", "email": "string"}],
      "processing_status": "recorded|pending|processed|skipped",
      "account_id": "uuid|null",
      "meeting_type": "external|internal|unknown",
      "duration_mins": 45
    }
  ],
  "total": 5
}
```

**Common calls:**
- Upcoming meetings: `GET /api/v1/meetings/?time=upcoming&limit=10`
- Unprocessed meetings: `GET /api/v1/meetings/?processing_status=recorded&limit=10`

### Sync from Granola

```
POST /api/v1/meetings/sync
```

**Request body:** None

**Response (200):**
```json
{
  "synced": 3,
  "skipped": 1,
  "already_seen": 12,
  "total_from_provider": 16
}
```

### Process Pending Meetings (batch)

```
POST /api/v1/meetings/process-pending
```

**Request body:** None

**Response (200):**
```json
{
  "queued": 2,
  "run_ids": ["uuid", "uuid"]
}
```

### Trigger Meeting Prep

```
POST /api/v1/meetings/{id}/prep
```

**Path params:** `id` (meeting UUID)

**Response (200):**
```json
{
  "run_id": "uuid",
  "stream_url": "/api/v1/skills/runs/{run_id}/stream"
}
```

### Process Single Meeting

```
POST /api/v1/meetings/{id}/process
```

**Path params:** `id` (meeting UUID)

**Response (200):**
```json
{
  "run_id": "uuid",
  "meeting_id": "uuid"
}
```

---

## Tasks

### List Tasks

```
GET /api/v1/tasks/
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter: `detected`, `confirmed`, `in_review`, `dismissed`, `completed` |
| `limit` | int | Max results (default 20) |

**Response (200):**
```json
{
  "tasks": [
    {
      "id": "uuid",
      "title": "string",
      "source": "string",
      "task_type": "follow_up|send_document|schedule|research|other",
      "priority": "high|medium|low",
      "suggested_skill": "email-drafter|null",
      "meeting_id": "uuid|null",
      "created_at": "2026-03-28T10:00:00Z",
      "status": "detected|confirmed|in_review|dismissed|completed"
    }
  ],
  "total": 8
}
```

**Common calls:**
- Detected tasks: `GET /api/v1/tasks/?status=detected&limit=20`
- Confirmed tasks: `GET /api/v1/tasks/?status=confirmed&limit=20`

### Task Summary (counts by status)

```
GET /api/v1/tasks/summary
```

**Response (200):**
```json
{
  "detected": 5,
  "in_review": 0,
  "confirmed": 3,
  "dismissed": 2,
  "completed": 1
}
```

### Update Task Status

```
PATCH /api/v1/tasks/{id}/status
```

**Path params:** `id` (task UUID)

**Request body:**
```json
{
  "status": "confirmed|dismissed|completed|in_review|detected"
}
```

**Valid transitions:**
- `detected` -> `confirmed`, `dismissed`, `in_review`
- `confirmed` -> `completed`, `dismissed`
- `dismissed` -> `detected` (reopen)

**Response (200):** Full TaskResponse object

**Errors:** 422 (invalid transition), 404 (task not found)

---

## Signals

### Get Signal Counts

```
GET /api/v1/signals/
```

**Response (200):**
```json
{
  "types": [
    {"type": "email_received", "count": 12},
    {"type": "meeting_completed", "count": 3}
  ],
  "total": 15,
  "tasks_detected": 5
}
```

---

## Skill Runs (SSE Streaming)

### Stream Skill Run Events

```
GET /api/v1/skills/runs/{id}/stream
```

**Path params:** `id` (run UUID from prep/process response)

**Response:** Server-Sent Events (SSE) stream

```
data: {"event": "stage", "data": {"stage": "researching", "message": "Gathering context..."}}
data: {"event": "text", "data": {"content": "partial output..."}}
data: {"event": "discovery", "data": {"key": "value"}}
data: {"event": "done", "data": {"rendered_html": "<html>...</html>"}}
data: {"event": "error", "data": {"message": "Something went wrong"}}
```

**Event types:** `stage`, `text`, `discovery`, `done`, `error`, `crawl_error`

**Usage:** `curl -s -N -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/skills/runs/{id}/stream"`

Note: Use `curl -N` (no buffering) for real-time SSE output.
