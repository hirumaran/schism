'use client'

import type { ContradictionPair, Paper } from '@/lib/types'

interface ClaimsSidebarProps {
  results: ContradictionPair[]
  activeClaimId: string | null
  onClaimClick: (paperId: string) => void
}

export function ClaimsSidebar({ results, activeClaimId, onClaimClick }: ClaimsSidebarProps) {
  // Get unique papers with their max scores
  const papersMap = new Map<string, { paper: Paper; maxScore: number }>()

  results.forEach((pair) => {
    const updatePaper = (paper: Paper, score: number) => {
      const existing = papersMap.get(paper.id)
      if (!existing || score > existing.maxScore) {
        papersMap.set(paper.id, { paper, maxScore: score })
      }
    }
    updatePaper(pair.paper_a, pair.score)
    updatePaper(pair.paper_b, pair.score)
  })

  const papers = Array.from(papersMap.values()).sort((a, b) => b.maxScore - a.maxScore)

  const getDotColor = (score: number) => {
    if (score > 0.8) return 'bg-red-500'
    if (score >= 0.6) return 'bg-amber-500'
    return 'bg-green-500'
  }

  const getSourceLabel = (source: string) => {
    const labels: Record<string, string> = {
      arxiv: 'arXiv',
      semantic_scholar: 'Semantic Scholar',
      pubmed: 'PubMed',
      openalex: 'OpenAlex',
      user_input: 'Your paper',
    }
    return labels[source] || source
  }

  return (
    <div className="w-[280px] flex-shrink-0 sticky top-14 h-[calc(100vh-56px)] overflow-y-auto border-r border-border p-4">
      <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
        Claims
      </h2>
      <div className="space-y-2">
        {papers.map(({ paper, maxScore }) => (
          <button
            key={paper.id}
            onClick={() => onClaimClick(paper.id)}
            className={`w-full text-left p-2 rounded-md transition-colors ${
              activeClaimId === paper.id
                ? 'bg-accent border border-foreground/20'
                : 'hover:bg-accent/50'
            }`}
          >
            <div className="flex items-start gap-2">
              <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${getDotColor(maxScore)}`} />
              <div className="min-w-0">
                <p className="font-serif text-sm line-clamp-2">{paper.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {paper.year} · {getSourceLabel(paper.source)}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
