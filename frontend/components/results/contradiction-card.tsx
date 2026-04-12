'use client'

import { ExternalLink, Copy, AlertTriangle } from 'lucide-react'
import { useStore } from '@/lib/store'
import type { ContradictionPair } from '@/lib/types'

interface ContradictionCardProps {
  pair: ContradictionPair
  isHighlighted: boolean
  id: string
}

export function ContradictionCard({ pair, isHighlighted, id }: ContradictionCardProps) {
  const { addToast } = useStore()

  const getTypeBadge = () => {
    switch (pair.type) {
      case 'direct':
        return 'bg-red-100 text-red-700'
      case 'conditional':
        return 'bg-amber-100 text-amber-700'
      case 'methodological':
        return 'bg-gray-100 text-gray-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  const getScoreColor = () => {
    if (pair.score > 0.8) return 'text-red-600'
    return 'text-amber-600'
  }

  const getBarColor = () => {
    if (pair.score > 0.8) return 'bg-red-500'
    return 'bg-amber-500'
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

  const formatAuthors = (authors: string[]) => {
    if (authors.length === 0) return 'Unknown authors'
    if (authors.length === 1) return authors[0]
    if (authors.length === 2) return authors.join(' & ')
    return `${authors[0]} et al.`
  }

  const handleCopy = () => {
    const text = `Paper A: ${pair.paper_a.title}\nClaim: ${pair.paper_a_claim || 'N/A'}\n\nPaper B: ${pair.paper_b.title}\nClaim: ${pair.paper_b_claim || 'N/A'}\n\nExplanation: ${pair.explanation}`
    navigator.clipboard.writeText(text)
    addToast('Copied to clipboard', 'success')
  }

  const yearGap = pair.paper_a.year && pair.paper_b.year
    ? Math.abs(pair.paper_a.year - pair.paper_b.year)
    : 0

  return (
    <div
      id={id}
      className={`bg-background border rounded-xl p-6 ${
        isHighlighted ? 'border-foreground/30 ring-2 ring-foreground/10' : 'border-border'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className={`px-2 py-0.5 text-xs rounded-full capitalize ${getTypeBadge()}`}>
          {pair.type}
        </span>
        <span className={`text-sm font-medium ${getScoreColor()}`}>
          {pair.score.toFixed(2)}
        </span>
      </div>

      <div className="h-[3px] bg-accent rounded-full overflow-hidden mb-4">
        <div
          className={`h-full ${getBarColor()}`}
          style={{ width: `${pair.score * 100}%` }}
        />
      </div>

      {/* Paper A */}
      <div className="mb-4">
        <span className="inline-block px-1.5 py-0.5 text-[10px] bg-accent rounded mb-1">
          {getSourceLabel(pair.paper_a.source)}
        </span>
        {pair.paper_a.url ? (
          <a
            href={pair.paper_a.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block font-serif text-base font-medium hover:underline"
          >
            {pair.paper_a.title}
          </a>
        ) : (
          <p className="font-serif text-base font-medium">{pair.paper_a.title}</p>
        )}
        <p className="text-xs text-muted-foreground mt-0.5">
          {formatAuthors(pair.paper_a.authors)} · {pair.paper_a.year || 'N/A'}
        </p>
        {pair.paper_a_claim ? (
          <p className="font-serif text-sm text-muted-foreground italic mt-2 pl-3 border-l-2 border-border">
            {pair.paper_a_claim}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground italic mt-2 pl-3 border-l-2 border-border opacity-50">
            No claim extracted
          </p>
        )}
      </div>

      {/* Divider */}
      <div className="flex items-center gap-4 my-4">
        <div className="flex-1 h-px bg-border" />
        <span className="text-sm text-muted-foreground">vs.</span>
        <div className="flex-1 h-px bg-border" />
      </div>

      {/* Paper B */}
      <div className="mb-4">
        <span className="inline-block px-1.5 py-0.5 text-[10px] bg-accent rounded mb-1">
          {getSourceLabel(pair.paper_b.source)}
        </span>
        {pair.paper_b.url ? (
          <a
            href={pair.paper_b.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block font-serif text-base font-medium hover:underline"
          >
            {pair.paper_b.title}
          </a>
        ) : (
          <p className="font-serif text-base font-medium">{pair.paper_b.title}</p>
        )}
        <p className="text-xs text-muted-foreground mt-0.5">
          {formatAuthors(pair.paper_b.authors)} · {pair.paper_b.year || 'N/A'}
        </p>
        {pair.paper_b_claim ? (
          <p className="font-serif text-sm text-muted-foreground italic mt-2 pl-3 border-l-2 border-border">
            {pair.paper_b_claim}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground italic mt-2 pl-3 border-l-2 border-border opacity-50">
            No claim extracted
          </p>
        )}
      </div>

      {/* Explanation */}
      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground mb-1">Why this contradicts</p>
        <p className="text-sm leading-relaxed">{pair.explanation}</p>
      </div>

      {/* Key difference */}
      {pair.key_difference && (
        <div className="mt-3">
          <p className="text-xs text-muted-foreground mb-1">Key difference</p>
          <p className="text-sm">{pair.key_difference}</p>
        </div>
      )}

      {/* Could both be true */}
      {pair.could_both_be_true && (
        <div className="flex items-center gap-2 mt-3 p-2 bg-amber-50 rounded-md">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span className="text-sm text-amber-700">
            These findings may not be mutually exclusive
          </span>
        </div>
      )}

      {/* Year gap note */}
      {yearGap > 15 && (
        <p className="text-xs text-muted-foreground mt-3">
          Score adjusted for {yearGap}-year gap between papers
        </p>
      )}

      {/* Bottom row */}
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
        <span className="text-xs text-muted-foreground">
          Topic cluster {pair.cluster_id}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded"
            title="Copy claim text"
          >
            <Copy className="w-4 h-4" />
          </button>
          {pair.paper_a.url && (
            <a
              href={pair.paper_a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-muted-foreground hover:text-foreground rounded"
              title="Open paper"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
