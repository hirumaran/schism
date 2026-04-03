'use client'

interface PasteAreaProps {
  value: string
  onChange: (value: string) => void
}

const MAX_CHARS = 10000

export function PasteArea({ value, onChange }: PasteAreaProps) {
  return (
    <div className="relative">
      <textarea
        value={value}
        onChange={(e) => {
          if (e.target.value.length <= MAX_CHARS) {
            onChange(e.target.value)
          }
        }}
        placeholder="Or paste your abstract or paper text here..."
        className="w-full h-[140px] px-4 py-3 text-sm border border-border rounded-md bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <span className="absolute bottom-2 right-3 text-xs text-muted-foreground">
        {value.length} / {MAX_CHARS}
      </span>
    </div>
  )
}
