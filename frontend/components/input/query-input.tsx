'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useAutocomplete } from '@/lib/use-autocomplete'
import { AutocompleteDropdown } from './autocomplete-dropdown'
import { addToSearchHistory, removeFromSearchHistory } from '@/lib/search-history'

interface QueryInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (overrideQuery?: string) => void
}

export function QueryInput({ value, onChange, onSubmit }: QueryInputProps) {
  const [isFocused, setIsFocused] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  
  const { suggestions, loading, clear } = useAutocomplete(value, isFocused)

  // Reset selected index when query changes
  useEffect(() => {
    setSelectedIndex(-1)
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (suggestions.length > 0) {
        setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev))
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (suggestions.length > 0) {
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : -1))
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectedIndex >= 0 && suggestions[selectedIndex]) {
        const text = suggestions[selectedIndex].text
        onChange(text)
        addToSearchHistory(text)
        setIsFocused(false)
        onSubmit(text)
      } else if (value.trim()) {
        addToSearchHistory(value.trim())
        setIsFocused(false)
        onSubmit(value.trim())
      }
    } else if (e.key === 'Escape') {
      setIsFocused(false)
      inputRef.current?.blur()
    }
  }

  const handleSelect = (text: string) => {
    onChange(text)
    addToSearchHistory(text)
    setIsFocused(false)
    onSubmit(text)
  }

  const handleRemoveHistory = (text: string) => {
    removeFromSearchHistory(text)
    // Small hack to re-trigger autocomplete hook logic by toggling focus briefly
    setIsFocused(false)
    setTimeout(() => setIsFocused(true), 10)
  }

  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => {
          // Delay hiding dropdown so clicks can register
          setTimeout(() => setIsFocused(false), 200)
        }}
        onKeyDown={handleKeyDown}
        placeholder="e.g. vitamin D and depression, omega-3 cardiovascular"
        className="w-full h-[52px] px-4 text-base border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-shadow"
      />
      
      {isFocused && (
        <AutocompleteDropdown
          suggestions={suggestions}
          selectedIndex={selectedIndex}
          onSelect={handleSelect}
          onRemove={handleRemoveHistory}
        />
      )}
    </div>
  )
}
