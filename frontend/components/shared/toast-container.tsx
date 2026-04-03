'use client'

import { X } from 'lucide-react'
import { useStore } from '@/lib/store'

export function ToastContainer() {
  const { toasts, removeToast } = useStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[9999] space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-3 px-4 py-3 bg-background border border-border rounded-lg shadow-lg max-w-sm ${
            toast.type === 'error'
              ? 'border-l-4 border-l-red-500'
              : toast.type === 'success'
                ? 'border-l-4 border-l-green-500'
                : 'border-l-4 border-l-blue-500'
          }`}
        >
          <span className="text-sm flex-1">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
