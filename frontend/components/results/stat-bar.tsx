'use client'

import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { exportReport, ApiError } from '@/lib/api'
import { useStore } from '@/lib/store'
import type { Report } from '@/lib/types'

interface StatBarProps {
  report: Report
  totalResults: number
  paperCount: number
}

export function StatBar({ report, totalResults, paperCount }: StatBarProps) {
  const { settings, addToast } = useStore()
  const [exporting, setExporting] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)

  const handleExport = async (format: 'json' | 'csv') => {
    setShowDropdown(false)
    setExporting(true)
    try {
      const blob = await exportReport(report.id, format, settings)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `schism-results-${report.id}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      if (err instanceof ApiError) {
        addToast('Export failed', 'error')
      }
    }
    setExporting(false)
  }

  return (
    <div className="border-b border-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-serif text-2xl">{totalResults} contradictions found</span>
            <span className="text-sm text-muted-foreground">in {paperCount} papers analyzed</span>
          </div>
          {report.input_paper && (
            <p className="text-sm text-muted-foreground mt-1">
              Your paper: {report.input_paper.title}
            </p>
          )}
        </div>

        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            disabled={exporting}
            className="flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
          >
            {exporting ? 'Exporting...' : 'Export'}
            <ChevronDown className="w-4 h-4" />
          </button>
          {showDropdown && (
            <div className="absolute top-full right-0 mt-1 w-40 bg-background border border-border rounded-md shadow-lg z-10">
              <button
                onClick={() => handleExport('json')}
                className="w-full px-3 py-2 text-sm text-left hover:bg-accent"
              >
                Download JSON
              </button>
              <button
                onClick={() => handleExport('csv')}
                className="w-full px-3 py-2 text-sm text-left hover:bg-accent"
              >
                Download CSV
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
