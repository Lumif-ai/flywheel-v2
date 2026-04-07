# Phase 80: Frontend Feature Flags - Research

**Researched:** 2026-03-30
**Domain:** Vite compile-time env vars + React Router route gating
**Confidence:** HIGH

## Summary

This phase is straightforward: use Vite's built-in `import.meta.env.VITE_*` mechanism to gate email and tasks routes at build time. The codebase already uses this exact pattern for Supabase credentials (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` in `src/lib/supabase.ts`), so no new dependencies or infrastructure are needed.

There are exactly four touch points: (1) route definitions in `routes.tsx`, (2) sidebar nav links in `AppSidebar.tsx`, (3) the `CriticalEmailAlert` component in `layout.tsx` which fires email API calls globally, and (4) the `vite-env.d.ts` type declarations. The command palette and mobile nav do NOT currently include email/tasks links, so they require no changes.

**Primary recommendation:** Create a `src/lib/feature-flags.ts` module exporting boolean constants derived from `import.meta.env`, then use those constants to conditionally include routes and nav items. Vite's dead-code elimination will tree-shake the gated feature code out of production builds when flags are false.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vite | (already installed) | Build-time env var substitution via `import.meta.env.VITE_*` | Zero-dependency, already in use |
| React Router v7 | (already installed) | Conditional route rendering | Already the routing solution |

### Supporting
No additional libraries needed. This is pure application-level conditional rendering using existing tooling.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compile-time env vars | Runtime feature flag service (LaunchDarkly, Flagsmith) | Massive overkill for hiding 2 routes from design partners. Runtime flags add latency, cost, and complexity. Compile-time is perfect for this use case. |
| Filtering route arrays | Vite `define` config option | `define` replaces arbitrary globals but `import.meta.env.VITE_*` is the idiomatic Vite approach and already used in this codebase. |

## Architecture Patterns

### Recommended: Centralized Feature Flag Module

Create a single source of truth for all feature flags:

```
src/
  lib/
    feature-flags.ts    # NEW: boolean constants from env vars
  app/
    routes.tsx           # MODIFY: conditionally include routes
  features/
    navigation/
      components/
        AppSidebar.tsx   # MODIFY: conditionally include nav items
  vite-env.d.ts          # MODIFY: add type declarations
```

### Pattern: Feature Flag Constants

```typescript
// src/lib/feature-flags.ts
export const FEATURE_EMAIL = import.meta.env.VITE_FEATURE_EMAIL !== 'false'
export const FEATURE_TASKS = import.meta.env.VITE_FEATURE_TASKS !== 'false'
```

Key design decision: **default to ENABLED** (`!== 'false'` rather than `=== 'true'`). This means:
- Developers who don't set any env vars get all features (good DX)
- Only explicitly setting `VITE_FEATURE_EMAIL=false` disables a feature
- Design partner deployments set `=false` explicitly

### Pattern: Conditional Routes with Redirect Fallback

```typescript
// In routes.tsx
import { FEATURE_EMAIL, FEATURE_TASKS } from '@/lib/feature-flags'

// Inside <Routes>:
{FEATURE_EMAIL && (
  <Route path="/email" element={<Suspense fallback={null}><EmailPage /></Suspense>} />
)}
{!FEATURE_EMAIL && (
  <Route path="/email" element={<Navigate to="/" replace />} />
)}
```

This handles both success criteria:
1. Route is removed from the route table when flag is false
2. Direct navigation to `/email` redirects to home instead of showing a broken page

### Pattern: Conditional Sidebar Items

```typescript
// In AppSidebar.tsx
import { FEATURE_EMAIL, FEATURE_TASKS } from '@/lib/feature-flags'

// Wrap the email SidebarMenuItem:
{FEATURE_EMAIL && (
  <SidebarMenuItem>
    <SidebarMenuButton isActive={...} render={<NavLink to="/email" />} tooltip="Email">
      <Mail className="size-4" />
      <span>Email</span>
    </SidebarMenuButton>
  </SidebarMenuItem>
)}
```

### Pattern: Gate Global Email Features

The `AuthenticatedAlerts` component in `layout.tsx` calls `useEmailThreads()` unconditionally and renders `CriticalEmailAlert`. When email is disabled, this should also be gated:

```typescript
// In layout.tsx
import { FEATURE_EMAIL } from '@/lib/feature-flags'

function AuthenticatedAlerts() {
  const { data: emailData } = useEmailThreads()
  if (!FEATURE_EMAIL) return null
  return emailData?.threads ? <CriticalEmailAlert threads={emailData.threads} /> : null
}
```

Note: Even better, move the `useEmailThreads()` call inside the conditional so it doesn't fire at all. But since the hook already handles missing data gracefully, gating just the render is acceptable as a simpler approach. The ideal approach wraps the entire component:

```typescript
function AuthenticatedAlerts() {
  if (!FEATURE_EMAIL) return null
  return <EmailAlertInner />
}

function EmailAlertInner() {
  const { data: emailData } = useEmailThreads()
  return emailData?.threads ? <CriticalEmailAlert threads={emailData.threads} /> : null
}
```

This ensures the hook never fires when email is disabled (avoiding unnecessary API calls).

### Anti-Patterns to Avoid
- **Scattering `import.meta.env` checks everywhere:** Always go through `feature-flags.ts` constants. Single source of truth.
- **Using runtime checks instead of compile-time:** `import.meta.env.VITE_*` is statically replaced by Vite at build time. Don't read from `window` or localStorage.
- **Forgetting the redirect route:** If you only omit the route without adding a redirect, users hitting `/email` directly get the React Router "no match" behavior (likely a blank page or 404).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feature flag evaluation | Custom flag service, database-backed flags | `import.meta.env.VITE_*` | Two boolean flags don't need infrastructure |
| Route gating | Custom route wrapper HOC | Conditional JSX in routes.tsx | Simple conditional rendering is clearer than abstraction for 2 routes |
| Nav item filtering | Dynamic nav config system | Conditional JSX in AppSidebar | Over-engineering for 2 items |

**Key insight:** This phase is intentionally minimal. The goal is hiding 2 features from design partners, not building a feature flag platform. Keep it simple.

## Common Pitfalls

### Pitfall 1: Lazy Import Still Bundled
**What goes wrong:** Even with the route gated, the lazy `import()` declaration at the top of `routes.tsx` might still be included in the bundle.
**Why it happens:** Vite/Rollup may not tree-shake dynamic imports that are conditionally referenced.
**How to avoid:** Move the lazy import inside the conditional block, or accept that lazy imports are already code-split (they create separate chunks that are only loaded on navigation). Since the route is never rendered, the chunk is never fetched. This is a non-issue in practice for lazy-loaded routes.
**Warning signs:** Unnecessarily large bundles (check with `vite build --report`).

### Pitfall 2: TypeScript Errors on import.meta.env
**What goes wrong:** TypeScript doesn't know about custom `VITE_FEATURE_*` env vars.
**Why it happens:** The default `vite/client` types only declare `VITE_*` as `string | undefined` via index signature, but adding explicit declarations improves DX.
**How to avoid:** Extend `ImportMetaEnv` in `vite-env.d.ts`:
```typescript
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_FEATURE_EMAIL?: string
  readonly VITE_FEATURE_TASKS?: string
}
```

### Pitfall 3: Forgetting the CriticalEmailAlert in layout.tsx
**What goes wrong:** Email is "disabled" but the app still makes email API calls on every page load and shows critical email alerts.
**Why it happens:** `AuthenticatedAlerts` in `layout.tsx` calls `useEmailThreads()` globally, outside of any email route.
**How to avoid:** Gate `AuthenticatedAlerts` behind `FEATURE_EMAIL`.
**Warning signs:** Network tab shows `/api/email/threads` requests when email feature is disabled.

### Pitfall 4: Env Var Not Set in Deployment
**What goes wrong:** Feature flags work locally but features are unexpectedly visible/hidden in production.
**Why it happens:** `.env` files are not committed to git; deployment environment doesn't have the vars set.
**How to avoid:** Document required env vars. Use the `!== 'false'` default-to-enabled pattern so missing vars don't accidentally hide features.

## Code Examples

### Complete feature-flags.ts Module

```typescript
// src/lib/feature-flags.ts

/**
 * Compile-time feature flags.
 *
 * These are evaluated at build time by Vite's import.meta.env substitution.
 * Set VITE_FEATURE_X=false in .env to disable a feature.
 * Features default to ENABLED when the env var is unset.
 */
export const FEATURE_EMAIL = import.meta.env.VITE_FEATURE_EMAIL !== 'false'
export const FEATURE_TASKS = import.meta.env.VITE_FEATURE_TASKS !== 'false'
```

### Updated vite-env.d.ts

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_ANON_KEY?: string
  readonly VITE_FEATURE_EMAIL?: string
  readonly VITE_FEATURE_TASKS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

### .env.example Addition

```bash
# Feature flags (default: enabled; set to "false" to disable)
# VITE_FEATURE_EMAIL=false
# VITE_FEATURE_TASKS=false
```

## Exact Touch Points (Complete Inventory)

| File | What to Change | Feature Flag |
|------|---------------|--------------|
| `src/lib/feature-flags.ts` | **CREATE** - centralized flag constants | both |
| `src/vite-env.d.ts` | **ADD** type declarations for new env vars | both |
| `src/app/routes.tsx` line 99 | Gate `/email` route + add redirect | FEATURE_EMAIL |
| `src/app/routes.tsx` line 109 | Gate `/tasks` route + add redirect | FEATURE_TASKS |
| `src/app/routes.tsx` lines 43-45 | Gate `EmailPage` lazy import (optional, already code-split) | FEATURE_EMAIL |
| `src/app/routes.tsx` lines 69-71 | Gate `TasksPage` lazy import (optional, already code-split) | FEATURE_TASKS |
| `src/features/navigation/components/AppSidebar.tsx` lines 141-150 | Gate Email nav item | FEATURE_EMAIL |
| `src/features/navigation/components/AppSidebar.tsx` lines 161-170 | Gate Tasks nav item | FEATURE_TASKS |
| `src/app/layout.tsx` lines 78-81 | Gate `AuthenticatedAlerts` (email API calls + CriticalEmailAlert) | FEATURE_EMAIL |

**Files that do NOT need changes:**
- `MobileNav.tsx` - does not include email or tasks links
- `CommandPalette.tsx` - does not include email or tasks links
- `vite.config.ts` - no changes needed, `import.meta.env.VITE_*` works out of the box

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Runtime feature flags via API | Compile-time env vars for static flags | Always valid for build-time decisions | Zero runtime cost, tree-shakeable |
| `.env` with dotenv package | Vite native `import.meta.env` | Vite 1.0+ | No extra dependencies |

## Open Questions

1. **Should we gate any other features?**
   - What we know: Phase spec mentions email and tasks only
   - What's unclear: Whether other features (meetings, pipeline, relationships) should also be gatable
   - Recommendation: Implement only email and tasks per spec. The pattern is trivially extensible if needed later.

2. **Should the .env.example or .env.local be created/updated?**
   - What we know: No `.env` files currently exist in the frontend directory
   - What's unclear: Whether the project uses a different env var management approach
   - Recommendation: Create a `.env.example` documenting available feature flags for developer reference.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `routes.tsx`, `AppSidebar.tsx`, `MobileNav.tsx`, `CommandPalette.tsx`, `layout.tsx`, `supabase.ts`, `vite-env.d.ts`, `vite.config.ts`
- Vite documentation on env vars: `import.meta.env.VITE_*` is statically replaced at build time (well-established Vite feature since v1.0)

### Secondary (MEDIUM confidence)
- Tree-shaking behavior of conditional lazy imports: Based on established Vite/Rollup behavior with code-split chunks

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, uses existing Vite env var mechanism already proven in this codebase
- Architecture: HIGH - direct codebase inspection identifies all touch points
- Pitfalls: HIGH - enumerated from reading actual code paths (especially the CriticalEmailAlert in layout.tsx)

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stable patterns, no moving parts)
