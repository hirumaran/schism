import React from 'react'
import { Clock, TrendingUp, FileText, Lightbulb, Search, X } from 'lucide-react'
import { AutocompleteSuggestion } from '@/lib/use-autocomplete'
import { removeFromSearchHistory } from '@/lib/search-history'

interface AutocompleteDropdownProps {
  suggestions: AutocompleteSuggestion[]
  selectedIndex: number
  onSelect: (text: string) => void
  onRemove?: (text: string) => void
}

export function AutocompleteDropdown({
  suggestions,
  selectedIndex,
  onSelect,
  onRemove
}: AutocompleteDropdownProps) {
  if (!suggestions.length) return null

  return (
    <div className="absolute top-full left-0 right-0 mt-2 bg-popover border border-border rounded-lg shadow-lg overflow-hidden z-50 py-2">
      <ul className="max-h-80 overflow-y-auto">
        {suggestions.map((suggestion, index) => {
          const isSelected = index === selectedIndex
          const Icon = getTierIcon(suggestion.tier)

          return (
            <li
              key={`${suggestion.tier}-${suggestion.text}-${index}`}
              className={`flex items-center justify-between px-4 py-2 cursor-pointer transition-colors ${
                isSelected
                  ? 'bg-accent/15 text-foreground'
                  : 'text-muted-foreground hover:bg-accent/10 hover:text-foreground'
              }`}
              onMouseDown={(e) => {
                e.preventDefault() // prevent input blur
                onSelect(suggestion.text)
              }}
            >
              <div className="flex items-center flex-1 gap-3 overflow-hidden">
                <Icon className="w-4 h-4 flex-shrink-0 opacity-70" />
                <span className="truncate">{suggestion.text}</span>
              </div>
              
              {suggestion.tier === 'recent' && (
                <button
                  type="button"
                  className="p-1 ml-2 text-muted-foreground hover:text-destructive rounded-md transition-colors"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    if (onRemove) onRemove(suggestion.text)
                    else {
                      removeFromSearchHistory(suggestion.text)
                      // Optionally we could force a refresh here, but handled by parent if needed
                    }
                  }}
                  title="Remove from history"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function getTierIcon(tier: AutocompleteSuggestion['tier']) {
  switch (tier) {
    case 'recent':
      return Clock
    case 'popular':
      return TrendingUp
    case 'paper':
      return FileText
    case 'topic':
      return Lightbulb
    default:
      return Search
  }
}
