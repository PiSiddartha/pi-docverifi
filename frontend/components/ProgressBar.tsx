'use client'

import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react'

interface ProgressData {
  document_id: string
  step: string
  progress: number
  message: string
  status: string
  timestamp: string
}

interface ProgressBarProps {
  documentId: string
  onComplete?: (status: string) => void
}

export default function ProgressBar({ documentId, onComplete }: ProgressBarProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!documentId) return

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const eventSource = new EventSource(
      `${API_URL}/api/v1/progress/progress/${documentId}`
    )

    eventSource.onopen = () => {
      setConnected(true)
      setError(null)
    }

    eventSource.onmessage = (event) => {
      try {
        const data: ProgressData = JSON.parse(event.data)
        setProgress(data)
        
        // Call onComplete callback when processing is finished
        if (['passed', 'failed', 'review', 'manual_review'].includes(data.status)) {
          eventSource.close()
          if (onComplete) {
            onComplete(data.status)
          }
        }
      } catch (err) {
        console.error('Error parsing progress data:', err)
        setError('Failed to parse progress update')
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE error:', err)
      setError('Connection error. Trying to reconnect...')
      setConnected(false)
      // EventSource will automatically try to reconnect
    }

    return () => {
      eventSource.close()
    }
  }, [documentId, onComplete])

  if (!progress && !error) {
    return (
      <div className="w-full p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-2">
          <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
          <span className="text-sm text-gray-600">Connecting to progress stream...</span>
        </div>
      </div>
    )
  }

  if (error && !progress) {
    return (
      <div className="w-full p-4 bg-red-50 rounded-lg">
        <div className="flex items-center space-x-2">
          <XCircle className="w-5 h-5 text-red-500" />
          <span className="text-sm text-red-600">{error}</span>
        </div>
      </div>
    )
  }

  if (!progress) return null

  const getStepLabel = (step: string) => {
    const stepLabels: Record<string, string> = {
      initializing: 'Initializing',
      file_validation: 'Validating File',
      ocr_extraction: 'OCR Extraction',
      ocr_complete: 'OCR Complete',
      forensic_analysis: 'Forensic Analysis',
      forensic_complete: 'Forensic Complete',
      companies_house_lookup: 'Companies House Lookup',
      companies_house_complete: 'Companies House Complete',
      companies_house_skipped: 'Companies House Skipped',
      score_calculation: 'Calculating Scores',
      complete: 'Complete',
      error: 'Error'
    }
    return stepLabels[step] || step.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  const getStatusIcon = () => {
    if (progress.status === 'processing') {
      return <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
    }
    if (progress.status === 'passed') {
      return <CheckCircle className="w-5 h-5 text-green-500" />
    }
    if (progress.status === 'failed') {
      return <XCircle className="w-5 h-5 text-red-500" />
    }
    if (['review', 'manual_review'].includes(progress.status)) {
      return <Clock className="w-5 h-5 text-yellow-500" />
    }
    return null
  }

  const getStatusColor = () => {
    if (progress.status === 'passed') return 'bg-green-500'
    if (progress.status === 'failed') return 'bg-red-500'
    if (['review', 'manual_review'].includes(progress.status)) return 'bg-yellow-500'
    return 'bg-primary-500'
  }

  return (
    <div className="w-full p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <h3 className="text-sm font-semibold text-gray-900">
            {getStepLabel(progress.step)}
          </h3>
        </div>
        <div className="flex items-center space-x-2">
          {connected && (
            <span className="text-xs text-green-600 flex items-center">
              <span className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></span>
              Connected
            </span>
          )}
          <span className="text-sm font-medium text-gray-700">{progress.progress}%</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${getStatusColor()}`}
          style={{ width: `${progress.progress}%` }}
        />
      </div>

      {/* Message */}
      <p className="text-sm text-gray-600 mt-2">{progress.message}</p>

      {/* Error Message */}
      {error && (
        <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600">
          {error}
        </div>
      )}

      {/* Status Badge */}
      {progress.status !== 'processing' && (
        <div className="mt-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          Status: {progress.status}
        </div>
      )}
    </div>
  )
}

