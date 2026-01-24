'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Upload, File, Trash2, CheckCircle, Clock } from 'lucide-react';
import { api, FileInfo } from '@/lib/api';

interface FileSidebarProps {
  onFileSelect: (docId: string, filename: string) => void;
  selectedDocId: string | null;
}

export default function FileSidebar({ onFileSelect, selectedDocId }: FileSidebarProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadFiles = useCallback(async () => {
    try {
      setLoading(true);
      const fileList = await api.listFiles();
      setFiles(fileList);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileUpload(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith('.pdf')) {
      alert('Only PDF files are supported');
      return;
    }

    setUploading(true);
    try {
      await api.uploadFile(file);
      await loadFiles();
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleFileUpload(e.target.files[0]);
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
      await api.deleteFile(docId);
      await loadFiles();
      // no-op for selection reset; parent handles it on deletion
    } catch (error) {
      console.error('Delete failed:', error);
      alert('Delete failed. Please try again.');
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="h-full flex flex-col bg-gray-50 border-r border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Documents</h2>
        
        {/* Upload Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`
            relative border-2 border-dashed rounded-lg p-4 text-center cursor-pointer
            transition-colors
            ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          `}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileInputChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={uploading}
          />
          <Upload className={`mx-auto h-8 w-8 mb-2 ${uploading ? 'text-gray-400' : 'text-gray-500'}`} />
          <p className="text-sm text-gray-600">
            {uploading ? 'Uploading...' : 'Drop PDF or click to upload'}
          </p>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No documents yet. Upload a PDF to get started.
          </div>
        ) : (
          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.doc_id}
                className={`
                  group p-3 rounded-lg border cursor-pointer transition-all
                  ${selectedDocId === file.doc_id 
                    ? 'bg-blue-50 border-blue-300' 
                    : 'bg-white border-gray-200 hover:border-gray-300'
                  }
                `}
                onClick={() => onFileSelect(file.doc_id, file.filename)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <File className="h-4 w-4 text-gray-500 flex-shrink-0" />
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {file.filename}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {file.status === 'indexed' ? (
                        <CheckCircle className="h-3 w-3 text-green-500" />
                      ) : (
                        <Clock className="h-3 w-3 text-yellow-500" />
                      )}
                      <span className="text-xs text-gray-500 capitalize">
                        {file.status}
                      </span>
                      <span className="text-xs text-gray-400">
                        • {formatFileSize(file.size_bytes)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(file.doc_id, file.filename);
                      }}
                      className="p-1 hover:bg-red-50 rounded"
                      title="Delete"
                    >
                      <Trash2 className="h-3 w-3 text-red-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
