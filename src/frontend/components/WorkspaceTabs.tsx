'use client';

import React, { useState } from 'react';
import { FileText, FlaskConical, Puzzle, X } from 'lucide-react';

/* ================================================================
   WorkspaceTabs — tabbed interface for documents, sessions, plugins
   Each tab has a visible border separating it from neighbors.
   ================================================================ */

export type WorkspaceTab =
  | { kind: 'document'; id: string; docId: string; filename: string }
  | { kind: 'session'; id: string; threadId: string; title: string }
  | { kind: 'plugins'; id: string };

interface WorkspaceTabsProps {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onReorder?: (fromIndex: number, toIndex: number) => void;
}

function getTabIcon(tab: WorkspaceTab) {
  switch (tab.kind) {
    case 'document': return <FileText className="h-3.5 w-3.5 shrink-0" />;
    case 'session': return <FlaskConical className="h-3.5 w-3.5 shrink-0" />;
    case 'plugins': return <Puzzle className="h-3.5 w-3.5 shrink-0" />;
  }
}

function getTabLabel(tab: WorkspaceTab): string {
  switch (tab.kind) {
    case 'document': return tab.filename;
    case 'session': return tab.title;
    case 'plugins': return 'Plugins';
  }
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
    <div className="flex h-9 shrink-0 items-stretch border-b border-border bg-card">
      {tabs.map((tab, index) => {
        const isActive = tab.id === activeTabId;
        const isDragOver = dragOverIndex === index;
        const isDragging = draggedIndex === index;

        return (
          <div
            key={tab.id}
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
            className={[
              'group flex max-w-[220px] cursor-pointer items-center gap-2 border-r border-border px-3 text-xs transition-colors',
              isActive
                ? 'tab-active bg-background text-foreground'
                : 'bg-card text-muted-foreground hover:bg-surface hover:text-foreground',
              isDragOver ? 'bg-accent/5' : '',
              isDragging ? 'opacity-40' : '',
            ].join(' ')}
            onClick={() => onSelectTab(tab.id)}
          >
            {getTabIcon(tab)}
            <span className="min-w-0 truncate" title={getTabLabel(tab)}>
              {getTabLabel(tab)}
            </span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id); }}
              className="ml-auto flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/20 hover:text-destructive group-hover:opacity-100"
              aria-label="Close tab"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
      {/* empty space after tabs — just background */}
      <div className="flex-1 bg-card" />
    </div>
  );
}

// Backward compat
export type DocumentTab = Extract<WorkspaceTab, { kind: 'document' }>;
export { WorkspaceTabs as DocumentTabs };
