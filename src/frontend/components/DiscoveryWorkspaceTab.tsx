'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useDiscoveryStore } from '@/stores/discoveryStore';
import { DiscoveryWorkbench } from './DiscoveryWorkbench';
import ChatShell from '@/components/chat/ChatShell';
import { ScriptApprovalModal } from './ScriptApprovalModal';
import { PluginManager } from './PluginManager';
import { MessageSquare, Download, FileText, Loader2, Play, X, Eye } from 'lucide-react';
import { api, getApiBase } from '@/lib/api';
import { streamSSE, type NormalizedEvent } from '@/lib/stream-adapter';
import { usePanelResize } from '@/hooks/usePanelResize';

interface DiscoveryWorkspaceTabProps {
  sessionId: string;
  projectId: string;
}

// ---------------------------------------------------------------------------
// Drag-handle divider — shared between horizontal and vertical splits
// ---------------------------------------------------------------------------
function DragHandle({
  direction,
  onMouseDown,
  isDragging,
}: {
  direction: 'horizontal' | 'vertical';
  onMouseDown: (e: React.MouseEvent) => void;
  isDragging: boolean;
}) {
  const isH = direction === 'horizontal';
  return (
    <div
      onMouseDown={onMouseDown}
      className={[
        'group relative shrink-0 flex items-center justify-center',
        'transition-colors duration-100 select-none',
        isH
          ? 'w-[5px] cursor-col-resize hover:bg-safety/20 active:bg-safety/30'
          : 'h-[5px] cursor-row-resize hover:bg-safety/20 active:bg-safety/30',
        isDragging ? (isH ? 'bg-safety/30' : 'bg-safety/30') : 'bg-border/60',
      ].join(' ')}
    >
      {/* Visual indicator bar */}
      <div
        className={[
          'rounded-full bg-border group-hover:bg-safety/60 transition-colors duration-100',
          isDragging ? 'bg-safety/60' : '',
          isH ? 'w-[2px] h-8' : 'h-[2px] w-8',
        ].join(' ')}
      />
    </div>
  );
}

export function DiscoveryWorkspaceTab({ sessionId, projectId }: DiscoveryWorkspaceTabProps) {
  const session = useDiscoveryStore((s) => s.sessions[sessionId]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Resizable panel sizes — persisted in localStorage
  // ---------------------------------------------------------------------------
  const { size: leftWidth, handleMouseDown: handleHDrag, isDragging: isHDragging } = usePanelResize({
    initialSize: 380,
    minSize: 240,
    maxSize: 620,
    direction: 'horizontal',
    storageKey: 'discovery-left-panel-width',
  });
  const { size: pluginHeight, handleMouseDown: handleV1Drag, isDragging: isV1Dragging } = usePanelResize({
    initialSize: 192, // h-48 = 12rem = 192px
    minSize: 80,
    maxSize: 400,
    direction: 'vertical',
    invert: true, // handle sits above this panel — drag down to shrink
    storageKey: 'discovery-plugin-panel-height',
  });
  const { size: filesHeight, handleMouseDown: handleV2Drag, isDragging: isV2Dragging } = usePanelResize({
    initialSize: 128, // h-32 = 8rem = 128px
    minSize: 60,
    maxSize: 300,
    direction: 'vertical',
    invert: true, // handle sits above this panel — drag down to shrink
    storageKey: 'discovery-files-panel-height',
  });
  // ---------------------------------------------------------------------------

  // File preview state
  const [previewFile, setPreviewFile] = useState<{
    filename: string;
    content: string;
  } | null>(null);

  const handleViewFile = useCallback(async (filePath: string) => {
    try {
      const file = await api.readSessionFile(sessionId, filePath);
      setPreviewFile({ filename: file.filename, content: file.content });
    } catch (err) {
      console.error('Failed to read session file:', err);
    }
  }, [sessionId]);

  // Phase 5: Executor state
  const [executorRunning, setExecutorRunning] = useState(false);
  const [pendingScript, setPendingScript] = useState<{
    filename: string;
    code: string;
    description: string;
    requiredPackages: string[];
  } | null>(null);

  // Fetch session files from backend on mount
  useEffect(() => {
    async function loadSessionFiles() {
      try {
        setIsLoading(true);
        setError(null);
        const files = await api.getSessionFiles(sessionId);

        // Update the discoveryStore with fetched files (store paths, not just names)
        useDiscoveryStore.setState((state) => {
          if (state.sessions[sessionId]) {
            return {
              ...state,
              sessions: {
                ...state.sessions,
                [sessionId]: {
                  ...state.sessions[sessionId],
                  generatedFiles: files.map(f => f.path),
                },
              },
            };
          }
          return state;
        });
      } catch (err) {
        // Gracefully handle 404 (backend session row not created yet) — do not block UI.
        // Any other error surfaces as a soft warning in the console only.
        const msg = err instanceof Error ? err.message : String(err);
        if (!msg.includes('404') && !msg.toLowerCase().includes('not found')) {
          console.error('Failed to load session files:', err);
        }
        // Don't set error state — allow workspace to render with empty file list.
      } finally {
        setIsLoading(false);
      }
    }

    loadSessionFiles();
  }, [sessionId]);

  // Phase 5: Executor handlers (must come before handleCoordinatorComplete which depends on it)
  const refreshSessionFiles = useCallback(async () => {
    try {
      const files = await api.getSessionFiles(sessionId);
      useDiscoveryStore.setState((state) => {
        if (state.sessions[sessionId]) {
          return {
            ...state,
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...state.sessions[sessionId],
                generatedFiles: files.map((f) => f.path),
              },
            },
          };
        }
        return state;
      });
    } catch (err) {
      console.error('Failed to refresh session files:', err);
    }
  }, [sessionId]);

  // All hooks must come before any early returns (Rules of Hooks)
  const handleCoordinatorComplete = useCallback((goals: string[]) => {
    useDiscoveryStore.setState((state) => {
      const s = state.sessions[sessionId];
      if (!s) return state;
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [sessionId]: { ...s, status: 'complete' as const },
        },
      };
    });

    // Refresh file list — coordinator writes SESSION_INIT.md and session_memory.json
    refreshSessionFiles();
  }, [sessionId, refreshSessionFiles]);

  const handleStartExecutor = useCallback(async (bodyOverrides: Record<string, any> = {}) => {
    setExecutorRunning(true);
    const url = `${getApiBase()}/api/discovery/${sessionId}/executor/start`;

    try {
      await streamSSE(
        url,
        { auto_approve: false, ...bodyOverrides },
        (event: NormalizedEvent) => {
          switch (event.type) {
            case 'executor_script_generated':
              setPendingScript({
                filename: event.filename,
                code: event.code,
                description: event.description,
                requiredPackages: event.requiredPackages,
              });
              break;

            case 'executor_artifact':
              // Refresh file list when new artifact is generated
              refreshSessionFiles();
              break;

            case 'executor_complete':
              setExecutorRunning(false);
              refreshSessionFiles();
              break;

            case 'error':
              console.error('Executor error:', event.message);
              setExecutorRunning(false);
              break;
          }
        },
        { timeout: 600000 } // 10 minutes
      );
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Executor stream error:', err);
        setExecutorRunning(false);
      }
    }
  }, [sessionId, refreshSessionFiles]);

  const handleApproveScript = useCallback(async () => {
    setPendingScript(null);
    handleStartExecutor({ decision: 'approve' });
  }, [handleStartExecutor]);

  const handleRejectScript = useCallback(async () => {
    setPendingScript(null);
    setExecutorRunning(false);
    handleStartExecutor({ decision: 'reject' });
  }, [handleStartExecutor]);

  const handleEditScript = useCallback(
    async (editedCode: string) => {
      setPendingScript(null);
      handleStartExecutor({ decision: 'edit', edited_code: editedCode });
    },
    [handleStartExecutor]
  );

  // Poll for new files during execution
  useEffect(() => {
    if (!executorRunning) return;

    const interval = setInterval(() => {
      refreshSessionFiles();
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [executorRunning, refreshSessionFiles]);

  // --- Early returns (after all hooks) ---

  if (!session) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Session not found: {sessionId}</p>
          <p className="text-xs text-muted-foreground mt-2">This session may have been deleted or corrupted.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">Loading Discovery Session</p>
            <p className="text-xs text-muted-foreground mt-1">{session.sessionName}</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <p className="text-sm text-destructive">Error: {error}</p>
          <p className="text-xs text-muted-foreground mt-2">Failed to load session data</p>
        </div>
      </div>
    );
  }

  const activeEpoch = session.activeEpochId ? session.epochs.get(session.activeEpochId) : null;

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* ========== LEFT: Coordinator Chat ========== */}
      <div
        className="flex shrink-0 flex-col border-r border-border bg-card overflow-hidden"
        style={{ width: leftWidth }}
      >
        <div className="flex h-11 shrink-0 items-center gap-2 border-b border-border bg-surface/30 px-3">
          <MessageSquare className="h-3.5 w-3.5 text-emerald-500" />
          <span className="text-xs font-medium text-foreground/80">Coordinator</span>
          <span className="ml-auto rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-500">
            Discovery Mode
          </span>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden">
          <ChatShell
            lockedMode="coordinator"
            coordinatorSessionId={sessionId}
            projectId={projectId}
            onCitationClick={(filename, page) => {
              console.log('Citation clicked:', filename, page);
            }}
            onCoordinatorComplete={handleCoordinatorComplete}
          />
        </div>

        {/* Phase 5: Start Execution Button */}
        {session.status === 'complete' && !executorRunning && (
          <div className="shrink-0 border-t border-border bg-card/50 p-3">
            <button
              onClick={handleStartExecutor}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-orange-600"
            >
              <Play className="h-4 w-4" />
              Start Execution Sandbox
            </button>
            <p className="mt-2 text-center text-[10px] text-muted-foreground">
              Generate and execute Python scripts
            </p>
          </div>
        )}

        {executorRunning && (
          <div className="shrink-0 border-t border-border bg-orange-500/10 p-3">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-orange-500" />
              <span className="text-xs font-medium text-orange-500">Executor Running...</span>
            </div>
          </div>
        )}
      </div>

      {/* ========== HORIZONTAL DRAG HANDLE ========== */}
      <DragHandle direction="horizontal" onMouseDown={handleHDrag} isDragging={isHDragging} />

      {/* ========== RIGHT: Tools + Plugins + Files ========== */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Top: DiscoveryWorkbench — takes remaining space */}
        <div className="min-h-0 flex-1 overflow-hidden">
          <DiscoveryWorkbench
            streamProgress={null}
            isLoading={session.status === 'running'}
            finalCandidates={activeEpoch?.candidates || []}
          />
        </div>

        {/* ========== VERTICAL DRAG HANDLE 1 (workbench ↔ plugins) ========== */}
        <DragHandle direction="vertical" onMouseDown={handleV1Drag} isDragging={isV1Dragging} />

        {/* Middle: Plugin Manager */}
        <div className="shrink-0 overflow-y-auto" style={{ height: pluginHeight }}>
          <PluginManager projectId={projectId} />
        </div>

        {/* ========== VERTICAL DRAG HANDLE 2 (plugins ↔ files) ========== */}
        <DragHandle direction="vertical" onMouseDown={handleV2Drag} isDragging={isV2Dragging} />

        {/* Bottom: Session Files */}
        <div className="shrink-0 bg-card/50" style={{ height: filesHeight }}>
          <div className="flex h-9 items-center gap-2 border-b border-border/50 bg-background/50 px-3">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Session Files
            </span>
            <span className="ml-auto text-[10px] text-muted-foreground">
              {session.generatedFiles.length} files
            </span>
          </div>
          <div className="overflow-y-auto p-2 h-[calc(100%-2.25rem)]">
            {session.generatedFiles.length === 0 ? (
              <p className="text-xs text-muted-foreground italic text-center py-4">
                No files generated yet. The coordinator will create session files when initialization completes.
              </p>
            ) : (
              <div className="space-y-1">
                {session.generatedFiles.map((file, idx) => {
                  const isViewable = /\.(md|json|txt|csv|py|log)$/i.test(file);
                  return (
                    <button
                      key={idx}
                      onClick={() => isViewable && handleViewFile(file)}
                      className={[
                        'flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs transition-colors group text-left',
                        isViewable
                          ? 'hover:bg-primary/10 cursor-pointer'
                          : 'hover:bg-surface cursor-default',
                      ].join(' ')}
                    >
                      <FileText className={`h-3 w-3 shrink-0 ${file.endsWith('.md') ? 'text-emerald-500' : 'text-muted-foreground'}`} />
                      <span className="flex-1 truncate font-mono text-foreground/80">{file}</span>
                      {isViewable && (
                        <Eye className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* File Preview Overlay */}
      {previewFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="relative mx-4 flex max-h-[80vh] w-full max-w-3xl flex-col rounded-xl border border-border bg-card shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <FileText className={`h-4 w-4 ${previewFile.filename.endsWith('.md') ? 'text-emerald-500' : 'text-muted-foreground'}`} />
                <span className="text-sm font-medium text-foreground">{previewFile.filename}</span>
              </div>
              <button
                onClick={() => setPreviewFile(null)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-surface hover:text-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              <pre className="whitespace-pre-wrap text-xs font-mono text-foreground/90 leading-relaxed">
                {previewFile.content}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Phase 5: Script Approval Modal */}
      {pendingScript && (
        <ScriptApprovalModal
          script={pendingScript}
          sessionId={sessionId}
          onApprove={handleApproveScript}
          onReject={handleRejectScript}
          onEdit={handleEditScript}
          onClose={() => setPendingScript(null)}
        />
      )}
    </div>
  );
}
