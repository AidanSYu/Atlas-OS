'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import LibrarySidebar from '@/components/LibrarySidebar';
import PDFViewer from '@/components/PDFViewer';
import KnowledgeGraph from '@/components/KnowledgeGraph';
import DualAgentChat from '@/components/DualAgentChat';
import EditorPane from '@/components/EditorPane';
import ContextEngine from '@/components/ContextEngine';
import { OmniBar } from '@/components/OmniBar';
import { api, ModelStatusResponse, ProjectInfo } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useGraphStore } from '@/stores/graphStore';
import { toastError } from '@/stores/toastStore';
import {
  FileText,
  ChevronLeft,
  MessageSquare,
  Network,
  BookOpen,
  PenTool,
  Cpu,
  Loader2,
  Trash2,
  ChevronsLeft,
  ChevronsRight,
  Zap,
  Activity,
} from 'lucide-react';

type MainView = 'document' | 'editor' | 'graph' | 'chat';

const VIEW_TABS: { key: MainView; label: string; icon: typeof FileText }[] = [
  { key: 'document', label: 'Documents', icon: BookOpen },
  { key: 'editor', label: 'Editor', icon: PenTool },
  { key: 'graph', label: 'Graph', icon: Network },
  { key: 'chat', label: 'Deep Chat', icon: MessageSquare },
];

export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = decodeURIComponent(params.id || '');

  const { setActiveProject } = useChatStore();
  const { refreshGraph } = useGraphStore();

  const [currentProject, setCurrentProject] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [activeView, setActiveView] = useState<MainView>('document');
  const [chatMode, setChatMode] = useState<'librarian' | 'cortex'>('librarian');

  const [contextCollapsed, setContextCollapsed] = useState(false);
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatusResponse | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [deletingProject, setDeletingProject] = useState(false);

  const [centerDimensions, setCenterDimensions] = useState({ width: 800, height: 600 });

  // Load project on mount
  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) {
        setLoading(false);
        return;
      }

      try {
        const projects = await api.listProjects();
        const project = projects.find((entry) => entry.id === projectId);
        if (!project) {
          router.push('/');
          return;
        }

        setCurrentProject(project);
        setActiveProject(project.id);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId, router, setActiveProject]);

  // Clear active project on unmount
  useEffect(() => {
    return () => {
      setActiveProject(null);
    };
  }, [setActiveProject]);

  // Track center panel dimensions for graph
  useEffect(() => {
    const updateDimensions = () => {
      const centerPanel = document.getElementById('atlas-main-stage');
      if (!centerPanel) return;
      setCenterDimensions({
        width: centerPanel.clientWidth,
        height: centerPanel.clientHeight,
      });
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Load model controls
  useEffect(() => {
    const loadModelControls = async () => {
      try {
        const [models, status] = await Promise.all([api.listModels(), api.getModelStatus()]);
        setLlmModels(models.llm.map((entry) => entry.name));
        setModelStatus(status);
      } catch (err) {
        console.error('Failed to load model controls:', err);
      }
    };

    loadModelControls();

    const interval = window.setInterval(async () => {
      try {
        const status = await api.getModelStatus();
        setModelStatus(status);
      } catch {
        // Transient backend unavailability
      }
    }, 8000);

    return () => window.clearInterval(interval);
  }, []);

  const handleModelChange = async (modelName: string) => {
    if (!modelName || modelStatus?.active_model === modelName) return;
    setModelLoading(true);
    try {
      const nextStatus = await api.loadModel(modelName);
      setModelStatus(nextStatus);
    } catch (err) {
      console.error('Failed to switch model:', err);
      toastError('Unable to switch model. Please check backend logs.');
    } finally {
      setModelLoading(false);
    }
  };

  const handleDeleteCurrentProject = async () => {
    const confirmed = window.confirm(`Delete project "${currentProject?.name}"? This cannot be undone.`);
    if (!confirmed || !currentProject) return;

    setDeletingProject(true);
    try {
      await api.deleteProject(currentProject.id);
      setActiveProject(null);
      router.replace('/');
      router.refresh();
    } catch (err) {
      console.error('Failed to delete current project:', err);
      toastError('Unable to delete project. Please check backend logs.');
    } finally {
      setDeletingProject(false);
    }
  };

  const handleIngestionComplete = useCallback(() => {
    refreshGraph();
  }, [refreshGraph]);

  const handleFileSelect = (docId: string, filename: string) => {
    setSelectedDocId(docId);
    setSelectedFilename(filename);
    setPdfPage(1);
    setActiveView('document');
  };

  const handleCitationClick = (filename: string, page: number, docId?: string) => {
    if (docId) {
      setSelectedDocId(docId);
      setSelectedFilename(filename);
    }
    setPdfPage(page);
    setActiveView('document');
  };

  const handleAskAboutPage = (question: string) => {
    setActiveView('chat');
    // Pre-fill the chat with the question — the chat component reads from the store
    useChatStore.getState().setPendingQuestion(question);
  };

  const handleUploadClick = () => {
    // Trigger file input in LibrarySidebar
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    input?.click();
  };

  const handleExport = async (type: 'bibtex' | 'markdown' | 'chat') => {
    // Placeholder for Phase 6D - will be implemented with full export functionality
    console.log('Export:', type);
  };

  const handleViewSwitch = (view: MainView) => {
    setActiveView(view);
  };

  // ---------- Loading / Error States ----------

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
            <Zap className="absolute inset-0 m-auto h-4 w-4 text-primary" />
          </div>
          <p className="text-sm text-muted-foreground">Loading workspace...</p>
        </div>
      </div>
    );
  }

  if (!projectId || !currentProject) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <p className="text-sm text-muted-foreground">Project not found.</p>
          <button
            onClick={() => router.push('/')}
            className="rounded-lg border border-border bg-surface px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:border-primary/30"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ---------- Main Workspace ----------

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      {/* ========== Header ========== */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card/80 backdrop-blur-sm px-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/')}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-muted-foreground transition-colors hover:bg-primary/10 hover:border-primary/30 hover:text-primary"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2.5">
            <div className="h-2 w-2 rounded-full bg-primary glow-sm" />
            <div>
              <p className="font-serif text-base leading-none text-foreground">{currentProject.name}</p>
              <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Research Workspace</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status Bar Metrics */}
          <div className="flex items-center gap-3 text-xs text-muted-foreground border-r border-border pr-3">
            <div className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5" />
              <span>{useGraphStore.getState().nodes.length} nodes</span>
            </div>
            {modelStatus?.device && (
              <div className="flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5 text-accent" />
                <span>{modelStatus.device.toUpperCase()}</span>
              </div>
            )}
          </div>

          {/* Model Selector */}
          <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Model</label>
          <select
            value={modelStatus?.active_model || ''}
            onChange={(event) => handleModelChange(event.target.value)}
            disabled={modelLoading || llmModels.length === 0}
            className="h-8 min-w-[200px] rounded-lg border border-border bg-surface px-2.5 text-xs text-foreground outline-none transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/25 disabled:opacity-60"
          >
            {llmModels.length === 0 && <option value="">No models found</option>}
            {llmModels.map((modelName) => (
              <option key={modelName} value={modelName}>
                {modelName}
              </option>
            ))}
          </select>

          <div className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-xs text-muted-foreground">
            {modelLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
            ) : (
              <Cpu className="h-3.5 w-3.5" />
            )}
            <span>{(modelStatus?.device || 'unknown').toUpperCase()}</span>
          </div>
        </div>
      </header>

      {/* ========== Three-Pane Layout ========== */}
      <PanelGroup direction="horizontal" className="min-h-0 flex-1">
        {/* ---- Left: Library Sidebar ---- */}
        <Panel defaultSize={18} minSize={14} maxSize={26} className="border-r border-border bg-card">
          <div className="flex h-full flex-col">
            <div className="min-h-0 flex-1 overflow-hidden">
              <LibrarySidebar
                onFileSelect={handleFileSelect}
                selectedDocId={selectedDocId}
                projectId={currentProject.id}
                onIngestionComplete={handleIngestionComplete}
              />
            </div>
            {/* Project Actions */}
            <div className="shrink-0 border-t border-border p-3 space-y-1.5">
              <button
                onClick={handleDeleteCurrentProject}
                disabled={deletingProject}
                className="inline-flex h-8 w-full items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-xs text-muted-foreground transition-colors hover:bg-destructive/10 hover:border-destructive/30 hover:text-destructive disabled:opacity-50"
              >
                {deletingProject ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                Delete Project
              </button>
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="resize-handle" />

        {/* ---- Center: Main Stage ---- */}
        <Panel defaultSize={contextCollapsed ? 60 : 52} minSize={35}>
          <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
            {/* Tab Bar */}
            <div className="flex shrink-0 items-center gap-1 border-b border-border bg-card/50 px-3 py-1.5">
              {VIEW_TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeView === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveView(tab.key)}
                    className={`relative inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'text-muted-foreground hover:text-foreground hover:bg-surface border border-transparent'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Content Area */}
            <div id="atlas-main-stage" className="relative min-h-0 flex-1 overflow-hidden">
              {/* Document View */}
              {activeView === 'document' && (
                selectedDocId && selectedFilename ? (
                  <PDFViewer
                    fileUrl={api.getFileUrl(selectedDocId)}
                    filename={selectedFilename}
                    docId={selectedDocId}
                    projectId={currentProject.id}
                    initialPage={pdfPage}
                    onAskAboutPage={handleAskAboutPage}
                    onRelatedPassageClick={handleCitationClick}
                  />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                    <div className="rounded-2xl bg-primary/5 p-6 mb-4">
                      <FileText className="h-10 w-10 text-primary/40" />
                    </div>
                    <p className="font-serif text-lg text-foreground/60">No document selected</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Select a document from the library to start reading
                    </p>
                  </div>
                )
              )}

              {/* Editor View */}
              {activeView === 'editor' && <EditorPane projectId={currentProject.id} />}

              {/* Knowledge Graph View */}
              {activeView === 'graph' && (
                <KnowledgeGraph
                  height={centerDimensions.height}
                  width={centerDimensions.width}
                  projectId={currentProject.id}
                  documentId={selectedDocId || undefined}
                />
              )}

              {/* Deep Chat View */}
              {activeView === 'chat' && (
                <div className="h-full max-h-full overflow-hidden">
                  <DualAgentChat
                    onCitationClick={handleCitationClick}
                    projectId={currentProject.id}
                    chatMode={chatMode}
                    onChatModeChange={setChatMode}
                  />
                </div>
              )}
            </div>
          </div>
        </Panel>

        {/* ---- Right: Context Engine ---- */}
        {!contextCollapsed && <PanelResizeHandle className="resize-handle" />}

        {!contextCollapsed && (
          <Panel defaultSize={22} minSize={18} maxSize={32} className="border-l border-border bg-card">
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Context Engine
                  </span>
                </div>
                <button
                  onClick={() => setContextCollapsed(true)}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
                >
                  <ChevronsRight className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">
                <ContextEngine
                  projectId={currentProject.id}
                  selectedDocId={selectedDocId}
                  selectedFilename={selectedFilename}
                  onCitationClick={handleCitationClick}
                />
              </div>
            </div>
          </Panel>
        )}

        {contextCollapsed && (
          <div className="flex w-10 shrink-0 items-start justify-center border-l border-border bg-card pt-3">
            <button
              onClick={() => setContextCollapsed(false)}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
              title="Show Context Engine"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </PanelGroup>

      {/* OmniBar - Global Command Palette */}
      <OmniBar
        projectId={currentProject.id}
        onUpload={handleUploadClick}
        onExport={handleExport}
        onSwitchView={handleViewSwitch}
      />
    </main>
  );
}
