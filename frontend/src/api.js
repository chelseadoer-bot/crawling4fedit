const API = import.meta.env.VITE_API_URL || '/api'

async function parseError(res) {
  const data = await res.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg || d).join(', ')
  return '요청에 실패했습니다.'
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function fetchBrands() {
  const res = await fetch(`${API}/brands`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createBrand(name, url, group = '') {
  const res = await fetch(`${API}/brands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, url, group: group || undefined }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function updateBrand(brandId, { name, url, group, category } = {}) {
  const body = {}
  if (name !== undefined) body.name = name
  if (url !== undefined) body.url = url
  if (group !== undefined) body.group = group
  if (category !== undefined) body.category = category
  const res = await fetch(`${API}/brands/${brandId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function deleteBrand(brandId) {
  const res = await fetch(`${API}/brands/${brandId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchCrawlStatus(brandId) {
  const res = await fetch(`${API}/brands/${brandId}/crawl/status`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function crawlBrand(brandId) {
  const res = await fetch(`${API}/brands/${brandId}/crawl`, { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** 백그라운드 크롤 완료까지 폴링 (29CM 등 장시간 작업) */
export async function waitForCrawl(brandId, onProgress, { start = true } = {}) {
  if (start) {
    const started = await crawlBrand(brandId)
    if (onProgress) onProgress(started)
  }

  for (;;) {
    const job = await fetchCrawlStatus(brandId)
    if (onProgress) onProgress(job)
    if (job.status === 'success') {
      return { count: job.count, message: job.message }
    }
    if (job.status === 'failed') {
      throw new Error(job.message || '크롤링에 실패했습니다.')
    }
    await sleep(2000)
  }
}

export async function fetchPreview(brandId, limit = 50) {
  const res = await fetch(`${API}/brands/${brandId}/preview?limit=${limit}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchGroupPreview(groupSlug, limit = 50) {
  const res = await fetch(`${API}/groups/${groupSlug}/preview?limit=${limit}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export function downloadUrl(brandId) {
  return `${API}/brands/${brandId}/download`
}
