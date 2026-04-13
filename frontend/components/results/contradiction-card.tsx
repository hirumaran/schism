'use client'

import { ExternalLink, Copy, AlertTriangle } from 'lucide-react'
import { useStore } from '@/lib/store'
import type { ContradictionPair, Paper } from '@/lib/types'
import { ReactNode } from 'react'

interface ContradictionCardProps {
  pair: ContradictionPair
}

function HighlightedAbstract({ text, claim }: { text: string | null; claim: string | null }) {
  if (!text) return <p className="text-sm italic opacity-50">No abstract available</p>
  if (!claim) return <p className="text-sm">{text}</p>

  // Try to find the exact claim in the abstract
  const claimIndex = text.toLowerCase().indexOf(claim.toLowerCase())
  
  if (claimIndex !== -1) {
    const before = text.substring(0, claimIndex)
    const match = text.substring(claimIndex, claimIndex + claim.length)
    const after = text.substring(claimIndex + claim.length)
    
    return (
      <div className="text-sm leading-relaxed space-y-4">
        <p>
          {before}
          <mark className="bg-amber-200/60 dark:bg-amber-900/40 text-amber-900 dark:text-amber-100 rounded-sm px-1 py-0.5">{match}</mark>
          {after}
        </p>
      </div>
    )
  }

  // Fallback: claim not found inline
  return (
    <div className="text-sm leading-relaxed space-y-4">
      <p>{text}</p>
      <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200/50 dark:border-amber-900/50 rounded-md">
        <p className="text-xs font-semibold text-amber-800 dark:text-amber-400 mb-1 uppercase tracking-wider">Extracted Claim</p>
        <p className="text-amber-900 dark:text-amber-100 font-medium italic">{claim}</p>
      </div>
    </div>
  )
}

function PaperColumn({ paper, claim, label }: { paper: Paper; claim: string | null; label: string }) {
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
    if (!authors || authors.length === 0) return 'Unknown authors'
    if (authors.length === 1) return authors[0]
    if (authors.length === 2) return authors.join(' & ')
    return `${authors[0]} et al.`
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-card rounded-xl border border-border shadow-sm overflow-hidden">
      <div className="p-4 sm:p-6 border-b border-border bg-muted/30">
        <div className="flex items-center justify-between mb-3">
          <span className="inline-flex px-2 py-0.5 text-[10px] font-medium tracking-wider bg-accent text-accent-foreground rounded uppercase">
            {getSourceLabel(paper.source)}
          </span>
          <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            {label}
          </span>
        </div>
        
        {paper.url ? (
          <a
            href={paper.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block font-serif text-lg font-medium hover:underline text-foreground leading-snug"
          >
            {paper.title}
          </a>
        ) : (
          <h3 className="font-serif text-lg font-medium text-foreground leading-snug">{paper.title}</h3>
        )}
        
        <p className="text-sm text-muted-foreground mt-2 font-medium">
          {formatAuthors(paper.authors)} · {paper.year || 'N/A'}
        </p>
      </div>
      
      <div className="p-4 sm:p-6 flex-1 overflow-y-auto min-h-[300px] text-foreground/90">
        <HighlightedAbstract text={paper.abstract} claim={claim} />
      </div>
    </div>
  )
}

export function ContradictionCard({ pair }: ContradictionCardProps) {
  const { addToast } = useStore()

  const getTypeBadge = () => {
    switch (pair.type) {
      case 'direct':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'conditional':
        return 'bg-amber-100 text-amber-800 border-amber-200'
      case 'methodological':
        return 'bg-slate-100 text-slate-800 border-slate-200'
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200'
    }
  }

  const getScoreColor = () => {
    if (pair.score > 0.8) return 'text-red-600'
    return 'text-amber-600'
  }

  const getBarColor = () => {
    if (pair.score > 0.8) return 'bg-gradient-to-r from-red-500 to-red-600'
    return 'bg-gradient-to-r from-amber-500 to-amber-600'
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
    <div className="w-full flex flex-col gap-6 animate-in fade-in duration-300">
      {/* Top Header / Score */}
      <div className="bg-card rounded-xl border border-border p-4 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className={`px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-md border ${getTypeBadge()}`}>
                {pair.type}
              </span>
              <span className={`text-2xl font-bold tracking-tight ${getScoreColor()}`}>
                {Math.round(pair.score * 100)}% Contradiction
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={handleCopy}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors"
              title="Copy details"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="h-2.5 bg-muted rounded-full overflow-hidden w-full shadow-inner">
          <div
            className={`h-full ${getBarColor()} transition-all duration-1000 ease-out`}
            style={{ width: `${pair.score * 100}%` }}
          />
        </div>
        
        {yearGap > 15 && (
          <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Score adjusted for {yearGap}-year gap between papers
          </p>
        )}
      </div>

      {/* Split View */}
      <div className="flex flex-col lg:flex-row gap-6">
        <PaperColumn paper={pair.paper_a} claim={pair.paper_a_claim} label="Paper A" />
        
        <div className="hidden lg:flex items-center justify-center -mx-3 z-10">
          <div className="w-8 h-8 rounded-full bg-background border border-border shadow-sm flex items-center justify-center text-xs font-bold text-muted-foreground italic">
            VS
          </div>
        </div>
        
        <PaperColumn paper={pair.paper_b} claim={pair.paper_b_claim} label="Paper B" />
      </div>

      {/* Analysis Details */}
      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden mb-8">
        <div className="p-4 sm:p-6 border-b border-border bg-muted/30">
          <h3 className="font-serif text-lg font-medium flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary"><path d="m21 16-4-4-4 4"/><path d="M17 21V8"/><path d="m3 8 4-4 4 4"/><path d="M7 3v13"/></svg>
            Analysis & Reasoning
          </h3>
        </div>
        
        <div className="p-4 sm:p-6 space-y-6">
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Explanation</h4>
            <p className="text-base text-foreground/90 leading-relaxed">{pair.explanation}</p>
          </div>

          {pair.key_difference && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Key Difference</h4>
              <p className="text-base font-medium text-foreground">{pair.key_difference}</p>
            </div>
          )}

          {pair.could_both_be_true && (
            <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-amber-800 dark:text-amber-400">Contextual Compatibility</h4>
                <p className="text-sm text-amber-700/90 dark:text-amber-500/90 mt-1 leading-relaxed">
                  These findings may not be mutually exclusive. The contradiction could be explained by methodological differences, different populations, or distinct experimental conditions rather than one paper being factually incorrect.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
