'use client'

import { useState, useEffect } from 'react'
import { File, CheckCircle, XCircle, Clock, Eye } from 'lucide-react'
import { listDocuments, getDocument, processVerification, manualReview, DocumentData } from '@/lib/api'
import DocumentDetail from './DocumentDetail'

export default function DocumentList() {
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDocument, setSelectedDocument] = useState<DocumentData | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('')

  useEffect(() => {
    loadDocuments()
  }, [statusFilter])

  const loadDocuments = async () => {
    setLoading(true)
    try {
      const result = await listDocuments(0, 100, statusFilter || undefined)
      setDocuments(result.documents)
    } catch (error) {
      console.error('Error loading documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleViewDocument = async (documentId: string) => {
    try {
      const doc = await getDocument(documentId)
      setSelectedDocument(doc)
    } catch (error) {
      console.error('Error loading document details:', error)
    }
  }

  const handleProcess = async (documentId: string) => {
    try {
      await processVerification(documentId)
      await loadDocuments()
      if (selectedDocument?.document_id === documentId) {
        const doc = await getDocument(documentId)
        setSelectedDocument(doc)
      }
    } catch (error) {
      console.error('Error processing document:', error)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'review':
      case 'manual_review':
        return <Clock className="w-5 h-5 text-yellow-500" />
      default:
        return <Clock className="w-5 h-5 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      case 'review':
      case 'manual_review':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  if (selectedDocument) {
    return (
      <DocumentDetail
        document={selectedDocument}
        onBack={() => setSelectedDocument(null)}
        onProcess={handleProcess}
        onReview={async (action, notes) => {
          await manualReview(selectedDocument.document_id, action, notes)
          await loadDocuments()
          const doc = await getDocument(selectedDocument.document_id)
          setSelectedDocument(doc)
        }}
      />
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-semibold">Documents</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="passed">Passed</option>
            <option value="failed">Failed</option>
            <option value="review">Review</option>
          </select>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <File className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <p>No documents found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Filename</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Score</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Decision</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Created</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <File className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-900">{doc.filename}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(doc.status)}
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(doc.status)}`}>
                          {doc.status}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {doc.final_score !== null ? (
                        <span className="text-sm font-semibold">{doc.final_score.toFixed(1)}/100</span>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {doc.decision ? (
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          doc.decision === 'PASS' ? 'bg-green-100 text-green-800' :
                          doc.decision === 'FAIL' ? 'bg-red-100 text-red-800' :
                          'bg-yellow-100 text-yellow-800'
                        }`}>
                          {doc.decision}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => handleViewDocument(doc.document_id)}
                        className="text-primary-600 hover:text-primary-700 flex items-center space-x-1"
                      >
                        <Eye className="w-4 h-4" />
                        <span className="text-sm">View</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
