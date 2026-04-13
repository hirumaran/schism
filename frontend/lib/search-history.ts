const STORAGE_KEY = 'schism-search-history'
const MAX_HISTORY = 8

export function getSearchHistory(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed
    return []
  } catch (e) {
    return []
  }
}

export function addToSearchHistory(query: string): void {
  if (typeof window === 'undefined' || !query.trim()) return
  const q = query.trim()
  try {
    const history = getSearchHistory()
    const filtered = history.filter(item => item.toLowerCase() !== q.toLowerCase())
    const updated = [q, ...filtered].slice(0, MAX_HISTORY)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  } catch (e) {
    // ignore
  }
}

export function removeFromSearchHistory(query: string): void {
  if (typeof window === 'undefined') return
  try {
    const history = getSearchHistory()
    const updated = history.filter(item => item !== query)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  } catch (e) {
    // ignore
  }
}

export function clearSearchHistory(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    // ignore
  }
}
