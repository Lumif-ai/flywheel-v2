---
status: verifying
trigger: "Multiple 500 errors in onboarding flow - Connection lost on Prepare a brief"
created: 2026-03-23T00:00:00Z
updated: 2026-03-23T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - meeting-prep not in subsidy skill list, anonymous users fail with "No API key"
test: Read skill_executor.py line 456 - subsidy tuple only contains "company-intel"
expecting: meeting-prep must be added to subsidy list + engine dispatch needs handling
next_action: Apply fix to skill_executor.py and verify

## Symptoms

expected: User enters LinkedIn URL + agenda on "Prepare" step, clicks button, sees SSE-streamed meeting prep results.
actual: "Connection lost" error. Console errors: 401 on SSE stream, 500 on /api/v1/tenants, JSON parse error.
errors:
- OnboardingPage.tsx: Uncaught ReferenceError: MeetingIngest is not defined
- api/v1/skills/runs/{run_id}/stream 401 Unauthorized
- api/v1/tenants 500 Internal Server Error
- sse.ts:38 "undefined" is not valid JSON
reproduction: Go to /onboarding, complete discover+organize, reach Prepare, enter LinkedIn URL, click Prepare briefing
started: Just introduced with OnboardingMeetingPrep component

## Eliminated

- hypothesis: Vite proxy misconfiguration
  evidence: Vite proxies all /api/* to localhost:8000 (line 15 vite.config.ts). curl to backend endpoint works.
  timestamp: 2026-03-23T00:01

- hypothesis: SSE endpoint not registered on backend
  evidence: GET /api/v1/onboarding/run/{run_id}/stream exists in onboarding.py router (line 393). curl returns 401 (auth required, not 404).
  timestamp: 2026-03-23T00:01

## Evidence

- timestamp: 2026-03-23T00:01
  checked: vite.config.ts proxy configuration
  found: '/api' proxied to localhost:8000 - covers all /api/v1/onboarding/* routes
  implication: Proxy is NOT the issue

- timestamp: 2026-03-23T00:02
  checked: skill_executor.py lines 452-461, subsidy API key fallback
  found: Only "company-intel" is in the subsidy tuple. meeting-prep is NOT included.
  implication: Anonymous users with no BYOK key get ValueError("No API key configured") immediately

- timestamp: 2026-03-23T00:02
  checked: skill_executor.py lines 521-537, engine dispatch
  found: If meeting-prep has engine_module in DB, it hits "no engine dispatch" error. If no engine_module, it uses _execute_with_tools (LLM path) which would work if API key is available.
  implication: Need to add meeting-prep to subsidy list AND verify engine_module setting in DB

- timestamp: 2026-03-23T00:03
  checked: onboarding_run_stream error handling flow
  found: Backend emits "error" event then sets status="failed". SSE stream forwards both error event and done event. Frontend error handler works correctly.
  implication: The "Connection lost" is from EventSource.onerror when the run stays stuck or the SSE connection fails for other reasons

## Resolution

root_cause: skill_executor.py line 456 only allows subsidy API key fallback for "company-intel" skill. Anonymous onboarding users running "meeting-prep" fail with "No API key configured" because meeting-prep is not in the subsidy tuple.
fix: |
  1. Added "meeting-prep" to subsidy skill tuple in skill_executor.py (line 456)
  2. Added initial SSE event in onboarding_run_stream to prevent "Connection lost" from browser timeout
  3. Added error handling in OnboardingMeetingPrep done event to show error message on failed runs
verification: Backend server needs restart; then reproduce by clicking "Prepare briefing" on onboarding
files_changed:
  - backend/src/flywheel/services/skill_executor.py
  - backend/src/flywheel/api/onboarding.py
  - frontend/src/features/onboarding/components/OnboardingMeetingPrep.tsx
