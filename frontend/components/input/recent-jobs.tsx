'use client'

import Link from 'next/link'
import { useStore } from '@/lib/store'
import { formatDistanceToNow } from 'date-fns'

export function RecentJobs() {
  const { recentJobs } = useStore()

  if (recentJobs.length === 0) return null

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done':
        return 'bg-green-100 text-green-700'
      case 'failed':
        return 'bg-red-100 text-red-700'
      case 'cancelled':
        return 'bg-gray-100 text-gray-700'
      default:
        return 'bg-amber-100 text-amber-700'
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
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
        Recent analyses
      </h3>
      <div className="space-y-2">
        {recentJobs.slice(0, 5).map((job) => {
          const href = getHref(job)
          const isClickable = href !== '#'

          return (
            <Link
              key={job.id}
              href={href}
              className={`flex items-center justify-between p-3 border border-border rounded-md ${
                isClickable ? 'hover:bg-accent/50' : 'opacity-60 cursor-default'
              }`}
              onClick={(e) => {
                if (!isClickable) e.preventDefault()
              }}
            >
              <span className="text-sm truncate max-w-[200px]">
                {job.query.slice(0, 50)}
                {job.query.length > 50 ? '...' : ''}
              </span>
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
            </Link>
          )
        })}
      </div>
    </div>
  )
}
