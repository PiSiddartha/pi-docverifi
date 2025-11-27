'use client'

import { useState } from 'react'
import DocumentUpload from '@/components/DocumentUpload'
import DocumentList from '@/components/DocumentList'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Document Verification System
          </h1>
          <p className="text-gray-600">
            Upload and verify documents with OCR, forensic analysis, and Companies House integration
          </p>
        </div>

        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="upload">Upload Document</TabsTrigger>
            <TabsTrigger value="documents">View Documents</TabsTrigger>
          </TabsList>
          
          <TabsContent value="upload" className="mt-6">
            <DocumentUpload />
          </TabsContent>
          
          <TabsContent value="documents" className="mt-6">
            <DocumentList />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  )
}
