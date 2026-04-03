'use client'

type Mode = 'query' | 'paper'

interface ModeToggleProps {
  mode: Mode
  onModeChange: (mode: Mode) => void
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="flex justify-center gap-2 mt-10">
      <button
        onClick={() => onModeChange('query')}
        className={`px-4 py-2 text-sm rounded-full transition-colors ${
          mode === 'query'
            ? 'bg-foreground text-background'
            : 'bg-background text-muted-foreground border border-border hover:border-foreground/30'
        }`}
      >
        Search by topic
      </button>
      <button
        onClick={() => onModeChange('paper')}
        className={`px-4 py-2 text-sm rounded-full transition-colors ${
          mode === 'paper'
            ? 'bg-foreground text-background'
            : 'bg-background text-muted-foreground border border-border hover:border-foreground/30'
        }`}
      >
        Upload a paper
      </button>
    </div>
  )
}
