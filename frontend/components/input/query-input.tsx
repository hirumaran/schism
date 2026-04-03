'use client'

interface QueryInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
}

export function QueryInput({ value, onChange, onSubmit }: QueryInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSubmit()
    }
  }

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="e.g. vitamin D and depression, omega-3 cardiovascular"
      className="w-full h-[52px] px-4 text-base border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
    />
  )
}
