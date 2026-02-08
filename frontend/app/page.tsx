'use client';

import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import FileSidebar from '@/components/FileSidebar';
import ChatInterface from '@/components/ChatInterface';
import PDFViewer from '@/components/PDFViewer';
import GraphCanvas from '@/components/GraphCanvas';
import { api, ProjectInfo } from '@/lib/api';
import { FileText, Network, FolderKanban, BookOpen, Brain, Plus, Trash2 } from 'lucide-react';

// ============================================================
// PROJECT CONTEXT
// ============================================================

interface ProjectContextValue {
  currentProject: ProjectInfo | null;
  setCurrentProject: (p: ProjectInfo | null) => void;
}

const ProjectContext = createContext<ProjectContextValue>({
  currentProject: null,
  setCurrentProject: () => {},
});

function useProject() {
  return useContext(ProjectContext);
}

// ============================================================
// SIDEBAR NAV TABS
// ============================================================

type SidebarTab = 'projects' | 'librarian' | 'cortex';

// ============================================================
// MAIN PAGE
// ============================================================

export default function Home() {
  // Project state
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectInfo | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);

  // Sidebar tab
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('projects');

  // Document viewer state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'document' | 'graph'>('document');
  const [pdfPage, setPdfPage] = useState<number>(1);
  const [centerDimensions, setCenterDimensions] = useState({ width: 800, height: 600 });

  // Chat mode
  const [chatMode, setChatMode] = useState<'librarian' | 'cortex'>('librarian');

  // Load projects
  const loadProjects = useCallback(async () => {
    try {
      const list = await api.listProjects();
      setProjects(list);
    } catch (e) {
      console.error('Failed to load projects:', e);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Create project
  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    try {
      const project = await api.createProject(newProjectName.trim());
      setProjects((prev) => [project, ...prev]);
      setCurrentProject(project);
      setNewProjectName('');
      setSidebarTab('librarian');
    } catch (e: any) {
      alert(e.message || 'Failed to create project');
    } finally {
      setCreatingProject(false);
    }
  };

  // Delete project
  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('Delete this project and all its data?')) return;
    try {
      await api.deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      if (currentProject?.id === projectId) {
        setCurrentProject(null);
        setSidebarTab('projects');
      }
    } catch (e: any) {
      alert(e.message || 'Failed to delete project');
    }
  };

  // Citation handler
  const handleCitationClick = (filename: string, page: number, docId?: string) => {
    if (docId) {
      setSelectedDocId(docId);
      setSelectedFilename(filename);
    }
    setPdfPage(page);
    setActiveView('document');
  };

  const handleFileSelect = (docId: string, filename: string) => {
    setSelectedDocId(docId);
    setSelectedFilename(filename);
    setPdfPage(1);
    setActiveView('document');
  };

  // Resize observer
  useEffect(() => {
    const updateDimensions = () => {
      const centerPanel = document.getElementById('center-panel');
      if (centerPanel) {
        setCenterDimensions({
          width: centerPanel.clientWidth,
          height: centerPanel.clientHeight,
        });
      }
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  return (
    <ProjectContext.Provider value={{ currentProject, setCurrentProject }}>
      <main className="h-screen w-screen overflow-hidden bg-gray-950">
        <PanelGroup direction="horizontal">
          {/* ===================== LEFT SIDEBAR ===================== */}
          <Panel defaultSize={22} minSize={16} maxSize={32}>
            <div className="h-full flex flex-col bg-gray-900 border-r border-gray-800">
              {/* Nav tabs */}
              <div className="flex border-b border-gray-800">
                <button
                  onClick={() => setSidebarTab('projects')}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-3 text-xs font-medium transition-colors ${
                    sidebarTab === 'projects'
                      ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  <FolderKanban className="h-3.5 w-3.5" />
                  Projects
                </button>
                <button
                  onClick={() => {
                    if (!currentProject) return;
                    setSidebarTab('librarian');
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-3 text-xs font-medium transition-colors ${
                    sidebarTab === 'librarian'
                      ? 'bg-gray-800 text-emerald-400 border-b-2 border-emerald-400'
                      : currentProject
                      ? 'text-gray-500 hover:text-gray-300'
                      : 'text-gray-700 cursor-not-allowed'
                  }`}
                >
                  <BookOpen className="h-3.5 w-3.5" />
                  Data
                </button>
                <button
                  onClick={() => {
                    if (!currentProject) return;
                    setSidebarTab('cortex');
                    setChatMode('cortex');
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-3 text-xs font-medium transition-colors ${
                    sidebarTab === 'cortex'
                      ? 'bg-gray-800 text-purple-400 border-b-2 border-purple-400'
                      : currentProject
                      ? 'text-gray-500 hover:text-gray-300'
                      : 'text-gray-700 cursor-not-allowed'
                  }`}
                >
                  <Brain className="h-3.5 w-3.5" />
                  Cortex
                </button>
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-y-auto">
                {sidebarTab === 'projects' && (
                  <div className="p-4 space-y-4">
                    {/* Create project */}
                    <div className="space-y-2">
                      <h2 className="text-sm font-semibold text-gray-300">Research Projects</h2>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={newProjectName}
                          onChange={(e) => setNewProjectName(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                          placeholder="New project name..."
                          className="flex-1 px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-md text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                        <button
                          onClick={handleCreateProject}
                          disabled={creatingProject || !newProjectName.trim()}
                          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 transition-colors"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Project list */}
                    <div className="space-y-2">
                      {projects.length === 0 ? (
                        <p className="text-xs text-gray-600 text-center py-6">
                          No projects yet. Create one to get started.
                        </p>
                      ) : (
                        projects.map((project) => (
                          <div
                            key={project.id}
                            onClick={() => {
                              setCurrentProject(project);
                              setSidebarTab('librarian');
                              setChatMode('librarian');
                            }}
                            className={`group p-3 rounded-lg border cursor-pointer transition-all ${
                              currentProject?.id === project.id
                                ? 'bg-blue-900/30 border-blue-700'
                                : 'bg-gray-800/50 border-gray-700/50 hover:border-gray-600'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-200 truncate">
                                  {project.name}
                                </p>
                                {project.description && (
                                  <p className="text-xs text-gray-500 truncate mt-0.5">
                                    {project.description}
                                  </p>
                                )}
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteProject(project.id);
                                }}
                                className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-900/50 rounded transition-all"
                              >
                                <Trash2 className="h-3.5 w-3.5 text-red-400" />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {sidebarTab === 'librarian' && currentProject && (
                  <FileSidebar
                    onFileSelect={handleFileSelect}
                    selectedDocId={selectedDocId}
                    projectId={currentProject.id}
                  />
                )}

                {sidebarTab === 'cortex' && currentProject && (
                  <div className="p-4 space-y-4">
                    <div className="text-center py-8">
                      <Brain className="h-12 w-12 text-purple-400 mx-auto mb-3 opacity-80" />
                      <h3 className="text-sm font-semibold text-gray-300 mb-1">
                        Two-Brain Cortex
                      </h3>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        Ask research questions in the chat panel. The swarm will automatically
                        choose between deep graph navigation or broad map-reduce search.
                      </p>
                    </div>
                    <div className="space-y-3 text-xs">
                      <div className="p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
                        <p className="text-purple-400 font-medium mb-1">Navigator Brain</p>
                        <p className="text-gray-500">
                          Walks the knowledge graph to find hidden connections and generate hypotheses
                          across domains.
                        </p>
                      </div>
                      <div className="p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
                        <p className="text-blue-400 font-medium mb-1">Cortex Brain</p>
                        <p className="text-gray-500">
                          Breaks broad queries into sub-tasks, searches in parallel*, then
                          synthesizes findings. (*sequential on GPU for VRAM safety)
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {!currentProject && sidebarTab !== 'projects' && (
                  <div className="p-4 text-center py-12">
                    <p className="text-xs text-gray-600">
                      Select a project first.
                    </p>
                  </div>
                )}
              </div>

              {/* Current project indicator */}
              {currentProject && (
                <div className="px-4 py-2 border-t border-gray-800 bg-gray-900">
                  <p className="text-xs text-gray-500">
                    Active: <span className="text-gray-300 font-medium">{currentProject.name}</span>
                  </p>
                </div>
              )}
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-gray-800 hover:bg-blue-500 transition-colors" />

          {/* ===================== CENTER PANEL ===================== */}
          <Panel defaultSize={48} minSize={30}>
            <div id="center-panel" className="h-full flex flex-col bg-gray-950">
              {/* View tabs */}
              <div className="flex border-b border-gray-800 bg-gray-900">
                <button
                  onClick={() => setActiveView('document')}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                    activeView === 'document'
                      ? 'bg-gray-950 text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  <FileText className="h-4 w-4" />
                  Document
                </button>
                <button
                  onClick={() => setActiveView('graph')}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                    activeView === 'graph'
                      ? 'bg-gray-950 text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  <Network className="h-4 w-4" />
                  Graph
                </button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-hidden">
                {activeView === 'document' ? (
                  selectedDocId && selectedFilename ? (
                    <PDFViewer
                      fileUrl={api.getFileUrl(selectedDocId)}
                      filename={selectedFilename}
                      initialPage={pdfPage}
                    />
                  ) : (
                    <div className="h-full flex items-center justify-center bg-gray-950">
                      <div className="text-center">
                        <FileText className="h-16 w-16 text-gray-700 mx-auto mb-4" />
                        <p className="text-gray-500 mb-2">No document selected</p>
                        <p className="text-sm text-gray-600">
                          Select a file from the sidebar or click a citation
                        </p>
                      </div>
                    </div>
                  )
                ) : (
                  <GraphCanvas
                    height={centerDimensions.height}
                    width={centerDimensions.width}
                    projectId={currentProject?.id}
                  />
                )}
              </div>
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-gray-800 hover:bg-blue-500 transition-colors" />

          {/* ===================== RIGHT PANEL: CHAT ===================== */}
          <Panel defaultSize={30} minSize={22} maxSize={45}>
            <ChatInterface
              onCitationClick={handleCitationClick}
              projectId={currentProject?.id}
              chatMode={chatMode}
              onChatModeChange={setChatMode}
            />
          </Panel>
        </PanelGroup>
      </main>
    </ProjectContext.Provider>
  );
}
