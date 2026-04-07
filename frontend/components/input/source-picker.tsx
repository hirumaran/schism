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
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border transition-all duration-200 ${
                  isSelected
                    ? 'bg-[#2A1D00] dark:bg-[#2A1D00] border-[#B87333] dark:border-[#B87333]/70 text-[#F0A830] dark:text-[#F0A830] shadow-sm'
                    : 'bg-[#1C1500] dark:bg-[#1C1500] border-[#3D2E00] dark:border-[#3D2E00]/70 text-[#78624A] dark:text-[#78624A] hover:bg-[#221A00] dark:hover:bg-[#221A00] hover:border-[#6B4F1A] dark:hover:border-[#6B4F1A]/70 hover:text-[#A07840] dark:hover:text-[#A07840]'
                }`}
              >
                {isSelected && <Check className="w-3 h-3 text-[#F0A830] dark:text-[#F0A830]" />}
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
