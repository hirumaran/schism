export async function fetchPaperSuggestions(query: string): Promise<string[]> {
  if (query.length < 3) return []
  try {
    const res = await fetch(`https://api.semanticscholar.org/graph/v1/paper/autocomplete?query=${encodeURIComponent(query)}`)
    if (!res.ok) return []
    const data = await res.json()
    return data.matches?.slice(0, 4).map((m: any) => m.title) || []
  } catch (e) {
    return []
  }
}
