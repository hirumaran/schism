'use client'

import type { ContradictionPair } from '@/lib/types'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface ClaimsSidebarProps {
  results: ContradictionPair[]
  activePairId: string | null
  onPairClick: (pairId: string) => void
}

export function ClaimsSidebar({ results, activePairId, onPairClick }: ClaimsSidebarProps) {
  const getTypeBadge = (type: string | null) => {
    switch (type) {
      case 'direct': return 'bg-red-100 text-red-700 border-red-200'
      case 'conditional': return 'bg-amber-100 text-amber-700 border-amber-200'
      case 'methodological': return 'bg-gray-100 text-gray-700 border-gray-200'
      default: return 'bg-gray-100 text-gray-700 border-gray-200'
    }
  }

  const getScoreColor = (score: number) => {
    if (score > 0.8) return 'text-red-600'
    if (score >= 0.6) return 'text-amber-600'
    return 'text-green-600'
  }

  return (
    <>
      {/* Mobile Dropdown */}
      <div className="md:hidden p-4 border-b border-border bg-background sticky top-14 z-10">
        <Select value={activePairId || ''} onValueChange={onPairClick}>
          <SelectTrigger className="w-full h-auto py-2">
            <SelectValue placeholder="Select a contradiction to view" />
          </SelectTrigger>
          <SelectContent>
            {results.map((pair) => (
              <SelectItem key={pair.pair_key} value={pair.pair_key} className="py-2">
                <div className="flex flex-col gap-1 text-left whitespace-normal max-w-[80vw]">
                  <span className="font-serif text-sm line-clamp-1">{pair.paper_a.title}</span>
                  <span className="text-xs text-muted-foreground italic">vs</span>
                  <span className="font-serif text-sm line-clamp-1">{pair.paper_b.title}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Desktop Sidebar */}
      <div className="hidden md:flex flex-col w-[280px] flex-shrink-0 sticky top-14 h-[calc(100vh-56px)] border-r border-border">
        <div className="p-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Contradictions ({results.length})
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {results.map((pair) => {
            const isActive = activePairId === pair.pair_key
            return (
              <button
                key={pair.pair_key}
                onClick={() => onPairClick(pair.pair_key)}
                className={`w-full text-left p-3 rounded-lg transition-all border ${
                  isActive
                    ? 'bg-accent border-border shadow-sm'
                    : 'border-transparent hover:bg-accent/50 hover:border-border/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`px-1.5 py-0.5 text-[10px] uppercase font-semibold rounded border ${getTypeBadge(pair.type)}`}>
                    {pair.type || 'unknown'}
                  </span>
                  <span className={`text-xs font-bold ${getScoreColor(pair.score)}`}>
                    {Math.round(pair.score * 100)}%
                  </span>
                </div>
                
                <div className="space-y-1.5">
                  <p className="font-serif text-sm line-clamp-2 leading-snug" title={pair.paper_a.title}>
                    {pair.paper_a.title}
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="h-px flex-1 bg-border/60"></div>
                    <span className="text-[10px] text-muted-foreground italic font-medium">vs</span>
                    <div className="h-px flex-1 bg-border/60"></div>
                  </div>
                  <p className="font-serif text-sm line-clamp-2 leading-snug" title={pair.paper_b.title}>
                    {pair.paper_b.title}
                  </p>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </>
  )
}
