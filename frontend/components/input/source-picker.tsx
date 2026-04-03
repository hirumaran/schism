'use client'

import { Check } from 'lucide-react'

const SOURCES = [
  { id: 'arxiv', label: 'arXiv' },
  { id: 'semantic_scholar', label: 'Semantic Scholar' },
  { id: 'pubmed', label: 'PubMed' },
  { id: 'openalex', label: 'OpenAlex' },
]

interface SourcePickerProps {
  selected: string[]
  onChange: (sources: string[]) => void
  maxResults: number
  onMaxResultsChange: (value: number) => void
}

export function SourcePicker({
  selected,
  onChange,
  maxResults,
  onMaxResultsChange,
}: SourcePickerProps) {
  const toggleSource = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  return (
    <div className="space-y-4 mt-4">
      <div className="flex flex-wrap gap-2">
        {SOURCES.map((source) => {
          const isSelected = selected.includes(source.id)
          return (
            <button
              key={source.id}
              onClick={() => toggleSource(source.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border transition-colors ${
                isSelected
                  ? 'bg-foreground text-background border-foreground'
                  : 'bg-background text-muted-foreground border-border hover:border-foreground/30'
              }`}
            >
              {isSelected && <Check className="w-3 h-3" />}
              {source.label}
            </button>
          )
        })}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm">Max papers</label>
          <span className="text-sm text-muted-foreground">{maxResults} papers</span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          step={10}
          value={maxResults}
          onChange={(e) => onMaxResultsChange(Number(e.target.value))}
          className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer accent-foreground"
        />
        <p className="text-xs text-muted-foreground">
          More papers = better coverage, slower analysis
        </p>
      </div>
    </div>
  )
}
