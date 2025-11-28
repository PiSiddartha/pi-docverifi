import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface DocumentUploadResponse {
  document_id: string
  status: string
  message: string
}

export interface DocumentData {
  document_id: string
  filename: string
  status: string
  final_score: number | null
  decision: string | null
  created_at: string | null
  processed_at: string | null
  ocr_data: {
    company_name: string | null
    company_number: string | null
    address: string | null
    date: string | null
    confidence: number | null
  }
  companies_house_data: {
    company_name: string | null
    company_number: string | null
    address: string | null
    date: string | null
  }
  forensic_analysis: {
    forensic_score: number | null
    forensic_penalty: number | null
    ela_score: number | null
    jpeg_quality: number | null
    copy_move_detected: boolean | null
    details: any
  }
  scores: {
    ocr_score: number
    registry_score: number
    provided_score: number
    final_score: number
  }
  flags: string[] | null
}

export interface DocumentListItem {
  document_id: string
  filename: string
  status: string
  final_score: number | null
  decision: string | null
  created_at: string | null
}

export const uploadDocument = async (
  file: File,
  documentType: string = 'companies_house',
  companyName?: string,
  companyNumber?: string,
  address?: string,
  date?: string
): Promise<DocumentUploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('document_type', documentType)
  if (companyName) formData.append('company_name', companyName)
  if (companyNumber) formData.append('company_number', companyNumber)
  if (address) formData.append('address', address)
  if (date) formData.append('date', date)

  const response = await api.post<DocumentUploadResponse>('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const getDocument = async (documentId: string): Promise<DocumentData> => {
  const response = await api.get<DocumentData>(`/documents/${documentId}`)
  return response.data
}

export const listDocuments = async (
  skip: number = 0,
  limit: number = 100,
  status?: string
): Promise<{ total: number; documents: DocumentListItem[] }> => {
  const params: any = { skip, limit }
  if (status) params.status = status
  const response = await api.get<{ total: number; documents: DocumentListItem[] }>('/documents/', { params })
  return response.data
}

export const processVerification = async (documentId: string): Promise<{ document_id: string; status: string; message: string }> => {
  const response = await api.post(`/verification/process/${documentId}`)
  return response.data
}

export const manualReview = async (
  documentId: string,
  action: 'APPROVE' | 'REJECT' | 'ESCALATE',
  reviewerNotes?: string,
  reviewerId?: string
): Promise<{ document_id: string; action: string; status: string; message: string }> => {
  const response = await api.post(`/verification/review/${documentId}`, null, {
    params: { action, reviewer_notes: reviewerNotes, reviewer_id: reviewerId },
  })
  return response.data
}

export interface ProgressData {
  document_id: string
  step: string
  progress: number
  message: string
  status: string
  timestamp: string
}

export const getCurrentProgress = async (documentId: string): Promise<ProgressData> => {
  const response = await api.get<ProgressData>(`/progress/progress/${documentId}/current`)
  return response.data
}
