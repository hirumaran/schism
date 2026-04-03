'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useReport, useJobResults } from '@/lib/polling'
import { getJobResults, ApiError } from '@/lib/api'
import { useStore } from '@/lib/store'
import { StatBar } from '@/components/results/stat-bar'
import { FilterBar } from '@/components/results/filter-bar'
import { ClaimsSidebar } from '@/components/results/claims-sidebar'
import { ContradictionCard } from '@/components/results/contradiction-card'
import type { ContradictionType, AnalysisMode, ContradictionPair } from '@/lib/types'

export default function ReportsPage() {
  const params = useParams()
  const reportId = params.id as string
  const { settings, addToast } = useStore()

  const [typeFilter, setTypeFilter] = useState<ContradictionType | 'all'>('all')
  const [modeFilter, setModeFilter] = useState<AnalysisMode | 'all'>('all')
  const [activeClaimId, setActiveClaimId] = useState<string | null>(null)
  const [allResults, setAllResults] = useState<ContradictionPair[]>([])
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)

  const { data: report, isLoading: reportLoading, error: reportError } = useReport(reportId, settings)
  const { data: initialResults, isLoading: resultsLoading, error: resultsError } = useJobResults(
    reportId,
    settings,
    { limit: 50 }
  )

  useEffect(() => {
    if (initialResults) {
      setAllResults(initialResults.results)
      setTotal(initialResults.total)
    }
  }, [initialResults])

  const loadMore = useCallback(async () => {
    if (loadingMore || allResults.length >= total) return
    setLoadingMore(true)
    try {
      const more = await getJobResults(
        reportId,
        { limit: 50, offset: allResults.length },
        settings
      )
      setAllResults((prev) => [...prev, ...more.results])
    } catch (err) {
      if (err instanceof ApiError) {
        addToast('Failed to load more results', 'error')
      }
    }
    setLoadingMore(false)
  }, [loadingMore, allResults.length, total, reportId, settings, addToast])

  const handleClaimClick = (paperId: string) => {
    setActiveClaimId(paperId)
    // Find the first card that contains this paper
    const cardIndex = filteredResults.findIndex(
      (pair) => pair.paper_a.id === paperId || pair.paper_b.id === paperId
    )
    if (cardIndex !== -1) {
      const element = document.getElementById(`card-${cardIndex}`)
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  const clearFilters = () => {
    setTypeFilter('all')
    setModeFilter('all')
  }

  // Filter results client-side
  const filteredResults = allResults.filter((pair) => {
    if (typeFilter !== 'all' && pair.type !== typeFilter) return false
    if (modeFilter !== 'all' && pair.mode !== modeFilter) return false
    return true
  })

  // Check if any results are paper_vs_corpus
  const hasPaperMode = allResults.some((r) => r.mode === 'paper_vs_corpus')

  // Get unique paper count
  const paperIds = new Set<string>()
  allResults.forEach((pair) => {
    paperIds.add(pair.paper_a.id)
    paperIds.add(pair.paper_b.id)
  })
  const paperCount = paperIds.size

  if (reportLoading || resultsLoading) {
    return (
      <div className="pt-16">
        <div className="p-6">
          <p className="text-muted-foreground">Loading results...</p>
        </div>
      </div>
    )
  }

  if (reportError || resultsError) {
    return (
      <div className="pt-16">
        <div className="p-6">
          <div className="p-4 border border-red-200 bg-red-50 rounded-lg">
            <p className="text-red-700">
              {reportError instanceof ApiError
                ? reportError.message
                : resultsError instanceof ApiError
                  ? resultsError.message
                  : 'Failed to load report'}
            </p>
          </div>
          <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="pt-16">
        <div className="p-6">
          <p className="text-muted-foreground">Report not found</p>
          <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  if (allResults.length === 0) {
    return (
      <div className="pt-16">
        <div className="p-6 max-w-lg mx-auto text-center">
          <h2 className="font-serif text-2xl mb-2">No contradictions found</h2>
          <p className="text-muted-foreground mb-4">
            The analyzed papers did not contain significant contradictions above the threshold.
          </p>
          <Link
            href="/"
            className="inline-block px-4 py-2 bg-foreground text-background rounded-md hover:bg-foreground/90"
          >
            Try another search
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="pt-14">
      <StatBar report={report} totalResults={total} paperCount={paperCount} />
      <FilterBar
        typeFilter={typeFilter}
        modeFilter={modeFilter}
        onTypeChange={setTypeFilter}
        onModeChange={setModeFilter}
        hasPaperMode={hasPaperMode}
      />

      <div className="flex">
        <ClaimsSidebar
          results={filteredResults}
          activeClaimId={activeClaimId}
          onClaimClick={handleClaimClick}
        />

        <div className="flex-1 p-6 overflow-y-auto">
          {filteredResults.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground mb-3">No contradictions match this filter.</p>
              <button
                onClick={clearFilters}
                className="text-sm text-foreground hover:underline"
              >
                Clear filters
              </button>
            </div>
          ) : (
            <div className="space-y-4 max-w-3xl">
              {filteredResults.map((pair, i) => (
                <ContradictionCard
                  key={i}
                  id={`card-${i}`}
                  pair={pair}
                  isHighlighted={
                    activeClaimId === pair.paper_a.id || activeClaimId === pair.paper_b.id
                  }
                />
              ))}

              {allResults.length < total && (
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="w-full py-3 text-sm text-muted-foreground border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {loadingMore ? 'Loading...' : `Load more (${allResults.length} of ${total})`}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
