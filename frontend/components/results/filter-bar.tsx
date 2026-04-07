'use client'

import type { ContradictionType, AnalysisMode } from '@/lib/types'

interface FilterBarProps {
  typeFilter: ContradictionType | 'all'
  modeFilter: AnalysisMode | 'all'
  onTypeChange: (type: ContradictionType | 'all') => void
  onModeChange: (mode: AnalysisMode | 'all') => void
  hasPaperMode: boolean
}

export function FilterBar({
  typeFilter,
  modeFilter,
  onTypeChange,
  onModeChange,
  hasPaperMode,
}: FilterBarProps) {
  const types: { value: ContradictionType | 'all'; label: string; dot?: string }[] = [
    { value: 'all', label: 'All types' },
    { value: 'direct', label: 'Direct', dot: 'bg-red-500' },
    { value: 'conditional', label: 'Conditional', dot: 'bg-amber-500' },
    { value: 'methodological', label: 'Methodological', dot: 'bg-gray-400' },
  ]

  return (
    <div className="border-b border-border px-6 py-3 flex items-center gap-2 flex-wrap">
       {types.map((type) => (
         <button
           key={type.value}
           onClick={() => onTypeChange(type.value)}
           className={`flex items-center gap-1.5 px-3 py-1 text-sm rounded-full transition-colors ${
             typeFilter === type.value
               ? 'bg-foreground text-background'
               : 'text-muted-foreground hover:bg-accent'
           }`}
         >
           {type.dot && <span className={`w-2 h-2 rounded-full ${type.dot}`} />}
           {type.label}
         </button>
       ))}

       {hasPaperMode && (
         <>
           <span className="text-border">|</span>
            {[
              { value: 'all' as const, label: 'All' },
              { value: 'paper_vs_corpus' as const, label: 'vs. your paper' },
              { value: 'corpus_vs_corpus' as const, label: 'corpus-only' },
            ].map((mode) => (
              <button
                key={mode.value}
                onClick={() => onModeChange(mode.value)}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  modeFilter === mode.value
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:bg-accent'
                }`}
              >
                {mode.label}
              </button>
            ))}
         </>
       )}
    </div>
  )
}
