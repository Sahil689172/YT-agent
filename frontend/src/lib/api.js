/**
 * AutoShorts backend API client.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(title, message, status = null) {
    super(message)
    this.name = 'ApiError'
    this.title = title
    this.status = status
  }
}

async function parseErrorBody(res) {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d) => d.msg || String(d)).join(', ')
    }
    return data?.message || res.statusText
  } catch {
    return res.statusText || 'Request failed'
  }
}

function mapHttpError(status, detail) {
  const msg = detail || 'Something went wrong'
  if (status === 400) return new ApiError('Invalid Script', msg, status)
  if (status === 404) return new ApiError('Not Found', msg, status)
  if (status === 409) return new ApiError('Still Processing', msg, status)
  if (status >= 500) return new ApiError('Video Creation Failed', msg, status)
  return new ApiError('Generation Failed', msg, status)
}

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`
  let res
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
  } catch {
    throw new ApiError(
      'Backend Offline',
      `Cannot reach the API at ${API_BASE_URL}. Start it with: python -m uvicorn backend.api:app --reload`,
    )
  }

  if (!res.ok) {
    const detail = await parseErrorBody(res)
    throw mapHttpError(res.status, detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export function assetUrl(relativePath) {
  if (!relativePath) return null
  const normalized = relativePath.replace(/\\/g, '/').replace(/^\//, '')
  return `${API_BASE_URL}/${normalized}`
}

export async function checkHealth() {
  return request('/health')
}

export async function generateFromTopic(topic) {
  return request('/generate/topic', {
    method: 'POST',
    body: JSON.stringify({ topic }),
  })
}

export async function generateFromScript(script, topic = 'Custom Script') {
  return request('/generate/script', {
    method: 'POST',
    body: JSON.stringify({ script, topic }),
  })
}

export async function getProgress(jobId) {
  return request(`/progress/${jobId}`)
}

export async function getResult(jobId) {
  return request(`/result/${jobId}`)
}

export function parseHashtags(hashtagsRaw) {
  if (!hashtagsRaw) return []
  return hashtagsRaw
    .split(/\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((tag) => tag.replace(/^#/, ''))
}
