'use client';

import React, { useState } from 'react';
import { FileText, FlaskConical, X } from 'lucide-react';

export type WorkspaceTab =
  | { kind: 'document'; id: string; docId: string; filename: string }
  | { kind: 'discovery'; id: string; sessionId: string; sessionName: string };

interface WorkspaceTabsProps {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onReorder?: (fromIndex: number, toIndex: number) => void;
}

export function WorkspaceTabs({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onReorder,
}: WorkspaceTabsProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  };

  const handleDragLeave = () => setDragOverIndex(null);

  const handleDrop = (e: React.DragEvent, toIndex: number) => {
    e.preventDefault();
    const fromIndex = draggedIndex;
    setDraggedIndex(null);
    setDragOverIndex(null);
    if (fromIndex != null && fromIndex !== toIndex && onReorder) {
      onReorder(fromIndex, toIndex);
    }
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  if (tabs.length === 0) return null;

  return (
    <div className="flex h-9 shrink-0 items-end gap-0.5 border-b border-border bg-card/50 px-1">
      {tabs.map((tab, index) => {
        const isActive = tab.id === activeTabId;
        const isDragOver = dragOverIndex === index;
        const isDragging = draggedIndex === index;

        const icon = tab.kind === 'document' ? (
          <FileText className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <FlaskConical className="h-3.5 w-3.5 shrink-0 text-orange-500" />
        );

        const label = tab.kind === 'document' ? tab.filename : tab.sessionName;

        return (
          <div
            key={tab.id}
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
            className={`
              group flex max-w-[200px] cursor-pointer items-center gap-2 rounded-t-md border border-b-0 border-transparent px-3 py-1.5 text-xs transition-all
              ${isActive ? 'border-border bg-background text-foreground' : 'text-muted-foreground hover:bg-surface hover:text-foreground'}
              ${isDragOver ? 'border-primary/40 bg-primary/5' : ''}
              ${isDragging ? 'opacity-50' : ''}
            `}
            onClick={() => onSelectTab(tab.id)}
          >
            {icon}
            <span className="min-w-0 truncate" title={label}>
              {label}
            </span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id); }}
              className="ml-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/20 hover:text-destructive group-hover:opacity-100"
              aria-label="Close tab"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// Backward compatibility export
export type DocumentTab = Extract<WorkspaceTab, { kind: 'document' }>;
export { WorkspaceTabs as DocumentTabs };
