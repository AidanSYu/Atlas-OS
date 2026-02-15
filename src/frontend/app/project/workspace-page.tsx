'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import FileSidebar from '@/components/FileSidebar';
import PDFViewer from '@/components/PDFViewer';
import KnowledgeGraph from '@/components/KnowledgeGraph';
import ChatInterface from '@/components/ChatInterface';
import { api, ModelStatusResponse, ProjectInfo } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import {
  FileText,
  ChevronLeft,
  MessageSquare,
  Network,
  BookOpen,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  Circle,
  Cpu,
  Loader2,
  Trash2
} from 'lucide-react';

type MainView = 'document' | 'graph' | 'chat';
type InspectorTab = 'citations' | 'details' | 'quick-chat';

export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = decodeURIComponent(params.id || '');

  const { setActiveProject } = useChatStore();

  const [currentProject, setCurrentProject] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [activeView, setActiveView] = useState<MainView>('document');
  const [chatMode, setChatMode] = useState<'librarian' | 'cortex'>('librarian');

  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('details');
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatusResponse | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [deletingProject, setDeletingProject] = useState(false);

  const [centerDimensions, setCenterDimensions] = useState({ width: 800, height: 600 });

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

  useEffect(() => {
    return () => {
      setActiveProject(null);
    };
  }, [setActiveProject]);

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
        // No-op: transient backend unavailability should not spam UI.
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
      alert('Unable to switch model. Please check backend logs.');
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
      alert('Unable to delete project. Please check backend logs.');
    } finally {
      setDeletingProject(false);
    }
  };

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

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="text-sm">Loading workspace…</p>
        </div>
      </div>
    );
  }

  if (!projectId || !currentProject) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm">Project not found.</p>
          <button
            onClick={() => router.push('/')}
            className="h-9 border border-border bg-surface px-4 text-xs font-medium text-foreground transition-colors hover:bg-accent/15"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/')}
            className="inline-flex h-8 w-8 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div>
            <p className="font-serif text-base leading-none text-foreground">{currentProject.name}</p>
            <p className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Workspace</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground">Model</label>
          <select
            value={modelStatus?.active_model || ''}
            onChange={(event) => handleModelChange(event.target.value)}
            disabled={modelLoading || llmModels.length === 0}
            className="h-8 min-w-[200px] border border-border bg-surface px-2 text-xs text-foreground outline-none disabled:opacity-60"
          >
            {llmModels.length === 0 && <option value="">No models found</option>}
            {llmModels.map((modelName) => (
              <option key={modelName} value={modelName}>
                {modelName}
              </option>
            ))}
          </select>

          <div className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-2 text-xs text-muted-foreground">
            {modelLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Cpu className="h-3.5 w-3.5" />}
            <span>{(modelStatus?.device || 'unknown').toUpperCase()}</span>
          </div>
        </div>
      </header>

      <PanelGroup direction="horizontal" className="min-h-0 flex-1">
        <Panel defaultSize={19} minSize={15} maxSize={28} className="border-r border-border bg-card">
          <div className="flex h-full flex-col">
            <div className="border-b border-border px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Project Files</p>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              <FileSidebar
                onFileSelect={handleFileSelect}
                selectedDocId={selectedDocId}
                projectId={currentProject.id}
              />
            </div>
            <div className="border-t border-border px-3 py-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Settings</p>
              <button className="inline-flex h-8 w-full items-center gap-2 border border-border bg-background px-2 text-xs text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground">
                <Settings className="h-3.5 w-3.5" />
                Project Preferences
              </button>
              <button
                onClick={handleDeleteCurrentProject}
                disabled={deletingProject}
                className="mt-2 inline-flex h-8 w-full items-center gap-2 border border-border bg-background px-2 text-xs text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive disabled:opacity-50"
              >
                {deletingProject ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                Delete Project
              </button>
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-px bg-border" />

        <Panel defaultSize={56} minSize={35}>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
            <div className="flex shrink-0 border-b border-border bg-card px-3 py-2">
              <div className="inline-flex border border-border bg-surface">
                <button
                  onClick={() => setActiveView('document')}
                  className={`inline-flex h-8 items-center gap-1.5 border-r border-border px-3 text-xs font-medium ${
                    activeView === 'document' ? 'bg-background text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <BookOpen className="h-3.5 w-3.5" />
                  PDF Reader
                </button>
                <button
                  onClick={() => setActiveView('graph')}
                  className={`inline-flex h-8 items-center gap-1.5 border-r border-border px-3 text-xs font-medium ${
                    activeView === 'graph' ? 'bg-background text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Network className="h-3.5 w-3.5" />
                  Knowledge Graph
                </button>
                <button
                  onClick={() => setActiveView('chat')}
                  className={`inline-flex h-8 items-center gap-1.5 px-3 text-xs font-medium ${
                    activeView === 'chat' ? 'bg-background text-foreground' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  Deep Chat
                </button>
              </div>
            </div>

            <div id="atlas-main-stage" className="relative min-h-0 flex-1 overflow-hidden">
              {activeView === 'document' && (
                selectedDocId && selectedFilename ? (
                  <PDFViewer
                    fileUrl={api.getFileUrl(selectedDocId)}
                    filename={selectedFilename}
                    initialPage={pdfPage}
                  />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                    <FileText className="mb-2 h-10 w-10" />
                    <p className="text-sm">Select a document from the file tree.</p>
                  </div>
                )
              )}

              {activeView === 'graph' && (
                <KnowledgeGraph
                  height={centerDimensions.height}
                  width={centerDimensions.width}
                  projectId={currentProject.id}
                  documentId={selectedDocId || undefined}
                />
              )}

              {activeView === 'chat' && (
                <div className="h-full max-h-full overflow-hidden">
                  <ChatInterface
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

        {!inspectorCollapsed && <PanelResizeHandle className="w-px bg-border" />}

        {!inspectorCollapsed && (
          <Panel defaultSize={25} minSize={20} maxSize={35} className="border-l border-border bg-card">
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-border px-2 py-2">
                <div className="inline-flex border border-border bg-surface">
                  <button
                    onClick={() => setInspectorTab('citations')}
                    className={`h-7 px-2 text-[11px] ${inspectorTab === 'citations' ? 'bg-background text-foreground' : 'text-muted-foreground'}`}
                  >
                    Citations
                  </button>
                  <button
                    onClick={() => setInspectorTab('details')}
                    className={`h-7 border-x border-border px-2 text-[11px] ${inspectorTab === 'details' ? 'bg-background text-foreground' : 'text-muted-foreground'}`}
                  >
                    Node Details
                  </button>
                  <button
                    onClick={() => setInspectorTab('quick-chat')}
                    className={`h-7 px-2 text-[11px] ${inspectorTab === 'quick-chat' ? 'bg-background text-foreground' : 'text-muted-foreground'}`}
                  >
                    Quick Chat
                  </button>
                </div>
                <button
                  onClick={() => setInspectorCollapsed(true)}
                  className="inline-flex h-7 w-7 items-center justify-center border border-border text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
                >
                  <ChevronsRight className="h-3.5 w-3.5" />
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {inspectorTab === 'citations' && (
                  <div className="space-y-2 text-xs text-muted-foreground">
                    <p className="font-semibold uppercase tracking-[0.12em]">Citation Context</p>
                    <p>Citations will appear here as you explore documents and chat responses.</p>
                  </div>
                )}

                {inspectorTab === 'details' && (
                  <div className="space-y-2 text-xs text-muted-foreground">
                    <p className="font-semibold uppercase tracking-[0.12em]">Selection Details</p>
                    {selectedFilename ? (
                      <div className="border border-border bg-background p-2">
                        <p className="text-[11px] uppercase tracking-[0.1em]">Active Document</p>
                        <p className="mt-1 text-foreground">{selectedFilename}</p>
                      </div>
                    ) : (
                      <p>No document selected.</p>
                    )}
                  </div>
                )}

                {inspectorTab === 'quick-chat' && (
                  <div className="space-y-2 text-xs text-muted-foreground">
                    <p className="font-semibold uppercase tracking-[0.12em]">Quick Chat</p>
                    <p>Open the Deep Chat tab for full session history and citation actions.</p>
                    <div className="border border-border bg-background p-3 text-[11px]">
                      <div className="mb-2 flex items-center gap-1.5 text-foreground">
                        <Circle className="h-2 w-2 fill-current" />
                        {chatMode === 'cortex' ? 'Cortex mode active' : 'Librarian mode active'}
                      </div>
                      <p className="text-muted-foreground">Mode can be changed from the Deep Chat stage.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </Panel>
        )}

        {inspectorCollapsed && (
          <div className="flex w-10 items-start justify-center border-l border-border bg-card pt-3">
            <button
              onClick={() => setInspectorCollapsed(false)}
              className="inline-flex h-7 w-7 items-center justify-center border border-border text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </PanelGroup>
    </main>
  );
}
