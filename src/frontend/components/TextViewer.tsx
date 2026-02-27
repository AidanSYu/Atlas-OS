'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Loader2, FileText, ZoomIn, ZoomOut, Copy, Check } from 'lucide-react';
import { api } from '@/lib/api';

interface TextViewerProps {
  fileUrl: string;
  filename: string;
  docId?: string;
  projectId?: string;
  onContextChange?: (selectedText?: string, docId?: string, pageNumber?: number) => void;
}

export default function TextViewer({ fileUrl, filename, docId, projectId, onContextChange }: TextViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fontSize, setFontSize] = useState(14);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(fileUrl)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load file: ${res.statusText}`);
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setContent(text);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [fileUrl]);

  const handleTextSelect = useCallback(() => {
    const selection = window.getSelection()?.toString().trim();
    if (selection && onContextChange) {
      onContextChange(selection, docId, 1);
    }
  }, [docId, onContextChange]);

  const handleCopy = useCallback(async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary/60" />
        <p className="text-sm text-muted-foreground">Loading document...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-destructive">
        <FileText className="h-8 w-8" />
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  const lineCount = content?.split('\n').length ?? 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex shrink-0 items-center justify-between border-b border-border/50 bg-background/80 backdrop-blur-sm px-4 py-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary/60" />
          <span className="text-xs font-medium text-foreground/80 truncate max-w-[300px]">{filename}</span>
          <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {lineCount} lines
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFontSize((s) => Math.max(10, s - 1))}
            className="rounded p-1.5 text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
            title="Decrease font size"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <span className="text-[10px] text-muted-foreground font-mono w-8 text-center">{fontSize}px</span>
          <button
            onClick={() => setFontSize((s) => Math.min(24, s + 1))}
            className="rounded p-1.5 text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
            title="Increase font size"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <div className="mx-1 h-4 w-px bg-border/50" />
          <button
            onClick={handleCopy}
            className="rounded p-1.5 text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
            title="Copy all text"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-auto p-6 custom-scrollbar"
        onMouseUp={handleTextSelect}
      >
        <pre
          className="whitespace-pre-wrap break-words font-mono text-foreground/90 leading-relaxed"
          style={{ fontSize: `${fontSize}px` }}
        >
          {content}
        </pre>
      </div>
    </div>
  );
}
