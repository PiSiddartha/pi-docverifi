# Real-Time Progress Updates - Usage Guide

## Backend API Endpoints

### 1. Stream Progress (Server-Sent Events)
```
GET /api/v1/progress/progress/{document_id}
```

Returns a Server-Sent Events (SSE) stream with real-time progress updates.

**Response Format:**
```
data: {"document_id": "...", "step": "ocr_extraction", "progress": 20, "message": "...", "status": "processing", "timestamp": "..."}

data: {"document_id": "...", "step": "forensic_analysis", "progress": 50, "message": "...", "status": "processing", "timestamp": "..."}
```

### 2. Get Current Progress (One-time)
```
GET /api/v1/progress/progress/{document_id}/current
```

Returns the current progress state for a document.

**Response:**
```json
{
  "document_id": "uuid",
  "step": "ocr_complete",
  "progress": 40,
  "message": "OCR completed. Company: ABC Ltd",
  "status": "processing",
  "timestamp": "2025-11-27T10:30:00Z"
}
```

## Frontend Implementation Example

### React/Next.js Component

```typescript
'use client'

import { useEffect, useState } from 'react'

interface ProgressData {
  document_id: string
  step: string
  progress: number
  message: string
  status: string
  timestamp: string
}

export default function ProgressBar({ documentId }: { documentId: string }) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!documentId) return

    const eventSource = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/progress/progress/${documentId}`
    )

    eventSource.onmessage = (event) => {
      try {
        const data: ProgressData = JSON.parse(event.data)
        setProgress(data)
        
        // Close connection if processing is complete
        if (['passed', 'failed', 'review', 'manual_review'].includes(data.status)) {
          eventSource.close()
        }
      } catch (err) {
        console.error('Error parsing progress data:', err)
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE error:', err)
      setError('Connection error. Please refresh.')
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [documentId])

  if (!progress) {
    return <div>Waiting for progress updates...</div>
  }

  return (
    <div className="w-full">
      <div className="flex justify-between mb-2">
        <span className="text-sm font-medium">{progress.step}</span>
        <span className="text-sm text-gray-600">{progress.progress}%</span>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
          style={{ width: `${progress.progress}%` }}
        />
      </div>
      
      <p className="mt-2 text-sm text-gray-600">{progress.message}</p>
      
      {error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}
      
      {progress.status === 'processing' && (
        <div className="mt-2 flex items-center">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2" />
          <span className="text-sm text-gray-600">Processing...</span>
        </div>
      )}
    </div>
  )
}
```

### Usage in Document Upload Component

```typescript
const [documentId, setDocumentId] = useState<string | null>(null)
const [showProgress, setShowProgress] = useState(false)

const handleUpload = async () => {
  // ... upload logic ...
  
  if (result.document_id) {
    setDocumentId(result.document_id)
    setShowProgress(true)
  }
}

return (
  <div>
    {/* Upload form */}
    
    {showProgress && documentId && (
      <div className="mt-4 p-4 border rounded">
        <h3 className="font-semibold mb-2">Processing Document</h3>
        <ProgressBar documentId={documentId} />
      </div>
    )}
  </div>
)
```

## Progress Steps

The verification process goes through these steps:

1. **initializing** (5%) - Starting document verification process
2. **file_validation** (10%) - File validated successfully
3. **ocr_extraction** (20%) - Extracting text and data from document using OCR
4. **ocr_complete** (40%) - OCR completed
5. **forensic_analysis** (50%) - Analyzing document for tampering
6. **forensic_complete** (60%) - Forensic analysis complete
7. **companies_house_lookup** (70%) - Looking up company information
8. **companies_house_complete** (80%) - Companies House lookup complete
9. **score_calculation** (90%) - Calculating final verification scores
10. **complete** (100%) - Verification complete

## Status Values

- `processing` - Currently being processed
- `passed` - Verification passed
- `failed` - Verification failed
- `review` - Requires manual review
- `manual_review` - In manual review

## Error Handling

If the connection is lost, the frontend should:
1. Attempt to reconnect
2. Fall back to polling the `/current` endpoint
3. Show appropriate error message

Example reconnection logic:

```typescript
const reconnectDelay = 1000 // 1 second
let reconnectTimeout: NodeJS.Timeout

eventSource.onerror = () => {
  eventSource.close()
  
  // Attempt to reconnect
  reconnectTimeout = setTimeout(() => {
    // Re-initialize EventSource
  }, reconnectDelay)
}
```

