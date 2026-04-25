'use client'

import { Check } from 'lucide-react'
import type { AnalysisJob } from '@/lib/types'

interface StageListProps {
  job: AnalysisJob
}

interface Stage {
  name: string
  getStatus: (job: AnalysisJob) => 'done' | 'active' | 'pending'
  getCounter?: (job: AnalysisJob) => string | null
}

const stages: Stage[] = [
  {
    name: 'Fetching papers',
    getStatus: (job) => {
      if (job.progress >= 25) return 'done'
      if (job.status === 'ingesting' || job.status === 'pending') return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.status === 'ingesting' || job.status === 'pending') {
        return `${job.paper_count} papers found`
      }
      return null
    },
  },
  {
    name: 'Deduplicating & filtering',
    getStatus: (job) => {
      if (job.progress >= 35) return 'done'
      if (job.progress >= 25) return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.progress >= 25 && job.progress < 35) {
        return `${job.paper_count} unique papers`
      }
      return null
    },
  },
  {
    name: 'Generating embeddings',
    getStatus: (job) => {
      if (job.progress >= 50) return 'done'
      if (job.status === 'embedding') return 'active'
      return 'pending'
    },
  },
  {
    name: 'Extracting claims',
    getStatus: (job) => {
      if (job.progress >= 70) return 'done'
      if (job.progress >= 55) return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.progress >= 55 && job.progress < 70) {
        return `${job.extracted_claim_count} extracted (${job.skipped_claim_count} skipped)`
      }
      return null
    },
  },
  {
    name: 'Clustering by topic',
    getStatus: (job) => {
      if (job.progress >= 75) return 'done'
      if (job.progress >= 70) return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.progress >= 75) {
        return `${job.cluster_count} topic clusters`
      }
      return null
    },
  },
  {
    name: 'Scoring contradictions',
    getStatus: (job) => {
      if (job.progress >= 95) return 'done'
      if (job.progress >= 80) return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.progress >= 80 && job.progress < 95) {
        return `${job.scored_pair_count} pairs scored (${job.cached_pair_count} from cache)`
      }
      return null
    },
  },
  {
    name: 'Finalizing results',
    getStatus: (job) => {
      if (job.progress === 100 || job.status === 'done') return 'done'
      if (job.progress >= 95) return 'active'
      return 'pending'
    },
    getCounter: (job) => {
      if (job.progress === 100 || job.status === 'done') {
        return `${job.contradiction_count} contradictions found`
      }
      return null
    },
  },
]

export function StageList({ job }: StageListProps) {
  return (
    <div className="space-y-3 mt-8">
      {stages.map((stage, i) => {
        const status = stage.getStatus(job)
        const counter = stage.getCounter?.(job)

        return (
          <div key={i} className="flex items-start gap-3">
            <div className="mt-0.5">
              {status === 'done' && (
                <div className="w-4 h-4 rounded-full bg-success flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 text-success-foreground" />
                </div>
              )}
              {status === 'active' && (
                <div className="w-4 h-4 rounded-full bg-warning animate-pulse" />
              )}
              {status === 'pending' && (
                <div className="w-4 h-4 rounded-full border-2 border-muted-foreground/30" />
              )}
            </div>
            <div className="flex-1">
              <span
                className={`text-sm ${
                  status === 'done'
                    ? 'text-foreground'
                    : status === 'active'
                      ? 'text-foreground font-medium'
                      : 'text-muted-foreground'
                }`}
              >
                {stage.name}
              </span>
              {counter && (
                <p className="text-xs text-muted-foreground mt-0.5">{counter}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
