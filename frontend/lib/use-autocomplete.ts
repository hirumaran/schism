import { useState, useEffect } from 'react'
import { getSearchHistory } from './search-history'
import { fetchPaperSuggestions } from './semantic-scholar-autocomplete'
import { fetchPopularQueries } from './api-client'

export interface AutocompleteSuggestion {
  text: string
  tier: 'recent' | 'popular' | 'paper' | 'topic'
}

export interface UseAutocompleteResult {
  suggestions: AutocompleteSuggestion[]
  loading: boolean
  clear: () => void
}

const STATIC_TOPICS = [
  "vitamin D and depression", "omega-3 cardiovascular", 
  "CRISPR gene editing", "mRNA vaccine efficacy",
  "gut microbiome mental health", "machine learning drug discovery",
  "sleep deprivation cognitive function", "intermittent fasting metabolic"
]

export function useAutocomplete(query: string, enabled: boolean): UseAutocompleteResult {
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled) {
      setSuggestions([])
      setLoading(false)
      return
    }

    const q = query.trim().toLowerCase()
    
    // Tier 1: Recent (max 3)
    const history = getSearchHistory()
    const recentMatches = q
      ? history.filter(item => item.toLowerCase().includes(q)).slice(0, 3)
      : history.slice(0, 3)
      
    const recentSuggestions: AutocompleteSuggestion[] = recentMatches.map(text => ({ text, tier: 'recent' }))
    const seen = new Set<string>(recentMatches.map(item => item.toLowerCase()))
    
    if (!q) {
      // Empty query fallback to recent only or top static topics
      const topicMatches = STATIC_TOPICS.filter(t => !seen.has(t.toLowerCase())).slice(0, 6)
      const topicSuggestions: AutocompleteSuggestion[] = topicMatches.map(text => ({ text, tier: 'topic' }))
      
      const merged = [...recentSuggestions, ...topicSuggestions].slice(0, 10)
      setSuggestions(merged)
      setLoading(false)
      return
    }

    // Debounce network calls
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        const [popular, papers] = await Promise.all([
          fetchPopularQueries(q, 5),
          fetchPaperSuggestions(q)
        ])
        
        // Tier 2: Popular (max 3)
        const popularSuggestions: AutocompleteSuggestion[] = []
        for (const item of popular) {
          if (!seen.has(item.toLowerCase()) && popularSuggestions.length < 3) {
            popularSuggestions.push({ text: item, tier: 'popular' })
            seen.add(item.toLowerCase())
          }
        }
        
        // Tier 3: Paper (max 4)
        const paperSuggestions: AutocompleteSuggestion[] = []
        for (const item of papers) {
          if (!seen.has(item.toLowerCase()) && paperSuggestions.length < 4) {
            paperSuggestions.push({ text: item, tier: 'paper' })
            seen.add(item.toLowerCase())
          }
        }
        
        // Tier 4: Topic (max 6)
        const topicMatches = STATIC_TOPICS.filter(t => t.toLowerCase().includes(q))
        const topicSuggestions: AutocompleteSuggestion[] = []
        for (const item of topicMatches) {
          if (!seen.has(item.toLowerCase()) && topicSuggestions.length < 6) {
            topicSuggestions.push({ text: item, tier: 'topic' })
            seen.add(item.toLowerCase())
          }
        }
        
        const merged = [
          ...recentSuggestions,
          ...popularSuggestions,
          ...paperSuggestions,
          ...topicSuggestions
        ].slice(0, 10)
        
        setSuggestions(merged)
      } catch (err) {
        console.error('Failed to fetch autocomplete suggestions:', err)
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query, enabled])

  return {
    suggestions,
    loading,
    clear: () => setSuggestions([])
  }
}
