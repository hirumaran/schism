'use client'

import { useState } from 'react'
import { X, Search, FileText, ChevronDown, ChevronRight } from 'lucide-react'
import { useStore } from '@/lib/store'

type Tab = 'overview' | 'api' | 'setup'

export function DocsDrawer() {
  const { docsOpen, setDocsOpen } = useStore()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [expandedRoutes, setExpandedRoutes] = useState<string[]>([])

  if (!docsOpen) return null

  const toggleRoute = (route: string) => {
    setExpandedRoutes((prev) =>
      prev.includes(route) ? prev.filter((r) => r !== route) : [...prev, route]
    )
  }

  return (
    <div className="fixed top-0 right-0 bottom-0 w-[480px] bg-background border-l border-border z-50 flex flex-col">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <h2 className="font-serif text-xl">Documentation</h2>
        <button
          onClick={() => setDocsOpen(false)}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex border-b border-border">
        {(['overview', 'api', 'setup'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-3 text-sm capitalize ${
              activeTab === tab
                ? 'border-b-2 border-foreground font-medium'
                : 'text-muted-foreground'
            }`}
          >
            {tab === 'api' ? 'API reference' : tab}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'api' && (
          <ApiTab expandedRoutes={expandedRoutes} toggleRoute={toggleRoute} />
        )}
        {activeTab === 'setup' && <SetupTab />}
      </div>
    </div>
  )
}

function OverviewTab() {
  return (
    <div className="space-y-8">
      <section>
        <h3 className="font-serif text-lg mb-3">What Schism does</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Schism finds research papers that contradict each other. It searches multiple academic databases, extracts the main claim from each paper, and surfaces pairs with opposing conclusions.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 border border-border rounded-lg">
            <Search className="w-5 h-5 mb-2 text-muted-foreground" />
            <h4 className="text-sm font-medium mb-1">Search by topic</h4>
            <p className="text-xs text-muted-foreground">
              Enter a research topic. Schism searches arXiv, Semantic Scholar, PubMed, and OpenAlex, extracts the main claim from each paper, clusters them by subtopic, and surfaces pairs with contradictory conclusions.
            </p>
          </div>
          <div className="p-4 border border-border rounded-lg">
            <FileText className="w-5 h-5 mb-2 text-muted-foreground" />
            <h4 className="text-sm font-medium mb-1">Upload your paper</h4>
            <p className="text-xs text-muted-foreground">
              Paste your abstract or upload a PDF. Schism extracts your specific claims and searches for published papers that directly contradict each one. Useful before submission.
            </p>
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Contradiction types</h3>
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <span className="w-2 h-2 rounded-full bg-red-500 mt-1.5" />
            <div>
              <span className="text-sm font-medium">Direct</span>
              <p className="text-xs text-muted-foreground">
                Same population, same outcome, opposite result. The strongest form of contradiction.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="w-2 h-2 rounded-full bg-amber-500 mt-1.5" />
            <div>
              <span className="text-sm font-medium">Conditional</span>
              <p className="text-xs text-muted-foreground">
                Same outcome, opposite result, but in different conditions, doses, or subgroups. Both may be true simultaneously.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="w-2 h-2 rounded-full bg-gray-400 mt-1.5" />
            <div>
              <span className="text-sm font-medium">Methodological</span>
              <p className="text-xs text-muted-foreground">
                Different methodology leads to different conclusions. May reflect measurement or design differences rather than a true contradiction.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Paper sources</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="font-medium">arXiv</span>
            <span className="text-muted-foreground">preprints, CS/physics/math/bio</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium">Semantic Scholar</span>
            <span className="text-muted-foreground">200M+ papers across all fields</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium">PubMed</span>
            <span className="text-muted-foreground">biomedical literature, NIH indexed</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium">OpenAlex</span>
            <span className="text-muted-foreground">broad coverage, open access focus</span>
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Scoring</h3>
        <p className="text-sm text-muted-foreground">
          Contradiction scores run from 0 (fully consistent) to 1 (directly contradictory). Schism only surfaces pairs scoring above 0.6. A score penalty of 0.15 is applied when papers are more than 15 years apart - older contradictions are less actionable than recent ones.
        </p>
      </section>
    </div>
  )
}

function ApiTab({
  expandedRoutes,
  toggleRoute,
}: {
  expandedRoutes: string[]
  toggleRoute: (route: string) => void
}) {
  const routes = [
    {
      method: 'POST',
      path: '/api/analyze',
      desc: 'Search by topic query',
      request: `{
  "query": "vitamin D depression",
  "max_results": 50,
  "sources": ["arxiv", "semantic_scholar"]
}`,
      response: `{ "job_id": "abc123", "status": "pending" }`,
    },
    {
      method: 'POST',
      path: '/api/analyze/paper',
      desc: 'Upload paper or paste text',
      request: `// Multipart form (file upload):
file: <PDF or .txt file>
max_results: 40
sources: arxiv,semantic_scholar

// OR JSON body (text):
{
  "text": "your abstract or full paper text",
  "title": "optional title",
  "max_results": 40,
  "sources": ["arxiv", "semantic_scholar"]  
}`,
      response: `{ "job_id": "abc123", "status": "pending" }`,
    },
    {
      method: 'GET',
      path: '/api/jobs/{id}',
      desc: 'Check job status',
      response: `{
  "id": "abc123",
  "status": "analyzing",
  "progress": 65,
  "paper_count": 42,
  ...
}`,
    },
    {
      method: 'GET',
      path: '/api/jobs/{id}/results',
      desc: 'Get contradiction pairs',
      response: `{
  "job_id": "abc123",
  "query": "vitamin D depression",
  "total": 12,
  "results": [...]
}`,
    },
    {
      method: 'DELETE',
      path: '/api/jobs/{id}',
      desc: 'Cancel or delete job',
      response: '204 No Content',
    },
    {
      method: 'GET',
      path: '/api/reports/{id}/export',
      desc: 'Download full report (format=json|csv)',
      response: 'File download',
    },
    {
      method: 'GET',
      path: '/api/health',
      desc: 'Check backend status',
      response: `{ "status": "ok", "app": "schism", ... }`,
    },
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        The frontend reads its API base from NEXT_PUBLIC_API_URL. In local development this is usually proxied to the backend.
      </p>
      <div className="p-3 bg-foreground/5 rounded-md font-mono text-xs">
        <p className="text-muted-foreground mb-1">Headers required for all /analyze endpoints:</p>
        <pre className="text-foreground">
{`X-Provider: anthropic | openai | ollama | mock
X-Api-Key:  your-api-key (omit for ollama/mock)
X-Model:    model-name (optional, uses default)`}
        </pre>
      </div>

      <div className="space-y-2">
        {routes.map((route) => (
          <div key={route.path} className="border border-border rounded-md">
            <button
              onClick={() => toggleRoute(route.path)}
              className="w-full flex items-center justify-between p-3 text-left hover:bg-accent/50"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-mono px-2 py-0.5 rounded ${
                    route.method === 'GET'
                      ? 'bg-green-100 text-green-700'
                      : route.method === 'POST'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-red-100 text-red-700'
                  }`}
                >
                  {route.method}
                </span>
                <span className="text-sm font-mono">{route.path}</span>
              </div>
              {expandedRoutes.includes(route.path) ? (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              )}
            </button>
            {expandedRoutes.includes(route.path) && (
              <div className="px-3 pb-3 space-y-2">
                <p className="text-sm text-muted-foreground">{route.desc}</p>
                {route.request && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Request:</p>
                    <pre className="p-2 bg-foreground/5 rounded text-xs font-mono overflow-x-auto">
                      {route.request}
                    </pre>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Response:</p>
                  <pre className="p-2 bg-foreground/5 rounded text-xs font-mono overflow-x-auto">
                    {route.response}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function SetupTab() {
  const [expandedTrouble, setExpandedTrouble] = useState<string[]>([])

  const toggleTrouble = (key: string) => {
    setExpandedTrouble((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  }

  const troubleshooting = [
    {
      key: '502',
      q: 'Backend returns 502 on LLM calls',
      a: 'Your API key is likely invalid or rate-limited. Check the Settings panel and validate your key.',
    },
    {
      key: 'no-results',
      q: 'No contradictions found',
      a: 'Try a more specific query, increase max_results, or add more sources. The contradiction threshold is 0.6 - pairs below this score are filtered out.',
    },
    {
      key: 'ollama',
      q: 'Ollama not connecting',
      a: 'Make sure ollama serve is running. Check that the base URL in Settings matches (default: localhost:11434). The model must be pulled first: ollama pull llama3.1',
    },
    {
      key: 'pdf',
      q: 'PDF extraction failed',
      a: 'Some PDFs are scanned images without selectable text. Copy-paste the abstract manually into the text input.',
    },
  ]

  return (
    <div className="space-y-6">
      <section>
        <h3 className="font-serif text-lg mb-3">Quick start</h3>
        <pre className="p-3 bg-foreground/5 rounded-md text-xs font-mono overflow-x-auto">
{`git clone https://github.com/your-org/schism
cd schism
cp apps/api/.env.example apps/api/.env
cp frontend/.env.example frontend/.env.local
docker compose up`}
        </pre>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Without Docker</h3>
        <pre className="p-3 bg-foreground/5 rounded-md text-xs font-mono overflow-x-auto">
{`cd apps/api
pip install -r requirements.txt
python -m app.main

cd ../../frontend
npm install
npm run dev`}
        </pre>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Environment variables</h3>
        <div className="text-xs space-y-1">
          <div className="grid grid-cols-3 gap-2 font-medium border-b border-border pb-1">
            <span>Variable</span>
            <span>Default</span>
            <span>Description</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-muted-foreground">
            <span className="font-mono">SCHISM_DATABASE_URL</span>
            <span>sqlite://...</span>
            <span>SQLite DB path</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-muted-foreground">
            <span className="font-mono">SCHISM_ENABLE_QDRANT</span>
            <span>false</span>
            <span>Enable vector store</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-muted-foreground">
            <span className="font-mono">SCHISM_QDRANT_URL</span>
            <span>localhost:6333</span>
            <span>Qdrant connection</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-muted-foreground">
            <span className="font-mono">SCHISM_CONTRADICTION_THRESHOLD</span>
            <span>0.6</span>
            <span>Min score to surface</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-muted-foreground">
            <span className="font-mono">SCHISM_JOB_TIMEOUT_MINUTES</span>
            <span>15</span>
            <span>Max job duration</span>
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">With Qdrant (recommended)</h3>
        <pre className="p-3 bg-foreground/5 rounded-md text-xs font-mono overflow-x-auto">
{`SCHISM_ENABLE_QDRANT=true
docker compose --profile qdrant up`}
        </pre>
        <p className="text-xs text-muted-foreground mt-2">
          Qdrant caches paper embeddings so repeated queries on similar topics skip the embedding step entirely.
        </p>
      </section>

      <section>
        <h3 className="font-serif text-lg mb-3">Troubleshooting</h3>
        <div className="space-y-2">
          {troubleshooting.map((item) => (
            <div key={item.key} className="border border-border rounded-md">
              <button
                onClick={() => toggleTrouble(item.key)}
                className="w-full flex items-center justify-between p-3 text-left hover:bg-accent/50"
              >
                <span className="text-sm">{item.q}</span>
                {expandedTrouble.includes(item.key) ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </button>
              {expandedTrouble.includes(item.key) && (
                <div className="px-3 pb-3">
                  <p className="text-sm text-muted-foreground">{item.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
