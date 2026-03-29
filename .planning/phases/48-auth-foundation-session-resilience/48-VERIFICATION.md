---
phase: 48-auth-foundation-session-resilience
verified: 2026-03-25T10:30:00Z
status: human_needed
score: 5/5 must-haves verified (automated); 1 item needs human confirmation
re_verification: false
human_verification:
  - test: "Open app in incognito, sign in with Google OAuth, close and reopen tab within the same incognito window"
    expected: "Session restores from Supabase's internal localStorage (flywheel-auth key) without requiring sign-in again"
    why_human: "persistSession:true uses localStorage which browsers clear when incognito session ends. Cannot verify incognito persistence programmatically — depends on Supabase SDK internals and browser-specific incognito behavior."
---

# Phase 48: Auth Foundation and Session Resilience — Verification Report

**Phase Goal:** Fix 5 fundamental auth/session/data-persistence issues: OAuth consent forced every time, session lost on refresh in incognito, data orphaned on signInWithOAuth fallback, forced onboarding redirect blocks workspace access, user name not displayed from OAuth session.

**Verified:** 2026-03-25T10:30:00Z
**Status:** human_needed (all 5 automated checks pass; 1 requires human confirmation)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Returning OAuth users see account-picker, not full consent screen | VERIFIED | `useOAuthSignIn.ts` uses `prompt:'select_account'` on signInWithOAuth fallback; `prompt:'consent'` only on linkIdentity (needed for refresh token) |
| 2 | Session survives page refresh | VERIFIED | `supabase.ts` has `persistSession: true, storageKey: 'flywheel-auth'`; `AuthBootstrap` calls `getSession()` on startup to restore any existing session before falling back to anonymous sign-in |
| 3 | Anonymous data is not lost when signInWithOAuth creates a new user | VERIFIED | `useOAuthSignIn` stores `flywheel-prev-anon-id` in localStorage pre-redirect; `AuthCallback` calls `POST /onboarding/claim-anonymous-data` when `prevAnonId !== session.user.id`; endpoint atomically migrates all 5 model types |
| 4 | User can reach workspace without being forced through onboarding | VERIFIED | No `navigate('/onboarding')` calls exist in any page component; `BriefingPage.tsx` line 153 confirms inline CTAs replace the old forced redirect; `AppShell` in `layout.tsx` uses a denylist for standalone routes, not a redirect |
| 5 | User name from OAuth (Google/Microsoft) is displayed in the sidebar | VERIFIED | `AuthStore` has `display_name` field; `AuthCallback` and `AuthBootstrap` both extract `user_metadata?.full_name ?? user_metadata?.name`; `AppSidebar` renders `user.display_name` with email fallback and derives initials |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/hooks/useOAuthSignIn.ts` | Shared OAuth hook with linkIdentity + signInWithOAuth fallback | VERIFIED | 71 lines, substantive; stores `flywheel-prev-anon-id`, uses `prompt:'consent'` for link, `prompt:'select_account'` for fallback |
| `frontend/src/lib/supabase.ts` | Supabase client with `persistSession: true, storageKey: 'flywheel-auth'` | VERIFIED | Lines 30-35 confirm auth config with both options |
| `frontend/src/app/AuthBootstrap.tsx` | Session restoration on startup + onAuthStateChange listener | VERIFIED | `getSession()` check before anonymous fallback (lines 64-76); `onAuthStateChange` listener syncs `display_name` and `avatar_url` |
| `frontend/src/app/AuthCallback.tsx` | Post-OAuth callback with metadata refresh + data claim | VERIFIED | Calls `getUser()` after promote-oauth for fresh metadata (lines 81-94); claim flow with `localStorage.removeItem` in finally block (lines 102-116) |
| `backend/src/flywheel/api/onboarding.py` | `POST /onboarding/claim-anonymous-data` endpoint | VERIFIED | Lines 575-679: substantive — validates anonymous tenant name, checks no other users, atomically migrates ContextEntry/WorkStream/SkillRun/Document/OnboardingSession, cleans up old rows |
| `frontend/src/stores/auth.ts` | AuthStore with `display_name` and `avatar_url` fields | VERIFIED | `User` interface (lines 3-9) includes both fields |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `SignupGate.tsx` | `useOAuthSignIn` | `signInWithProvider` call | WIRED | Line 10: import; lines 21, 29, 42: used for both google and azure |
| `BriefingChatPanel.tsx` | `useOAuthSignIn` | `signInWithProvider` call | WIRED | Line 6: import; lines 34, 68, 73, 79, 84: used for both providers |
| `AppSidebar.tsx` | `useOAuthSignIn` | `signInWithProvider` call | WIRED | Lines 6/29: imported and called in handlers |
| `AuthCallback.tsx` | `POST /onboarding/claim-anonymous-data` | `api.post` call | WIRED | Lines 106-108: calls endpoint with `previous_anonymous_id: prevAnonId` |
| `AuthCallback.tsx` | `AuthStore.setUser` | `display_name` population | WIRED | Lines 51-57 (session data) and 84-90 (fresh getUser data) both set `display_name` |
| `onboarding_router` | `main.py` | `include_router` | WIRED | `main.py` line 148: `app.include_router(onboarding_router, prefix="/api/v1")` |
| `/auth/callback` route | `AuthCallback` component | React Router `<Route>` | WIRED | `routes.tsx` line 55 |

---

### Requirements Coverage

No REQUIREMENTS.md entries mapped to Phase 48 were found. Phase 48 is a cross-cutting gap closure phase targeting runtime behavioral bugs identified during testing.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `AuthCallback.tsx` | 109 | `console.log` in claim success path | Info | Dev-only logging, no impact on correctness |
| `AuthBootstrap.tsx` | 81 | `console.warn` for lost anonymous session | Info | Diagnostics only |

No blockers or warnings found.

---

## Human Verification Required

### 1. Session Persistence in Incognito

**Test:** Open the app in an incognito/private window. Sign in via Google OAuth. After landing on the dashboard, close the tab and reopen the same incognito window to the app URL.

**Expected:** The session restores (user is still signed in, no new anonymous session created). The `flywheel-auth` key in localStorage should be present.

**Why human:** `persistSession: true` uses localStorage under the hood. Standard browsers retain localStorage within the same incognito session (same window), but the session is lost when the incognito window is fully closed. The fix addresses "lost on refresh" (same session) but not "lost on close" (new session). This is the expected browser behavior, but the phase goal says "session lost on refresh in incognito" — refreshing within the same incognito tab should now work. Human needs to confirm this specific scenario works.

---

## Gaps Summary

No gaps found. All 5 issues targeted by Phase 48 have verifiable implementations:

- **OAuth consent issue**: `useOAuthSignIn` centralizes the linkIdentity-first / signInWithOAuth-fallback pattern with the correct `prompt` values. Returning users hit `select_account` instead of `consent`.
- **Session persistence**: `persistSession: true` + `storageKey` namespacing prevents token collision. `AuthBootstrap` restores sessions on startup.
- **Orphaned data**: The `flywheel-prev-anon-id` lifecycle is complete across all 3 plans — captured (Plan 01), consumed (Plan 03), cleaned up (finally block).
- **Forced redirect**: Removed via commit 9dd35d2 — no `navigate('/onboarding')` in any page component. `BriefingPage` shows inline CTAs.
- **User name display**: `display_name` field propagated from Supabase `user_metadata` through AuthStore to AppSidebar rendering.

The one human-needed item is behavioral confirmation that incognito refresh (same tab) works, not a code gap.

---

*Verified: 2026-03-25T10:30:00Z*
*Verifier: Claude (gsd-verifier)*
