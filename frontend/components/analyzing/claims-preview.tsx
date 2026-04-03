'use client'

import { useLiveClaimsPreview } from '@/lib/polling'
import type { Settings } from '@/lib/types'

interface ClaimsPreviewProps {
  jobId: string
  settings: Settings
  isActive: boolean
}

export function ClaimsPreview({ jobId, settings, isActive }: ClaimsPreviewProps) {
  const { data } = useLiveClaimsPreview(jobId, settings, isActive)

  if (!data || data.results.length === 0) return null

  const getSourceBadge = (source: string) => {
    const labels: Record<string, string> = {
      arxiv: 'arXiv',
      semantic_scholar: 'S2',
      pubmed: 'PubMed',
      openalex: 'OpenAlex',
    }
    return labels[source] || source
  }

  return (
    <div className="mt-8 p-4 border border-border rounded-lg">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
        Claims extracted so far
      </h3>
      <div className="space-y-3">
        {data.results.slice(0, 3).map((pair, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="px-1.5 py-0.5 text-[10px] bg-accent rounded">
              {getSourceBadge(pair.paper_a.source)}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-serif line-clamp-2">
                {pair.paper_a.claim || pair.paper_a.title}
              </p>
              {pair.paper_a.claim_direction && (
                <span
                  className={`inline-block mt-1 px-1.5 py-0.5 text-[10px] rounded ${
                    pair.paper_a.claim_direction === 'positive'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {pair.paper_a.claim_direction}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
