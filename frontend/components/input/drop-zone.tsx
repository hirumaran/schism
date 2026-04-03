'use client'

import { useCallback, useState } from 'react'
import { Upload, FileText, X } from 'lucide-react'
import { useStore } from '@/lib/store'

interface DropZoneProps {
  file: File | null
  onFileChange: (file: File | null) => void
}

export function DropZone({ file, onFileChange }: DropZoneProps) {
  const { addToast } = useStore()
  const [isDragging, setIsDragging] = useState(false)

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const droppedFile = e.dataTransfer.files[0]
      if (droppedFile) {
        const ext = droppedFile.name.split('.').pop()?.toLowerCase()
        if (!['pdf', 'txt', 'md'].includes(ext || '')) {
          addToast('Only PDF and text files supported', 'error')
          return
        }
        onFileChange(droppedFile)
      }
    },
    [onFileChange, addToast]
  )

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0]
      if (selectedFile) {
        const ext = selectedFile.name.split('.').pop()?.toLowerCase()
        if (!['pdf', 'txt', 'md'].includes(ext || '')) {
          addToast('Only PDF and text files supported', 'error')
          return
        }
        onFileChange(selectedFile)
      }
    },
    [onFileChange, addToast]
  )

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  if (file) {
    return (
      <div className="flex items-center justify-between p-4 border border-border rounded-md">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
          </div>
        </div>
        <button
          onClick={() => onFileChange(null)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <X className="w-4 h-4" />
          Remove
        </button>
      </div>
    )
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`relative h-[180px] border-2 border-dashed rounded-md flex flex-col items-center justify-center gap-2 transition-colors ${
        isDragging ? 'border-foreground bg-accent/50' : 'border-border'
      }`}
    >
      <Upload className="w-6 h-6 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Drop a PDF or text file here</p>
      <label className="text-sm text-muted-foreground/80 underline cursor-pointer hover:text-muted-foreground">
        or click to browse
        <input
          type="file"
          accept=".pdf,.txt,.md"
          onChange={handleFileSelect}
          className="sr-only"
        />
      </label>
    </div>
  )
}
