'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Upload, File, Trash2, CheckCircle, Clock } from 'lucide-react';
import { api, FileInfo, ModelStatusResponse, ModelsResponse } from '@/lib/api';

interface FileSidebarProps {
  onFileSelect: (docId: string, filename: string) => void;
  selectedDocId: string | null;
  projectId?: string;
}

export default function FileSidebar({ onFileSelect, selectedDocId, projectId }: FileSidebarProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelStatus, setModelStatus] = useState<ModelStatusResponse | null>(null);
  const [activeModel, setActiveModel] = useState<string>('');
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    try {
      setLoading(true);
      const fileList = await api.listFiles(projectId);
      setFiles(fileList);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  useEffect(() => {
    const loadModels = async () => {
      try {
        setModelsLoading(true);
        setModelError(null);
        const data = await api.listModels();
        setModels(data);
        const status = await api.getModelStatus();
        setModelStatus(status);
        if (status?.active_model) {
          setActiveModel(status.active_model);
        } else if (data.llm && data.llm.length > 0) {
          setActiveModel(data.llm[0].name);
        }
      } catch (error) {
        console.error('Failed to load models:', error);
        setModelError(error instanceof Error ? error.message : 'Failed to load models');
      } finally {
        setModelsLoading(false);
      }
    };
    loadModels();
  }, []);

  const handleModelChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value;
    if (!selected || selected === activeModel) return;
    setActiveModel(selected);
    setModelLoading(true);
    setModelError(null);
    try {
      const status = await api.loadModel(selected);
      setModelStatus(status);
    } catch (error) {
      console.error('Failed to load model:', error);
      setModelError(error instanceof Error ? error.message : 'Failed to load model');
    } finally {
      setModelLoading(false);
    }
  };

  // Poll for updates when files are processing
  useEffect(() => {
    const hasProcessingFiles = files.some(
      (f) => f.status === 'processing' || f.status === 'pending'
    );
    if (!hasProcessingFiles) return;
    const interval = setInterval(() => loadFiles(), 2000);
    return () => clearInterval(interval);
  }, [files, loadFiles]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        await handleFileUpload(e.dataTransfer.files[0]);
      }
    },
    [projectId]
  );

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith('.pdf')) {
      alert('Only PDF files are supported');
      return;
    }
    setUploading(true);
    try {
      await api.uploadFile(file, projectId);
      alert(`Successfully uploaded ${file.name}`);
    } catch (error) {
      console.error('Upload failed:', error);
      alert(`Upload failed: ${error instanceof Error ? error.message : 'Please try again'}`);
    } finally {
      setUploading(false);
      await loadFiles();
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

  const renderModelList = (items?: Array<{ name: string }>, emptyLabel?: string) => {
    if (!items || items.length === 0) {
      return <p className="text-xs text-gray-600">{emptyLabel || 'None found'}</p>;
    }
    return (
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.name} className="text-xs text-gray-400 truncate" title={item.name}>
            {item.name}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Documents</h2>

        {/* Upload Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
            dragActive
              ? 'border-blue-500 bg-blue-900/20'
              : 'border-gray-700 hover:border-gray-600'
          }`}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileInputChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={uploading}
          />
          <Upload
            className={`mx-auto h-8 w-8 mb-2 ${uploading ? 'text-gray-700' : 'text-gray-500'}`}
          />
          <p className="text-xs text-gray-500">
            {uploading ? 'Uploading...' : 'Drop PDF or click to upload'}
          </p>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="text-center py-8 text-gray-600 text-xs">Loading...</div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">
            No documents yet. Upload a PDF to get started.
          </div>
        ) : (
          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.doc_id}
                className={`group p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedDocId === file.doc_id
                    ? 'bg-blue-900/30 border-blue-700'
                    : 'bg-gray-800/30 border-gray-700/50 hover:border-gray-600'
                }`}
                onClick={() => onFileSelect(file.doc_id, file.filename)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <File className="h-4 w-4 text-gray-500 flex-shrink-0" />
                      <p className="text-xs font-medium text-gray-300 truncate">{file.filename}</p>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {file.status === 'indexed' ? (
                        <CheckCircle className="h-3 w-3 text-emerald-500" />
                      ) : (
                        <Clock className="h-3 w-3 text-yellow-500" />
                      )}
                      <span className="text-xs text-gray-500 capitalize">{file.status}</span>
                      {(file.status === 'processing' || file.status === 'pending') &&
                      file.progress !== undefined &&
                      file.total_chunks !== undefined &&
                      file.total_chunks > 0 ? (
                        <span className="text-xs text-blue-400 font-medium">
                          {file.progress.toFixed(0)}%
                        </span>
                      ) : null}
                      <span className="text-xs text-gray-600">
                        {formatFileSize(file.size_bytes)}
                      </span>
                    </div>
                  </div>

                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(file.doc_id, file.filename);
                      }}
                      className="p-1 hover:bg-red-900/50 rounded"
                      title="Delete"
                    >
                      <Trash2 className="h-3 w-3 text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Models */}
      <div className="border-t border-gray-800 p-4">
        <h3 className="text-xs font-semibold text-gray-400 mb-2">Models</h3>
        {modelsLoading ? (
          <p className="text-xs text-gray-600">Loading models...</p>
        ) : !models ? (
          <p className="text-xs text-gray-600">Unavailable</p>
        ) : (
          <div className="space-y-3">
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Active LLM</p>
              <select
                value={activeModel}
                onChange={handleModelChange}
                disabled={modelLoading || !models.llm || models.llm.length === 0}
                className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-800/50 disabled:text-gray-500"
              >
                {models.llm && models.llm.length > 0 ? (
                  models.llm.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.name}
                    </option>
                  ))
                ) : (
                  <option value="">No models found</option>
                )}
              </select>
              <div className="mt-1 text-[10px] text-gray-500">
                {modelStatus ? (
                  <>
                    <div>
                      {modelStatus.fallback
                        ? 'CPU fallback'
                        : modelStatus.device === 'gpu'
                        ? 'GPU active'
                        : modelStatus.device === 'cpu'
                        ? 'CPU active'
                        : 'Unloaded'}
                    </div>
                    <div>
                      {modelStatus.model_type} · layers {modelStatus.gpu_layers}
                    </div>
                  </>
                ) : (
                  <div>Status unknown</div>
                )}
              </div>
              {modelError && (
                <p className="text-[10px] text-red-400 mt-1">{modelError}</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">LLM (GGUF)</p>
              {renderModelList(models.llm, 'No LLM models')}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Embeddings</p>
              {renderModelList(models.embeddings, 'No embedding models')}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">NER</p>
              {renderModelList(models.ner, 'No NER models')}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
