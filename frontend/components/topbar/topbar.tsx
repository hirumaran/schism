'use client'

import Link from 'next/link'
import { useStore } from '@/lib/store'
import { ThemeToggle } from './theme-toggle'

export function Topbar() {
  const { setSettingsOpen, setDocsOpen } = useStore()

  const getStatusDot = () => {
    return 'bg-green-500'
  }

  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-background border-b border-border z-50">
      <div className="flex items-center justify-between h-full px-6">
<Link href="/" className="flex items-baseline gap-2">
           <span className="font-serif text-xl font-thin">Schism</span>
         </Link>

        <div className="flex items-center gap-4">
          {/* Theme Toggle */}
          <ThemeToggle />

          <button
            onClick={() => setDocsOpen(true)}
            className="text-sm text-foreground hover:text-foreground/80 transition-colors"
          >
            Docs
          </button>

          <button
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2 text-sm text-foreground hover:text-foreground/80 transition-colors"
          >
            Settings
            <span
              className={`w-2 h-2 rounded-full ${getStatusDot()}`}
            />
          </button>
        </div>
      </div>
    </header>
  )
}
