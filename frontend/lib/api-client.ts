'use client'

import type { Settings } from './types'

const AUTH_TOKEN_KEY = 'schism_auth_token'
const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL?.trim() || '/api'

export class ApiError extends Error {
  constructor(
    public status: number,
    public override message: string,
    public detail?: string
  ) {
    super(message)
  }
}

function trimTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function getApiBaseUrl(): string {
  if (!RAW_API_BASE) return ''
  return trimTrailingSlash(RAW_API_BASE)
}

function getStoredAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  const localToken = window.localStorage.getItem(AUTH_TOKEN_KEY)
  if (localToken) return localToken

  const cookieToken = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${AUTH_TOKEN_KEY}=`))

  if (!cookieToken) return null
  return decodeURIComponent(cookieToken.split('=').slice(1).join('='))
}

function clearStoredAuthToken(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
  document.cookie = `${AUTH_TOKEN_KEY}=; Max-Age=0; path=/`
}

function notifyAuthExpired(): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('schism:auth-expired'))
}

export function providerHeaders(settings?: Settings): HeadersInit {
  if (!settings) return {}
  const headers: HeadersInit = {
    'X-Provider': settings.provider,
    'X-Model': settings.model,
    'X-Base-Url': settings.baseUrl,
    'X-Embedding-Provider': settings.embeddingProvider,
  }

  if (settings.apiKey) {
    headers['X-Api-Key'] = settings.apiKey
  }

  return headers
}

function buildUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  const base = getApiBaseUrl()
  if (!base) return path
  if (path.startsWith('/')) return `${base}${path}`
  return `${base}/${path}`
}

async function parseError(res: Response): Promise<ApiError> {
  const body = await res
    .json()
    .catch(() => null) as
    | { detail?: string; message?: string; error?: string }
    | null

  const detail = body?.detail || body?.message || body?.error
  return new ApiError(res.status, detail || `HTTP ${res.status}`, detail)
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & {
    settings?: Settings
    expectBlob?: boolean
  } = {}
): Promise<T> {
  const headers = new Headers(options.headers)
  const authToken = getStoredAuthToken()

  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }

  console.log('API Request:', path, {
    method: options.method,
    hasBody: !!options.body,
    bodyType: options.body?.constructor.name,
    headers: Object.fromEntries(headers.entries())
  })

  // If the body is FormData, we must NOT set the Content-Type header.
  // The browser will automatically set it to multipart/form-data with the correct boundary.
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
  })

  if (response.status === 401 && authToken) {
    clearStoredAuthToken()
    notifyAuthExpired()
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (options.expectBlob) {
    return response.blob() as Promise<T>
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
