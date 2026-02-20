'use client';

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  Loader2,
  Search,
  ChevronDown,
  ChevronRight,
  FolderOpen,
  Sparkles,
  X,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { api, FileInfo } from '@/lib/api';
import { toastError } from '@/stores/toastStore';

interface LibrarySidebarProps {
  onFileSelect: (docId: string, filename: string) => void;
  selectedDocId: string | null;
  projectId: string;
  onIngestionComplete?: () => void;
}

export default function LibrarySidebar({
  onFileSelect,
  selectedDocId,
  projectId,
  onIngestionComplete,
}: LibrarySidebarProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [smartGroupsOpen, setSmartGroupsOpen] = useState(true);
  const [allDocsOpen, setAllDocsOpen] = useState(true);
  const prevProcessingRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(
    async (silent = false) => {
      if (!projectId) return;
      try {
        if (!silent) setLoading(true);
        const fileList = await api.listFiles(projectId);
        setFiles(fileList);
      } catch (error) {
        console.error('Failed to load files:', error);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [projectId]
  );

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const hasProcessing = files.some((f) => f.status === 'processing');

  useEffect(() => {
    if (!hasProcessing) {
      if (prevProcessingRef.current && onIngestionComplete) {
        onIngestionComplete();
      }
      prevProcessingRef.current = false;
      return;
    }
    prevProcessingRef.current = true;
    const interval = window.setInterval(() => loadFiles(true), 3000);
    return () => window.clearInterval(interval);
  }, [hasProcessing, loadFiles, onIngestionComplete]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (!fileList || fileList.length === 0 || !projectId) return;

    setUploading(true);
    try {
      for (let i = 0; i < fileList.length; i++) {
        await api.uploadFile(fileList[i], projectId);
      }
      await loadFiles();
    } catch (error) {
      toastError((error as Error).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (e: React.MouseEvent, fileId: string) => {
    e.stopPropagation();
    try {
      await api.deleteFile(fileId);
      setFiles((prev) => prev.filter((f) => f.doc_id !== fileId));
    } catch (err) {
      console.error(err);
    }
  };

  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files;
    const q = searchQuery.toLowerCase();
    return files.filter((f) => f.filename.toLowerCase().includes(q));
  }, [files, searchQuery]);

  // Group files by extension type
  const fileGroups = useMemo(() => {
    const groups: Record<string, FileInfo[]> = {};
    files.forEach((f) => {
      const ext = f.filename.split('.').pop()?.toUpperCase() || 'OTHER';
      if (!groups[ext]) groups[ext] = [];
      groups[ext].push(f);
    });
    return groups;
  }, [files]);

  const stats = useMemo(() => {
    const total = files.length;
    const ready = files.filter((f) => f.status === 'completed' || f.status === 'indexed').length;
    const processing = files.filter((f) => f.status === 'processing').length;
    return { total, ready, processing };
  }, [files]);

  const StatusIcon = ({ status }: { status: string }) => {
    if (status === 'completed' || status === 'indexed') {
      return <CheckCircle2 className="h-3 w-3 text-emerald-400" />;
    }
    if (status === 'processing') {
      return <Loader2 className="h-3 w-3 animate-spin text-amber-400" />;
    }
    return <Clock className="h-3 w-3 text-muted-foreground" />;
  };

  return (
    <div className="flex h-full flex-col">
      {/* Search */}
      <div className="shrink-0 p-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents..."
            className="h-8 w-full rounded-lg border border-border bg-background pl-8 pr-8 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Stats bar */}
      {files.length > 0 && (
        <div className="mx-3 mb-2 flex items-center gap-3 rounded-md bg-surface/50 px-2.5 py-1.5">
          <span className="text-[10px] text-muted-foreground">
            <span className="font-semibold text-foreground">{stats.total}</span> docs
          </span>
          <span className="text-[10px] text-emerald-400">
            {stats.ready} ready
          </span>
          {stats.processing > 0 && (
            <span className="text-[10px] text-amber-400 flex items-center gap-1">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
              {stats.processing} processing
            </span>
          )}
        </div>
      )}

      {/* File Tree */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="text-[10px] text-muted-foreground">Loading library...</span>
            </div>
          </div>
        ) : files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="rounded-full bg-primary/10 p-3 mb-3">
              <Upload className="h-6 w-6 text-primary" />
            </div>
            <p className="text-sm font-medium text-foreground">No documents yet</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Upload PDFs to start building your knowledge base
            </p>
          </div>
        ) : (
          <>
            {/* Smart Groups */}
            {Object.keys(fileGroups).length > 1 && !searchQuery && (
              <div className="mb-1">
                <button
                  onClick={() => setSmartGroupsOpen(!smartGroupsOpen)}
                  className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
                >
                  {smartGroupsOpen ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                  <Sparkles className="h-3 w-3 text-primary" />
                  Groups
                </button>
                {smartGroupsOpen && (
                  <div className="mt-0.5 space-y-0.5 pl-2">
                    {Object.entries(fileGroups).map(([ext, groupFiles]) => (
                      <div
                        key={ext}
                        className="flex items-center gap-2 rounded-md px-2 py-1 text-[11px] text-muted-foreground"
                      >
                        <FolderOpen className="h-3 w-3 text-primary/60" />
                        <span>{ext} Files</span>
                        <span className="ml-auto rounded bg-surface px-1.5 py-0.5 text-[10px]">
                          {groupFiles.length}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* All Documents */}
            <div>
              <button
                onClick={() => setAllDocsOpen(!allDocsOpen)}
                className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                {allDocsOpen ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                All Documents
              </button>
              {allDocsOpen && (
                <div className="mt-0.5 space-y-0.5">
                  {filteredFiles.map((file) => (
                    <div
                      key={file.doc_id}
                      onClick={() => onFileSelect(file.doc_id, file.filename)}
                      className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 transition-all ${
                        selectedDocId === file.doc_id
                          ? 'bg-primary/15 text-foreground border border-primary/30'
                          : 'text-muted-foreground hover:bg-surface hover:text-foreground border border-transparent'
                      }`}
                    >
                      <StatusIcon status={file.status} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium">{file.filename}</p>
                        <p className="text-[10px] opacity-60">
                          {((file.size_bytes || 0) / 1024).toFixed(0)} KB
                        </p>
                      </div>
                      <button
                        onClick={(e) => handleDelete(e, file.doc_id)}
                        className="rounded p-1 opacity-0 transition-all group-hover:opacity-100 hover:bg-destructive/20 hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Upload Area */}
      <div className="shrink-0 border-t border-border p-3">
        <label
          className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-border p-2.5 transition-all hover:border-primary/50 hover:bg-primary/5 ${
            uploading ? 'pointer-events-none opacity-50' : ''
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileUpload}
            accept=".pdf,.txt,.docx,.doc"
            multiple
            disabled={uploading}
          />
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          ) : (
            <Upload className="h-4 w-4 text-primary" />
          )}
          <span className="text-xs font-medium text-muted-foreground">
            {uploading ? 'Uploading...' : 'Upload Documents'}
          </span>
        </label>
      </div>
    </div>
  );
}
