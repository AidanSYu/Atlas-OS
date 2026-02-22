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
import { ResearchCanvas } from '@/components/ResearchCanvas';
import { WelcomeTour } from '@/components/WelcomeTour';
import { api, ModelStatusResponse, ModelRegistryResponse, ProjectInfo } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useGraphStore } from '@/stores/graphStore';
import { toastError, toast, toastSuccess } from '@/stores/toastStore';
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
  Download,
  ChevronDown,
  FileCode,
  Layers,
  Settings,
} from 'lucide-react';

import SettingsModal from '@/components/SettingsModal';

type MainView = 'document' | 'editor' | 'graph' | 'chat' | 'canvas';

const VIEW_TABS: { key: MainView; label: string; icon: typeof FileText }[] = [
  { key: 'document', label: 'Documents', icon: BookOpen },
  { key: 'editor', label: 'Editor', icon: PenTool },
  { key: 'graph', label: 'Graph', icon: Network },
  { key: 'chat', label: 'Deep Chat', icon: MessageSquare },
  { key: 'canvas', label: 'Canvas', icon: Layers },
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
  const [chatMode, setChatMode] = useState<'librarian' | 'cortex' | 'moe'>('librarian');

  const [contextCollapsed, setContextCollapsed] = useState(false);
  const [modelRegistry, setModelRegistry] = useState<ModelRegistryResponse | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatusResponse | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [deletingProject, setDeletingProject] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

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

  // Load model controls (registry = local + cloud API models)
  useEffect(() => {
    const loadModelControls = async () => {
      try {
        const registry = await api.getModelRegistry();
        setModelRegistry(registry);
        setModelStatus(registry.active);
      } catch (err) {
        console.error('Failed to load model controls:', err);
      }
    };

    loadModelControls();

    const interval = window.setInterval(async () => {
      try {
        const registry = await api.getModelRegistry();
        setModelRegistry(registry);
        setModelStatus(registry.active);
      } catch {
        // Transient backend unavailability
      }
    }, 8000);

    return () => window.clearInterval(interval);
  }, []);

  // Close export menu on outside click
  useEffect(() => {
    if (!exportMenuOpen) return;
    const handleClick = () => setExportMenuOpen(false);
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [exportMenuOpen]);

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

  const handleFileDeleted = useCallback((docId: string) => {
    if (docId === selectedDocId) {
      setSelectedDocId(null);
      setSelectedFilename(null);
    }
  }, [selectedDocId]);

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
    try {
      toast(`Exporting ${type}...`, 'info');

      if (type === 'bibtex') {
        const blob = await api.exportBibtexProject(projectId);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentProject?.name || 'atlas-project'}.bib`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toastSuccess('BibTeX export complete');
      } else if (type === 'markdown') {
        // Get editor content from localStorage or EditorPane
        const editorContent = localStorage.getItem(`atlas-editor-${projectId}`) || '';
        if (!editorContent.trim()) {
          toastError('No editor content to export');
          return;
        }

        const result = await api.exportMarkdown({
          content: editorContent,
          citations: [],
          projectId: projectId,
          title: currentProject?.name || 'Research Synthesis',
          author: 'Atlas User',
          style: 'apa',
        });

        // Download the markdown file
        const blob = new Blob([result.markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = result.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toastSuccess('Markdown export complete');
      } else if (type === 'chat') {
        const cortexMessages = useChatStore.getState().cortexMessages;
        const librarianMessages = useChatStore.getState().librarianMessages;
        const allMessages = [...cortexMessages, ...librarianMessages].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        if (allMessages.length === 0) {
          toastError('No chat history to export');
          return;
        }

        const result = await api.exportChatHistory(allMessages, currentProject?.name);

        const blob = new Blob([result.markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentProject?.name || 'chat'}-history.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toastSuccess('Chat history exported');
      }
    } catch (error: any) {
      toastError(`Export failed: ${error.message}`);
    }
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

          {/* Model Selector (Local + Cloud API from registry) */}
          <label className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Model</label>
          <select
            value={modelStatus?.active_model || ''}
            onChange={(event) => handleModelChange(event.target.value)}
            disabled={modelLoading || ((modelRegistry?.local?.length ?? 0) + (modelRegistry?.api?.length ?? 0)) === 0}
            className="h-8 min-w-[200px] rounded-lg border border-border bg-surface px-2.5 text-xs text-foreground outline-none transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/25 disabled:opacity-60"
          >
            {((modelRegistry?.local?.length ?? 0) + (modelRegistry?.api?.length ?? 0)) === 0 && (
              <option value="">No models found</option>
            )}
            {modelRegistry?.local && modelRegistry.local.length > 0 && (
              <optgroup label="Local">
                {modelRegistry.local.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name}
                  </option>
                ))}
              </optgroup>
            )}
            {modelRegistry?.api && modelRegistry.api.length > 0 && (
              <optgroup label="Cloud API">
                {modelRegistry.api.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name}{m.has_key === false ? ' (no API key)' : ''}
                  </option>
                ))}
              </optgroup>
            )}
          </select>

          <div className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-xs text-muted-foreground">
            {modelLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
            ) : (
              <Cpu className="h-3.5 w-3.5" />
            )}
            <span>{(modelStatus?.device || 'unknown').toUpperCase()}</span>
          </div>

          {/* Settings Button */}
          <button
            onClick={() => setSettingsOpen(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-muted-foreground transition-colors hover:bg-primary/10 hover:border-primary/30 hover:text-primary ml-2"
            title="Configure API Keys"
          >
            <Settings className="h-4 w-4" />
          </button>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExportMenuOpen(!exportMenuOpen);
              }}
              className="flex h-8 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-xs text-foreground transition-colors hover:bg-surface/80 hover:border-primary/30"
            >
              <Download className="h-3.5 w-3.5" />
              Export
              <ChevronDown className={`h-3 w-3 transition-transform ${exportMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-52 rounded-lg border border-border bg-card shadow-xl z-50 overflow-hidden">
                <div className="p-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleExport('bibtex');
                      setExportMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 text-xs text-foreground hover:bg-primary/10 transition-colors"
                  >
                    <FileCode className="h-4 w-4 text-primary" />
                    <div className="flex-1 text-left">
                      <div className="font-medium">BibTeX</div>
                      <div className="text-[10px] text-muted-foreground">Bibliography file (.bib)</div>
                    </div>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleExport('markdown');
                      setExportMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 text-xs text-foreground hover:bg-primary/10 transition-colors"
                  >
                    <FileText className="h-4 w-4 text-accent" />
                    <div className="flex-1 text-left">
                      <div className="font-medium">Markdown</div>
                      <div className="text-[10px] text-muted-foreground">Editor content (.md)</div>
                    </div>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleExport('chat');
                      setExportMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 text-xs text-foreground hover:bg-primary/10 transition-colors"
                  >
                    <MessageSquare className="h-4 w-4 text-success" />
                    <div className="flex-1 text-left">
                      <div className="font-medium">Chat History</div>
                      <div className="text-[10px] text-muted-foreground">Conversation log (.md)</div>
                    </div>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ========== Three-Pane Layout ========== */}
      <PanelGroup direction="horizontal" className="min-h-0 flex-1">
        {/* ---- Left: Library Sidebar ---- */}
        <Panel defaultSize={18} minSize={14} maxSize={26} className="border-r border-border bg-card">
          <div id="atlas-library-sidebar" className="flex h-full flex-col">
            <div className="min-h-0 flex-1 overflow-hidden">
              <LibrarySidebar
                onFileSelect={handleFileSelect}
                selectedDocId={selectedDocId}
                projectId={currentProject.id}
                onIngestionComplete={handleIngestionComplete}
                onFileDeleted={handleFileDeleted}
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
            <div id="atlas-view-tabs" className="flex shrink-0 items-center gap-1 border-b border-border bg-card/50 px-3 py-1.5">
              {VIEW_TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeView === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveView(tab.key)}
                    className={`relative inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${isActive
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

              {/* Research Canvas View */}
              {activeView === 'canvas' && <ResearchCanvas projectId={currentProject.id} />}
            </div>
          </div>
        </Panel>

        {/* ---- Right: Context Engine ---- */}
        {!contextCollapsed && <PanelResizeHandle className="resize-handle" />}

        {!contextCollapsed && (
          <Panel defaultSize={22} minSize={18} maxSize={32} className="border-l border-border bg-card">
            <div id="atlas-context-engine" className="flex h-full flex-col">
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

      {/* Welcome Tour - First-time onboarding */}
      <WelcomeTour />

      {/* Settings Modal */}
      <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} />
    </main>
  );
}
