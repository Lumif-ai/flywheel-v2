/**
 * Feature flags with runtime tenant override.
 *
 * Priority: tenant.features > compile-time VITE_FEATURE_* > default (enabled)
 *
 * Compile-time flags still work for local dev (set VITE_FEATURE_X=false in .env).
 * Runtime flags come from tenant.settings.features in the DB, delivered via
 * the /tenants endpoint and stored in useTenantStore.
 *
 * To disable a feature for a tenant, set in DB:
 *   UPDATE tenants SET settings = jsonb_set(settings, '{features,email}', 'false');
 *
 * Feature names: email, tasks, leads, pipeline, meetings, crm
 */

import { useTenantStore } from '@/stores/tenant'

/** Compile-time defaults — enabled unless explicitly "false" */
const COMPILE_TIME: Record<string, boolean> = {
  email: import.meta.env.VITE_FEATURE_EMAIL !== 'false',
  tasks: import.meta.env.VITE_FEATURE_TASKS !== 'false',
  leads: true,
  pipeline: true,
  meetings: true,
  crm: true,
}

/**
 * Check if a feature is enabled for the current tenant.
 * Runtime tenant flags take precedence over compile-time defaults.
 */
export function useFeatureFlag(name: string): boolean {
  const features = useTenantStore((s) => s.activeTenant?.features)
  // Runtime override from tenant settings
  if (features && name in features) {
    return features[name]
  }
  // Fall back to compile-time
  return COMPILE_TIME[name] ?? true
}

/** Non-hook version for use outside React components (e.g., route config) */
export function getFeatureFlag(name: string): boolean {
  const tenant = useTenantStore.getState().activeTenant
  if (tenant?.features && name in tenant.features) {
    return tenant.features[name]
  }
  return COMPILE_TIME[name] ?? true
}

// Legacy exports for backward compatibility during migration
export const FEATURE_EMAIL = COMPILE_TIME.email
export const FEATURE_TASKS = COMPILE_TIME.tasks
