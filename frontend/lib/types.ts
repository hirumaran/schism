export type Provider = 'anthropic' | 'openai' | 'ollama' | 'mock'

export type EmbeddingProvider = 'local' | 'openai' | 'cohere'

export type JobStatus =
  | 'pending'
  | 'ingesting'
  | 'embedding'
  | 'analyzing'
  | 'done'
  | 'failed'
  | 'cancelled'

export type ContradictionType = 'direct' | 'conditional' | 'methodological' | 'null'

export type AnalysisMode = 'corpus_vs_corpus' | 'paper_vs_corpus'

export interface Settings {
  provider: Provider
  apiKey: string
  model: string
  embeddingProvider: EmbeddingProvider
  baseUrl: string
  anthropicModel: string
  openaiModel: string
  ollamaModel: string
  cohereKey: string
}

export interface Paper {
  id: string
  title: string
  abstract: string
  authors: string[]
  year: number | null
  source: string
  url: string | null
  citation_count: number
  claim: string | null
  claim_direction: string | null
  magnitude: string | null
  population: string | null
  outcome: string | null
}

export interface ContradictionPair {
  paper_a: Paper
  paper_b: Paper
  score: number
  raw_score: number
  score_penalty: number
  type: ContradictionType
  explanation: string
  could_both_be_true: boolean
  key_difference: string | null
  mode: AnalysisMode
  cluster_id: number
}

export interface AnalysisJob {
  id: string
  query: string
  status: JobStatus
  progress: number
  paper_count: number
  extracted_claim_count: number
  skipped_claim_count: number
  cluster_count: number
  filtered_pair_count: number
  scored_pair_count: number
  contradiction_count: number
  error: string | null
  created_at: string
  completed_at: string | null
  has_contradictions: boolean
  cached_pair_count: number
  mode: AnalysisMode
}

export interface JobStats extends AnalysisJob {
  cache_hit_rate: number
  duration_ms: number | null
  cost_estimate: {
    claim_extraction_tokens: number
    contradiction_scoring_tokens: number
    total_tokens: number
  }
}

export interface JobResults {
  job_id: string
  query: string
  total: number
  results: ContradictionPair[]
}

export interface AnalyzeResponse {
  job_id: string
  status: JobStatus
}

export interface JobSummary {
  id: string
  query: string
  status: JobStatus
  contradiction_count: number
  created_at: string
}

export interface Report {
  id: string
  query: string
  contradiction_count: number
  input_paper?: {
    title: string
    filename: string
    claims_extracted: number
    search_queries_used: string[]
  }
}

export interface Toast {
  id: string
  message: string
  type: 'error' | 'success' | 'info'
}
