'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { Switch } from '@/components/ui/switch'
import { Moon, Sun } from 'lucide-react'

export function ThemeToggle() {
  const { theme, setTheme, systemTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Render a placeholder matching the Switch dimensions so SSR and
    // first client paint are identical — avoids hydration mismatch.
    return (
      <div className="flex items-center gap-2">
        <Sun className="w-4 h-4 text-muted-foreground" />
        <div className="w-[36px] h-[20px]" aria-hidden="true" />
        <Moon className="w-4 h-4 text-muted-foreground" />
      </div>
    )
  }

  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark')

  return (
    <div className="flex items-center gap-2">
      <Sun className="w-4 h-4 text-muted-foreground" />
      <Switch
        checked={isDark}
        onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
        aria-label="Toggle dark mode"
      />
      <Moon className="w-4 h-4 text-muted-foreground" />
    </div>
  )
}