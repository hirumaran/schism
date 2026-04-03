import type {
  Settings,
  AnalyzeResponse,
  AnalysisJob,
  JobStats,
  JobResults,
  Report,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public override message: string,
    public detail?: string
  ) {
    super(message)
  }
}

function providerHeaders(settings: Settings): HeadersInit {
  return {
    'X-Provider': settings.provider,
    'X-Api-Key': settings.apiKey,
    'X-Model': settings.model,
    'X-Base-Url': settings.baseUrl,
    'X-Embedding-Provider': settings.embeddingProvider,
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(
      res.status,
      body.detail ?? body.message ?? `HTTP ${res.status}`,
      body.detail
    )
  }
  return res.json() as Promise<T>
}

export async function analyzeQuery(
  params: { query: string; max_results: number; sources: string[] },
  settings: Settings
): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...providerHeaders(settings),
    },
    body: JSON.stringify(params),
  })
  return handleResponse<AnalyzeResponse>(res)
}

export async function analyzePaper(
  params: {
    file?: File
    text?: string
    title?: string
    max_results: number
    sources: string[]
  },
  settings: Settings
): Promise<AnalyzeResponse> {
  if (params.file) {
    const formData = new FormData()
    formData.append('file', params.file)
    formData.append('max_results', params.max_results.toString())
    formData.append('sources', params.sources.join(','))
    if (params.title) formData.append('title', params.title)

    const res = await fetch(`${BASE}/api/analyze/paper`, {
      method: 'POST',
      headers: providerHeaders(settings),
      body: formData,
    })
    return handleResponse<AnalyzeResponse>(res)
  } else {
    const res = await fetch(`${BASE}/api/analyze/paper`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...providerHeaders(settings),
      },
      body: JSON.stringify({
        text: params.text,
        title: params.title,
        max_results: params.max_results,
        sources: params.sources,
      }),
    })
    return handleResponse<AnalyzeResponse>(res)
  }
}

export async function getJob(
  jobId: string,
  settings: Settings
): Promise<AnalysisJob> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}`, {
    headers: providerHeaders(settings),
  })
  return handleResponse<AnalysisJob>(res)
}

export async function getJobStats(
  jobId: string,
  settings: Settings
): Promise<JobStats> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}/stats`, {
    headers: providerHeaders(settings),
  })
  return handleResponse<JobStats>(res)
}

export async function getJobResults(
  jobId: string,
  params: { type?: string; mode?: string; limit?: number; offset?: number },
  settings: Settings
): Promise<JobResults> {
  const searchParams = new URLSearchParams()
  if (params.type) searchParams.set('type', params.type)
  if (params.mode) searchParams.set('mode', params.mode)
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  const res = await fetch(
    `${BASE}/api/jobs/${jobId}/results?${searchParams.toString()}`,
    {
      headers: providerHeaders(settings),
    }
  )
  return handleResponse<JobResults>(res)
}

export async function getReport(
  reportId: string,
  settings: Settings
): Promise<Report> {
  const res = await fetch(`${BASE}/api/reports/${reportId}`, {
    headers: providerHeaders(settings),
  })
  return handleResponse<Report>(res)
}

export async function cancelJob(
  jobId: string,
  settings: Settings
): Promise<void> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}`, {
    method: 'DELETE',
    headers: providerHeaders(settings),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(
      res.status,
      body.detail ?? body.message ?? `HTTP ${res.status}`,
      body.detail
    )
  }
}

export async function exportReport(
  reportId: string,
  format: 'json' | 'csv',
  settings: Settings
): Promise<Blob> {
  const res = await fetch(
    `${BASE}/api/reports/${reportId}/export?format=${format}`,
    {
      headers: providerHeaders(settings),
    }
  )
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(
      res.status,
      body.detail ?? body.message ?? `HTTP ${res.status}`,
      body.detail
    )
  }
  return res.blob()
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${BASE}/api/health`)
  return handleResponse<{ status: string; version: string }>(res)
}

export async function validateKey(settings: Settings): Promise<boolean> {
  const res = await fetch(`${BASE}/api/health`, {
    headers: providerHeaders(settings),
  })
  return res.ok
}

export async function testOllamaConnection(
  baseUrl: string
): Promise<{ models: string[] }> {
  const res = await fetch(`${baseUrl}/api/tags`)
  if (!res.ok) {
    throw new ApiError(res.status, 'Cannot connect to Ollama')
  }
  const data = await res.json()
  return { models: data.models?.map((m: { name: string }) => m.name) ?? [] }
}
