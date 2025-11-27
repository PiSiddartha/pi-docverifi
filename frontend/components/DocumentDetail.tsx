'use client'

import { useState } from 'react'
import { ArrowLeft, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'
import { DocumentData } from '@/lib/api'

interface DocumentDetailProps {
  document: DocumentData
  onBack: () => void
  onProcess: (documentId: string) => void
  onReview: (action: 'APPROVE' | 'REJECT' | 'ESCALATE', notes?: string) => Promise<void>
}

export default function DocumentDetail({ document, onBack, onProcess, onReview }: DocumentDetailProps) {
  const [reviewNotes, setReviewNotes] = useState('')
  const [reviewing, setReviewing] = useState(false)

  const handleReview = async (action: 'APPROVE' | 'REJECT' | 'ESCALATE') => {
    setReviewing(true)
    try {
      await onReview(action, reviewNotes)
      setReviewNotes('')
    } catch (error) {
      console.error('Error submitting review:', error)
    } finally {
      setReviewing(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 75) return 'text-green-600'
    if (score >= 50) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <button
          onClick={onBack}
          className="mb-4 flex items-center space-x-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to List</span>
        </button>

        <div className="mb-6">
          <h2 className="text-2xl font-semibold mb-2">{document.filename}</h2>
          <div className="flex items-center space-x-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              document.status === 'passed' ? 'bg-green-100 text-green-800' :
              document.status === 'failed' ? 'bg-red-100 text-red-800' :
              document.status === 'review' ? 'bg-yellow-100 text-yellow-800' :
              'bg-gray-100 text-gray-800'
            }`}>
              {document.status}
            </span>
            {document.decision && (
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                document.decision === 'PASS' ? 'bg-green-100 text-green-800' :
                document.decision === 'FAIL' ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {document.decision}
              </span>
            )}
            {document.final_score !== null && (
              <span className={`text-2xl font-bold ${getScoreColor(document.final_score)}`}>
                {document.final_score.toFixed(1)}/100
              </span>
            )}
          </div>
        </div>

        {/* Scores Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">OCR Score</p>
            <p className="text-2xl font-bold text-blue-600">
              {document.scores.ocr_score.toFixed(1)}/30
            </p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Registry Score</p>
            <p className="text-2xl font-bold text-green-600">
              {document.scores.registry_score.toFixed(1)}/40
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Provided Score</p>
            <p className="text-2xl font-bold text-purple-600">
              {document.scores.provided_score.toFixed(1)}/30
            </p>
          </div>
          <div className="bg-red-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Forensic Penalty</p>
            <p className="text-2xl font-bold text-red-600">
              -{document.forensic_analysis.forensic_penalty?.toFixed(1) || 0}/15
            </p>
          </div>
        </div>

        {/* OCR Data */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3 text-gray-900">OCR Extracted Data</h3>
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Company Name</p>
                <p className="font-medium text-gray-900">{document.ocr_data.company_name || <span className="text-gray-500">-</span>}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Company Number</p>
                <p className="font-medium text-gray-900">{document.ocr_data.company_number || <span className="text-gray-500">-</span>}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Address</p>
                <p className="font-medium text-gray-900">{document.ocr_data.address || <span className="text-gray-500">-</span>}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Confidence</p>
                <p className="font-medium text-gray-900">
                  {document.ocr_data.confidence ? `${document.ocr_data.confidence.toFixed(1)}%` : <span className="text-gray-500">-</span>}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Companies House Data */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3 text-gray-900">Companies House Data</h3>
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Company Name</p>
                <p className="font-medium text-gray-900">{document.companies_house_data.company_name || <span className="text-gray-500">-</span>}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Company Number</p>
                <p className="font-medium text-gray-900">{document.companies_house_data.company_number || <span className="text-gray-500">-</span>}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Address</p>
                <p className="font-medium text-gray-900">{document.companies_house_data.address || <span className="text-gray-500">-</span>}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Forensic Analysis */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3 text-gray-900">Forensic Analysis</h3>
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Forensic Score</p>
                <p className="font-medium text-gray-900">
                  {document.forensic_analysis.forensic_score !== null && document.forensic_analysis.forensic_score !== undefined 
                    ? document.forensic_analysis.forensic_score.toFixed(1) 
                    : <span className="text-gray-500">-</span>}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">ELA Score</p>
                <p className="font-medium text-gray-900">
                  {document.forensic_analysis.ela_score !== null && document.forensic_analysis.ela_score !== undefined 
                    ? document.forensic_analysis.ela_score.toFixed(1) 
                    : <span className="text-gray-500">-</span>}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">JPEG Quality</p>
                <p className="font-medium text-gray-900">
                  {document.forensic_analysis.jpeg_quality !== null && document.forensic_analysis.jpeg_quality !== undefined 
                    ? document.forensic_analysis.jpeg_quality.toFixed(1) 
                    : <span className="text-gray-500">-</span>}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Copy-Move Detected</p>
                <p className="font-medium text-gray-900">{document.forensic_analysis.copy_move_detected ? 'Yes' : 'No'}</p>
              </div>
            </div>
            {document.forensic_analysis.details && document.forensic_analysis.details.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-gray-600 mb-2">Details:</p>
                <ul className="list-disc list-inside text-sm text-gray-900">
                  {document.forensic_analysis.details.map((detail: string, idx: number) => (
                    <li key={idx} className="text-gray-900">{detail}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="border-t pt-6">
          {document.status === 'pending' && (
            <button
              onClick={() => onProcess(document.document_id)}
              className="bg-primary-600 text-white px-6 py-2 rounded-lg hover:bg-primary-700"
            >
              Start Processing
            </button>
          )}

          {document.status === 'review' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Manual Review</h3>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Enter review notes..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                rows={4}
              />
              <div className="flex space-x-4">
                <button
                  onClick={() => handleReview('APPROVE')}
                  disabled={reviewing}
                  className="flex-1 bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:bg-gray-400 flex items-center justify-center space-x-2"
                >
                  <CheckCircle className="w-5 h-5" />
                  <span>Approve</span>
                </button>
                <button
                  onClick={() => handleReview('REJECT')}
                  disabled={reviewing}
                  className="flex-1 bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 disabled:bg-gray-400 flex items-center justify-center space-x-2"
                >
                  <XCircle className="w-5 h-5" />
                  <span>Reject</span>
                </button>
                <button
                  onClick={() => handleReview('ESCALATE')}
                  disabled={reviewing}
                  className="flex-1 bg-yellow-600 text-white px-6 py-2 rounded-lg hover:bg-yellow-700 disabled:bg-gray-400 flex items-center justify-center space-x-2"
                >
                  <AlertTriangle className="w-5 h-5" />
                  <span>Escalate</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

