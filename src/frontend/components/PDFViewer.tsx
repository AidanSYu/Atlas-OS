'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCw, Loader2 } from 'lucide-react';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface PDFViewerProps {
  fileUrl: string;
  filename: string;
  initialPage?: number;
}

export default function PDFViewer({ fileUrl, filename, initialPage = 1 }: PDFViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(initialPage);
  const [scale, setScale] = useState<number>(1.0);
  const [rotation, setRotation] = useState<number>(0);
  const [fitMode, setFitMode] = useState<'fit' | 'actual'>('fit');
  const [containerWidth, setContainerWidth] = useState<number>(1000);

  useEffect(() => {
    setPageNumber(initialPage);
  }, [initialPage, fileUrl]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver(() => {
      setContainerWidth(el.clientWidth);
    });

    setContainerWidth(el.clientWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber((prev) => Math.min(Math.max(prev, 1), numPages));
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-11 items-center justify-between border-b border-border bg-card px-3">
        <p className="max-w-[45%] truncate text-xs text-muted-foreground">{filename}</p>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setPageNumber(p => Math.max(p - 1, 1))}
            disabled={pageNumber <= 1}
            className="inline-flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <span className="min-w-[4.5rem] text-center text-xs text-foreground">
             {pageNumber} / {numPages || '-'}
          </span>

          <button
            onClick={() => setPageNumber(p => Math.min(p + 1, numPages))}
            disabled={pageNumber >= numPages}
            className="inline-flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>

          <div className="mx-1 h-5 w-px bg-border" />

          <button
            onClick={() => {
              setFitMode('actual');
              setScale(s => Math.max(s - 0.1, 0.5));
            }}
            className="inline-flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
          >
             <ZoomOut className="h-3 w-3" />
          </button>

          <span className="w-10 text-center text-[11px] text-muted-foreground">{Math.round(scale * 100)}%</span>

          <button
            onClick={() => {
              setFitMode('actual');
              setScale(s => Math.min(s + 0.1, 3.0));
            }}
            className="inline-flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
          >
             <ZoomIn className="h-3 w-3" />
          </button>

          <button
            onClick={() => setRotation(r => (r + 90) % 360)}
            className="inline-flex h-7 items-center justify-center border border-border bg-surface px-2 text-xs text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
          >
            <RotateCw className="mr-1 h-3 w-3" />
            Rotate
          </button>

          <button
            onClick={() => {
              setFitMode('fit');
              setScale(1);
            }}
            className={`inline-flex h-7 items-center justify-center border border-border px-2 text-xs transition-colors ${
              fitMode === 'fit'
                ? 'bg-background text-foreground'
                : 'bg-surface text-muted-foreground hover:bg-accent/15 hover:text-foreground'
            }`}
          >
            Fit
          </button>
        </div>
      </div>

      <div ref={containerRef} className="flex-1 overflow-auto bg-background p-6">
        <div className="mx-auto flex min-h-full w-full justify-center">
         <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={
                <div className="flex h-64 w-full items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            }
            error={
                <div className="flex h-64 w-full items-center justify-center text-sm text-destructive">
                    Failed to load PDF.
                </div>
            }
            className="border border-border bg-surface"
         >
            <Page
                pageNumber={pageNumber}
                scale={scale}
                rotate={rotation}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                className="bg-white"
                width={fitMode === 'fit' ? Math.max(320, Math.min(1100, Math.floor(containerWidth - 80))) : undefined}
            />
         </Document>
        </div>
      </div>
    </div>
  );
}
