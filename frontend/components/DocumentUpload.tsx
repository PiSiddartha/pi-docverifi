'use client'

import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react'
import { uploadDocument } from '@/lib/api'
import ProgressBar from './ProgressBar'

export default function DocumentUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [companyName, setCompanyName] = useState('')
  const [companyNumber, setCompanyNumber] = useState('')
  const [address, setAddress] = useState('')
  const [date, setDate] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string; documentId?: string } | null>(null)
  const [processing, setProcessing] = useState(false)
  const [currentDocumentId, setCurrentDocumentId] = useState<string | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg']
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0])
        setUploadResult(null)
      }
    }
  })

  const handleUpload = async () => {
    if (!file) {
      setUploadResult({ success: false, message: 'Please select a file' })
      return
    }

    setUploading(true)
    setUploadResult(null)

    try {
      const result = await uploadDocument(
        file,
        companyName || undefined,
        companyNumber || undefined,
        address || undefined,
        date || undefined
      )

      setUploadResult({
        success: true,
        message: result.message,
        documentId: result.document_id
      })

      // Set document ID for progress tracking (processing starts automatically on upload)
      if (result.document_id) {
        setCurrentDocumentId(result.document_id)
        setProcessing(true)
      }

      // Don't reset form yet - wait for processing to complete
    } catch (error: any) {
      setUploadResult({
        success: false,
        message: error.response?.data?.detail || 'Upload failed. Please try again.'
      })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-semibold mb-6">Upload Document</h2>

        {/* File Dropzone */}
        <div className="mb-6">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-300 hover:border-primary-400'
            }`}
          >
            <input {...getInputProps()} />
            {file ? (
              <div className="flex items-center justify-center space-x-2">
                <File className="w-8 h-8 text-primary-500" />
                <span className="text-gray-700">{file.name}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setFile(null)
                  }}
                  className="ml-2 text-red-500 hover:text-red-700"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div>
                <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-600">
                  {isDragActive
                    ? 'Drop the file here'
                    : 'Drag & drop a file here, or click to select'}
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  PDF, PNG, JPG (max 10MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Optional Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Company Name (Optional)
            </label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Enter company name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Company Number (Optional)
            </label>
            <input
              type="text"
              value={companyNumber}
              onChange={(e) => setCompanyNumber(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Enter company number"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Address (Optional)
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Enter address"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Date (Optional)
            </label>
            <input
              type="text"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="YYYY-MM-DD"
            />
          </div>
        </div>

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={!file || uploading || processing}
          className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2"
        >
          {uploading || processing ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              <span>{uploading ? 'Uploading...' : 'Processing...'}</span>
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              <span>Upload & Verify Document</span>
            </>
          )}
        </button>

        {/* Result Message */}
        {uploadResult && !processing && (
          <div
            className={`mt-4 p-4 rounded-lg flex items-center space-x-2 ${
              uploadResult.success
                ? 'bg-green-50 text-green-800'
                : 'bg-red-50 text-red-800'
            }`}
          >
            {uploadResult.success ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <AlertCircle className="w-5 h-5" />
            )}
            <span>{uploadResult.message}</span>
          </div>
        )}

        {/* Progress Bar */}
        {processing && currentDocumentId && (
          <div className="mt-6">
            <ProgressBar 
              documentId={currentDocumentId}
              onComplete={(status) => {
                setProcessing(false)
                // Reset form after processing completes
                setFile(null)
                setCompanyName('')
                setCompanyNumber('')
                setAddress('')
                setDate('')
                setCurrentDocumentId(null)
                
                // Update result message based on final status
                if (status === 'passed') {
                  setUploadResult({
                    success: true,
                    message: 'Document verification completed successfully!',
                    documentId: currentDocumentId
                  })
                } else if (status === 'failed') {
                  // "failed" can mean either low score (normal) or processing error
                  // The progress message should contain details about the score
                  setUploadResult({
                    success: false,
                    message: 'Document verification did not pass. Check document details for score breakdown.',
                    documentId: currentDocumentId
                  })
                } else if (['review', 'manual_review'].includes(status)) {
                  setUploadResult({
                    success: true,
                    message: 'Document requires manual review.',
                    documentId: currentDocumentId
                  })
                }
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
