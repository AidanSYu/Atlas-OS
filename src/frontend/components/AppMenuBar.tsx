'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
  Upload,
  FileDown,
  Download,
  Settings,
  Home,
  Network,
  MessageSquare,
  History,
  HelpCircle,
  ChevronRight,
  Layers,
} from 'lucide-react';

export interface AppMenuBarProps {
  projectId?: string;
  projectName?: string;
  /** Trigger file upload (programmatic click on hidden input) */
  onUploadDocuments?: () => void;
  /** Trigger BibTeX/RIS import (programmatic click on hidden input) */
  onImportBibtex?: () => void;
  onExport?: (type: 'bibtex' | 'markdown' | 'chat') => void;
  onOpenSettings?: () => void;
  onSwitchView?: (view: 'document' | 'graph' | 'chat' | 'canvas') => void;
  onOpenRunHistory?: () => void;
}

type MenuId = 'file' | 'edit' | 'view' | 'go' | 'run' | 'help' | null;

export function AppMenuBar({
  projectId,
  projectName,
  onUploadDocuments,
  onImportBibtex,
  onExport,
  onOpenSettings,
  onSwitchView,
  onOpenRunHistory,
}: AppMenuBarProps) {
  const router = useRouter();
  const [openMenu, setOpenMenu] = useState<MenuId>(null);
  const [exportSubOpen, setExportSubOpen] = useState(false);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
        setExportSubOpen(false);
      }
    };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  const toggle = (id: MenuId) => {
    setOpenMenu((prev) => (prev === id ? null : id));
    if (id !== 'file') setExportSubOpen(false);
  };

  const handleExport = (type: 'bibtex' | 'markdown' | 'chat') => {
    onExport?.(type);
    setExportSubOpen(false);
    setOpenMenu(null);
  };

  return (
    <div ref={barRef} className="flex h-full items-center">
      <div className="flex items-center gap-0.5 text-[13px] text-muted-foreground/90 font-light">
        {/* File */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('file')}
          onMouseLeave={() => { setOpenMenu(null); setExportSubOpen(false); }}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'file' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            File
          </button>
          {openMenu === 'file' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[220px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem
                icon={Upload}
                label="Upload Documents..."
                onClick={() => { onUploadDocuments?.(); setOpenMenu(null); }}
                disabled={!projectId}
              />
              <MenuItem
                icon={FileDown}
                label="Import BibTeX/RIS..."
                onClick={() => { onImportBibtex?.(); setOpenMenu(null); }}
                disabled={!projectId}
              />
              <div className="my-1 border-t border-border" />
              <div
                className="relative"
                onMouseEnter={() => setExportSubOpen(true)}
                onMouseLeave={() => setExportSubOpen(false)}
              >
                <MenuItem icon={Download} label="Export" hasSub />
                {exportSubOpen && (
                  <div className="absolute left-full top-0 z-[10001] ml-0.5 min-w-[180px] rounded border border-border bg-card py-1 shadow-2xl">
                    <MenuItem icon={FileText} label="BibTeX (.bib)" onClick={() => handleExport('bibtex')} />
                    <MenuItem icon={FileText} label="Markdown (.md)" onClick={() => handleExport('markdown')} />
                    <MenuItem icon={MessageSquare} label="Chat history (.md)" onClick={() => handleExport('chat')} />
                  </div>
                )}
              </div>
              <div className="my-1 border-t border-border" />
              <MenuItem icon={Settings} label="Settings..." onClick={() => { onOpenSettings?.(); setOpenMenu(null); }} />
              <MenuItem icon={Home} label="Back to Dashboard" onClick={() => { router.push('/'); setOpenMenu(null); }} />
            </div>
          )}
        </div>

        {/* Edit */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('edit')}
          onMouseLeave={() => setOpenMenu(null)}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'edit' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            Edit
          </button>
          {openMenu === 'edit' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[200px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem label="Find in workspace..." onClick={() => setOpenMenu(null)} />
              <MenuItem label="Preferences" onClick={() => { onOpenSettings?.(); setOpenMenu(null); }} />
            </div>
          )}
        </div>

        {/* View */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('view')}
          onMouseLeave={() => setOpenMenu(null)}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'view' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            View
          </button>
          {openMenu === 'view' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[200px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem icon={FileText} label="Documents" onClick={() => { onSwitchView?.('document'); setOpenMenu(null); }} />
              <MenuItem icon={Network} label="Knowledge Graph" onClick={() => { onSwitchView?.('graph'); setOpenMenu(null); }} />
              <MenuItem icon={MessageSquare} label="Chat" onClick={() => { onSwitchView?.('chat'); setOpenMenu(null); }} />
              <MenuItem icon={Layers} label="Canvas" onClick={() => { onSwitchView?.('canvas'); setOpenMenu(null); }} />
            </div>
          )}
        </div>

        {/* Go */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('go')}
          onMouseLeave={() => setOpenMenu(null)}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'go' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            Go
          </button>
          {openMenu === 'go' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[200px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem icon={Home} label="Back to Dashboard" onClick={() => { router.push('/'); setOpenMenu(null); }} />
              {projectId && (
                <MenuItem icon={FileText} label={`Workspace: ${projectName || projectId}`} onClick={() => setOpenMenu(null)} disabled />
              )}
            </div>
          )}
        </div>

        {/* Run */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('run')}
          onMouseLeave={() => setOpenMenu(null)}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'run' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            Run
          </button>
          {openMenu === 'run' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[220px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem
                icon={History}
                label="Open Run History"
                onClick={() => { onOpenRunHistory?.(); setOpenMenu(null); }}
                disabled={!projectId}
              />
            </div>
          )}
        </div>

        {/* Help */}
        <div
          className="relative flex items-center h-full"
          onMouseEnter={() => setOpenMenu('help')}
          onMouseLeave={() => setOpenMenu(null)}
        >
          <button
            type="button"
            className={`flex h-8 items-center px-2 text-left rounded-md transition-colors ${openMenu === 'help' ? 'bg-primary/10 text-primary' : 'hover:bg-primary/10'}`}
          >
            Help
          </button>
          {openMenu === 'help' && (
            <div className="absolute left-0 top-full z-[10000] min-w-[200px] rounded border border-border bg-card py-1 shadow-2xl">
              <MenuItem icon={HelpCircle} label="Welcome / Tour" onClick={() => setOpenMenu(null)} />
              <MenuItem icon={HelpCircle} label="About Atlas" onClick={() => setOpenMenu(null)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MenuItem({
  icon: Icon,
  label,
  onClick,
  disabled,
  hasSub,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  hasSub?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-primary/10 disabled:opacity-50 disabled:pointer-events-none"
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
      <span className="flex-1">{label}</span>
      {hasSub && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
    </button>
  );
}
