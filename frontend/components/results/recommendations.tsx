import { useEffect, useState } from 'react'
import { ApiError } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Skeleton } from '@/components/ui/skeleton'

interface RecommendationsResponse {
  videos: any[]
  web_resources: any[]
  generated_at: string
}

interface RecommendationsProps {
  jobId: string
  searchQueries: string[]
}

export function Recommendations({ jobId, searchQueries }: RecommendationsProps) {
  const [data, setData] = useState<RecommendationsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const { settings } = useStore()

  useEffect(() => {
    let mounted = true
    const fetchRecs = async () => {
      try {
        const response = await fetch(`/api/reports/${jobId}/recommendations`)
        if (!response.ok) throw new Error('Failed to fetch')
        const result = await response.json()
        if (mounted) {
          setData(result)
          setLoading(false)
        }
      } catch (err) {
        if (mounted) {
          setData({ videos: [], web_resources: [], generated_at: '' })
          setLoading(false)
        }
      }
    }
    fetchRecs()
    return () => { mounted = false }
  }, [jobId])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
        <h3 className="text-2xl font-serif">Learn More</h3>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-48 w-64 rounded-xl flex-shrink-0" />
          ))}
        </div>
        <div className="space-y-4">
          {[1, 2].map(i => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (!data || (data.videos.length === 0 && data.web_resources.length === 0)) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 space-y-4 border-t mt-12">
        <h3 className="text-2xl font-serif">Learn More</h3>
        <p className="text-muted-foreground">
          We couldn't load external resources right now. Try searching for:
        </p>
        <div className="flex flex-wrap gap-2 pt-2">
          {searchQueries.map((query, i) => (
            <a 
              key={i} 
              href={`https://www.google.com/search?q=${encodeURIComponent(query)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-full text-sm font-medium transition-colors"
            >
              {query}
            </a>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-10 border-t mt-12">
      <h3 className="text-2xl font-serif">Learn More</h3>

      {data.videos.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-lg font-medium flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-destructive"><path d="M2.27 16.126A10 10 0 0 1 12 2a10 10 0 0 1 9.73 14.126 1 1 0 0 1-.84.664l-4.14.734a1 1 0 0 0-.69.34l-2.45 2.822a1 1 0 0 1-1.56 0l-2.45-2.822a1 1 0 0 0-.69-.34l-4.14-.734a1 1 0 0 1-.84-.664Z"/><path d="M10 8.5v7l5-3.5-5-3.5Z"/></svg>
            Video Explainers
          </h4>
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x">
            {data.videos.map((video, i) => (
              <div key={i} className="snap-start flex-shrink-0 w-72 rounded-xl overflow-hidden border bg-card hover:shadow-md transition-shadow">
                {video.thumbnail_url ? (
                  <div className="aspect-video relative overflow-hidden bg-muted">
                    <img src={video.thumbnail_url} alt={video.title} className="object-cover w-full h-full" />
                  </div>
                ) : (
                  <div className="aspect-video bg-muted flex items-center justify-center text-muted-foreground">
                    No thumbnail
                  </div>
                )}
                <div className="p-4 space-y-2">
                  <h5 className="font-medium line-clamp-2 text-sm leading-snug" title={video.title}>{video.title}</h5>
                  {video.channel && <p className="text-xs text-muted-foreground">{video.channel}</p>}
                  <a 
                    href={video.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="inline-block mt-2 text-xs font-semibold text-primary hover:underline"
                  >
                    {video.is_search_fallback ? 'Search YouTube' : 'Watch on YouTube'}
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.web_resources.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-lg font-medium flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-blue-500"><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"/><path d="m21 3-9 9"/><path d="M15 3h6v6"/></svg>
            Web Resources
          </h4>
          <div className="grid gap-4">
            {data.web_resources.map((res, i) => (
              <a 
                key={i} 
                href={res.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="block p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <h5 className="font-medium text-foreground group-hover:text-primary transition-colors">{res.title}</h5>
                    {res.source_domain && <p className="text-xs text-muted-foreground">{res.source_domain}</p>}
                    <p className="text-sm text-foreground/80 line-clamp-2 mt-2">{res.description_snippet}</p>
                  </div>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground flex-shrink-0 group-hover:text-primary"><path d="m9 18 6-6-6-6"/></svg>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
