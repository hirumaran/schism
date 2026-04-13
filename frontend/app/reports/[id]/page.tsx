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
import { PaperBreakdown } from '@/components/results/paper-breakdown'
import { Recommendations } from '@/components/results/recommendations'
import type { ContradictionType, AnalysisMode, ContradictionPair } from '@/lib/types'

export default function ReportsPage() {
  const params = useParams()
  const reportId = params.id as string
  const { settings, addToast } = useStore()

  const [typeFilter, setTypeFilter] = useState<ContradictionType | 'all'>('all')
  const [modeFilter, setModeFilter] = useState<AnalysisMode | 'all'>('all')
  const [activePairId, setActivePairId] = useState<string | null>(null)
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
      if (initialResults.results.length > 0 && !activePairId) {
        setActivePairId(initialResults.results[0].pair_key)
      }
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

  // Filter results client-side
  const filteredResults = allResults.filter((pair) => {
    if (typeFilter !== 'all' && pair.type !== typeFilter) return false
    if (modeFilter !== 'all' && pair.mode !== modeFilter) return false
    return true
  })

  // Ensure active pair is valid after filtering
  useEffect(() => {
    if (filteredResults.length > 0) {
      const activeExists = filteredResults.some(p => p.pair_key === activePairId)
      if (!activeExists) setActivePairId(filteredResults[0].pair_key)
    }
  }, [filteredResults, activePairId])

  const clearFilters = () => {
    setTypeFilter('all')
    setModeFilter('all')
  }

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

  const activePair = filteredResults.find(p => p.pair_key === activePairId) || filteredResults[0]

  const searchQueries = []
  if (report.paper_breakdown?.search_queries) {
    searchQueries.push(...report.paper_breakdown.search_queries.youtube)
    searchQueries.push(...report.paper_breakdown.search_queries.academic)
    searchQueries.push(...report.paper_breakdown.search_queries.general)
  }

  return (
    <div className="pt-14 min-h-screen bg-background">
      <StatBar report={report} totalResults={total} paperCount={paperCount} />
      
      {allResults.length > 0 && (
        <FilterBar
          typeFilter={typeFilter}
          modeFilter={modeFilter}
          onTypeChange={setTypeFilter}
          onModeChange={setModeFilter}
          hasPaperMode={hasPaperMode}
        />
      )}

      {allResults.length > 0 ? (
        <div className="flex flex-col md:flex-row relative">
          <ClaimsSidebar
            results={filteredResults}
            activePairId={activePairId}
            onPairClick={setActivePairId}
          />

          <div className="flex-1 max-w-[1200px] mx-auto w-full">
            {filteredResults.length === 0 ? (
              <div className="text-center py-20">
                <p className="text-muted-foreground mb-4">No contradictions match this filter.</p>
                <button
                  onClick={clearFilters}
                  className="px-4 py-2 text-sm font-medium text-primary bg-primary/10 hover:bg-primary/20 rounded-md transition-colors"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="p-4 md:p-8">
                {activePair && <ContradictionCard pair={activePair} />}
                
                {allResults.length < total && (
                  <div className="mt-8 flex justify-center">
                    <button
                      onClick={loadMore}
                      disabled={loadingMore}
                      className="px-6 py-2.5 text-sm font-medium text-foreground bg-accent hover:bg-accent/80 border border-border rounded-full shadow-sm disabled:opacity-50 transition-all"
                    >
                      {loadingMore ? 'Loading more...' : `Load more contradictions (${allResults.length} of ${total})`}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="w-full">
          {/* Replaced empty state with the breakdown component entirely if available */}
          {!report.paper_breakdown && (
            <div className="p-12 max-w-lg mx-auto text-center border mt-12 rounded-xl bg-card">
              <h2 className="font-serif text-2xl mb-3">Analysis Complete</h2>
              <p className="text-muted-foreground mb-6">
                Run analysis again to see a detailed paper breakdown for this job.
              </p>
              <Link
                href="/"
                className="inline-flex items-center justify-center px-4 py-2 bg-primary text-primary-foreground font-medium rounded-md hover:bg-primary/90 transition-colors shadow-sm"
              >
                Try another search
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Paper Breakdown Section (shows below contradictions, or replaces the no-contradictions dead end) */}
      {report.paper_breakdown && (
        <div className={allResults.length > 0 ? "border-t border-border bg-muted/10 pb-8" : "bg-background pb-8"}>
          {allResults.length > 0 && (
            <div className="max-w-4xl mx-auto px-4 pt-16 pb-4">
              <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">Analysis Complete</h2>
              <h3 className="text-3xl font-serif">Paper Breakdown</h3>
            </div>
          )}
          <PaperBreakdown breakdown={report.paper_breakdown} />
          
          <Recommendations 
            jobId={reportId} 
            searchQueries={searchQueries.filter(Boolean)} 
          />
        </div>
      )}
    </div>
  )
}
