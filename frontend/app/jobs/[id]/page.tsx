'use client'

import { useEffect, useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useJobPolling } from '@/lib/polling'
import { cancelJob, ApiError } from '@/lib/api'
import { useStore } from '@/lib/store'
import { StageList } from '@/components/analyzing/stage-list'
import { ClaimsPreview } from '@/components/analyzing/claims-preview'
import { PROVIDER_LABELS } from '@/lib/api-client'
import type { Provider } from '@/lib/types'

export default function JobPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.id as string
  const { settings, updateRecentJob, addToast } = useStore()
  const [cancelling, setCancelling] = useState(false)
  const hasNotifiedFailover = useRef(false)

  const { data: job, error, isLoading } = useJobPolling(jobId, settings)

  useEffect(() => {
    if (job?.status === 'done') {
      updateRecentJob(jobId, { status: 'done', contradiction_count: job.contradiction_count })
      
      if (job.failover_occurred && job.provider_used && !hasNotifiedFailover.current) {
        hasNotifiedFailover.current = true
        const providerName = PROVIDER_LABELS[job.provider_used as Provider] || job.provider_used
        addToast(`Primary provider unavailable. Analysis completed using ${providerName}.`, 'info')
      }

      const timeout = setTimeout(() => {
        router.push(`/reports/${jobId}`)
      }, 800)
      return () => clearTimeout(timeout)
    }
    if (job?.status === 'failed') {
      updateRecentJob(jobId, { status: 'failed' })
    }
  }, [job?.status, job?.contradiction_count, job?.failover_occurred, job?.provider_used, jobId, router, updateRecentJob, addToast])

  const handleCancel = async () => {
    if (!confirm('Cancel this analysis?')) return
    setCancelling(true)
    try {
      await cancelJob(jobId, settings)
      updateRecentJob(jobId, { status: 'cancelled' })
      router.push('/')
    } catch (err) {
      if (err instanceof ApiError) {
        addToast(`Failed to cancel: ${err.message}`, 'error')
      }
    }
    setCancelling(false)
  }

  if (isLoading) {
    return (
      <div className="pt-20 pb-16 px-6">
        <div className="max-w-[560px] mx-auto">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="pt-20 pb-16 px-6">
        <div className="max-w-[560px] mx-auto">
          <div className="p-4 border border-destructive/20 bg-destructive/10 rounded-lg">
            <p className="text-destructive">
              {error instanceof ApiError ? error.message : 'Failed to load job'}
            </p>
          </div>
          <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="pt-20 pb-16 px-6">
        <div className="max-w-[560px] mx-auto">
          <p className="text-muted-foreground">Job not found</p>
          <Link href="/" className="inline-block mt-4 text-sm text-muted-foreground hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  if (job.status === 'failed') {
    return (
      <div className="pt-20 pb-16 px-6">
        <div className="max-w-[560px] mx-auto">
          <div className="p-4 border border-destructive/20 bg-destructive/10 rounded-lg">
            <h2 className="font-serif text-lg text-destructive mb-2">Analysis failed</h2>
            <p className="text-sm text-destructive/90">{job.error || 'An unknown error occurred'}</p>
            {job.failover_occurred && job.primary_error && (
              <p className="text-xs text-destructive/70 mt-2">
                Primary provider error: {job.primary_error}
              </p>
            )}
          </div>
          <div className="flex gap-3 mt-4">
            <Link
              href="/"
              className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent"
            >
              Try again
            </Link>
            {job.contradiction_count > 0 && (
              <Link
                href={`/reports/${jobId}`}
                className="px-4 py-2 text-sm bg-foreground text-background rounded-md hover:bg-foreground/90"
              >
                View partial results
              </Link>
            )}
          </div>
        </div>
      </div>
    )
  }

  const isTerminal = ['done', 'failed', 'cancelled'].includes(job.status)

  return (
    <div className="pt-20 pb-16 px-6">
      <div className="max-w-[560px] mx-auto">
        <div>
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Analyzing
          </span>
          <h1 className="font-serif text-2xl mt-1">{job.query}</h1>
          {job.mode === 'paper_vs_corpus' && (
            <span className="inline-block mt-2 px-2 py-0.5 text-xs bg-warning/15 text-warning rounded-full">
              Paper input mode
            </span>
          )}
        </div>

        <div className="mt-6">
          <div className="h-1 bg-accent rounded-full overflow-hidden">
            <div
              className="h-full bg-foreground transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            {job.progress}% complete
          </p>
        </div>

        <StageList job={job} />

        <ClaimsPreview
          jobId={jobId}
          settings={settings}
          isActive={!isTerminal && job.extracted_claim_count > 0}
        />

        {job.status === 'ingesting' && job.paper_count > 0 && (
          <p className="text-sm text-muted-foreground mt-6">
            {job.paper_count} papers found across sources
          </p>
        )}

        {!isTerminal && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="mt-8 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            {cancelling ? 'Cancelling...' : 'Cancel analysis'}
          </button>
        )}
      </div>
    </div>
  )
}
