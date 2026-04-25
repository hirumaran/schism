'use client'

import Link from 'next/link'
import { Trash2 } from 'lucide-react'
import { useStore } from '@/lib/store'
import { formatDistanceToNow } from 'date-fns'

export function RecentJobs() {
  const { recentJobs, removeRecentJob } = useStore()

  if (recentJobs.length === 0) return null

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done':
        return 'bg-success/15 text-success'
      case 'failed':
        return 'bg-destructive/15 text-destructive'
      case 'cancelled':
        return 'bg-muted text-muted-foreground'
      default:
        return 'bg-warning/15 text-warning'
    }
  }

  const getHref = (job: { id: string; status: string }) => {
    if (job.status === 'done') return `/reports/${job.id}`
    if (['pending', 'ingesting', 'embedding', 'analyzing'].includes(job.status)) {
      return `/jobs/${job.id}`
    }
    return '#'
  }

  return (
    <div className="mt-12">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Recent analyses
        </h3>
      </div>
      <div className="space-y-2">
        {recentJobs.slice(0, 5).map((job) => {
          const href = getHref(job)
          const isClickable = href !== '#'

          return (
            <div
              key={job.id}
              className={`flex items-center justify-between p-3 border border-border rounded-md ${
                isClickable ? 'hover:bg-accent/50' : 'opacity-60 cursor-default'
              }`}
            >
              <div className="flex items-center gap-3">
                <Link
                  href={href}
                  className={`flex-1 ${
                    isClickable ? 'hover:text-accent' : 'text-muted-foreground pointer-events-none'
                  }`}
                  onClick={(e) => {
                    if (!isClickable) e.preventDefault()
                  }}
                >
                  <span className="text-sm truncate max-w-[200px]">
                    {job.query.slice(0, 50)}
                    {job.query.length > 50 ? '...' : ''}
                  </span>
                </Link>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${getStatusColor(job.status)}`}>
                    {job.status === 'pending' || job.status === 'ingesting' || job.status === 'embedding' || job.status === 'analyzing'
                      ? 'running'
                      : job.status}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
                  </span>
                </div>
              </div>
              <button
                onClick={() => removeRecentJob(job.id)}
                className="p-1 rounded-full hover:bg-accent/20 text-muted-foreground hover:text-accent transition-colors"
                aria-label="Remove from history"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
