export type Provider = 'anthropic' | 'openai' | 'ollama' | 'mock'

export type EmbeddingProvider = 'local' | 'openai' | 'cohere'

export type OllamaMode = 'local' | 'cloud'

export type JobStatus =
  | 'pending'
  | 'running'
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
   ollamaMode: OllamaMode
   ollamaLocalBaseUrl: string
   ollamaLocalModel: string
   ollamaCloudApiKey: string
   ollamaCloudModel: string
  cohereKey: string
}

export interface Paper {
  id: string
  title: string
  abstract: string | null
  authors: string[]
  year: number | null
  source: string
  url: string | null
  citation_count: number | null
  influential_citation_count?: number | null
  magnitude: string | null
  population: string | null
  outcome: string | null
  relevance_score?: number | null
}

export interface ContradictionPair {
  pair_key: string
  paper_a_id: string
  paper_b_id: string
  paper_a: Paper
  paper_b: Paper
  paper_a_claim: string | null
  paper_b_claim: string | null
  score: number
  raw_score: number
  score_penalty: number
  type: ContradictionType | null
  explanation: string
  is_contradiction: boolean
  could_both_be_true: boolean
  key_difference: string | null
  mode: AnalysisMode
  cluster_id: string | null
}

export interface AnalysisJob {
  id: string
  query: string
  provider?: string
  model?: string | null
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
  metadata?: Record<string, unknown>
  warnings?: string[]
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

export interface AnalyzeAcceptedResponse {
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
  job_id?: string | null
  query: string | null
  mode: AnalysisMode
  status: JobStatus
  contradiction_threshold: number
  has_contradictions: boolean
  created_at: string
  completed_at: string | null
  input_paper?: {
    title: string | null
    filename: string | null
    claims_extracted: number
    search_queries_used: string[]
  }
}

export interface HealthResponse {
  status: string
  app: string
  embedding_backend: string
  vector_store: Record<string, unknown>
  supported_sources: string[]
  supported_providers: Provider[]
}

export interface SearchResponse {
  search_run_id: string
  query: string
  total: number
  sources_searched: string[]
  papers: Paper[]
  dedup_removed: number
  filter_removed: number
  warnings: string[]
}

export interface Toast {
  id: string
  message: string
  type: 'error' | 'success' | 'info'
}
