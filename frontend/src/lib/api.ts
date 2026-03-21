import { useAuthStore } from '@/stores/auth'
import { useFocusStore } from '@/stores/focus'

const BASE_URL = '/api/v1'

export class ApiError extends Error {
  constructor(
    public code: number,
    public error: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = useAuthStore.getState().token
  const focusId = useFocusStore.getState().activeFocus?.id
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(focusId ? { 'X-Focus-Id': focusId } : {}),
      ...options.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({
      error: 'Unknown',
      message: res.statusText,
      code: res.status,
    }))
    throw new ApiError(body.code, body.error, body.message)
  }

  return res.json()
}

export const api = {
  get: <T>(path: string, opts?: { params?: Record<string, unknown> }) => {
    const url = opts?.params
      ? `${path}?${new URLSearchParams(
          Object.entries(opts.params)
            .filter(([, v]) => v != null)
            .map(([k, v]) => [k, String(v)])
        )}`
      : path
    return request<T>(url)
  },
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
}
