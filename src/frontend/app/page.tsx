'use client';

import React, { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, usePathname } from 'next/navigation';
import { api, ProjectInfo } from '@/lib/api';
import {
  FolderOpen,
  FolderKanban,
  Search,
  ArrowRight,
  Plus,
  AlertCircle,
  Trash2,
  Loader2,
  Brain,
  Network,
  BookOpen,
  Zap,
  Sparkles,
  Database,
  GitBranch,
  FileText,
  Clock,
  HardDrive,
  Puzzle,
} from 'lucide-react';

const WindowControls = dynamic(
  () => import('@/components/WindowControls').then((m) => ({ default: m.WindowControls })),
  { ssr: false }
);

export default function HomePage() {
  const router = useRouter();
  const pathname = usePathname();
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [navigatingToId, setNavigatingToId] = useState<string | null>(null);
  const [navigatingToName, setNavigatingToName] = useState<string>('');

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    let isMounted = true;

    const loadProjects = async () => {
      try {
        const list = await api.listProjects();
        if (!isMounted) return;
        setProjects(list);
        setError(null);
        setLoading(false);
      } catch (e: any) {
        if (!isMounted) return;
        setError(e.message || 'Failed to connect to backend. Retrying...');
        timeoutId = setTimeout(loadProjects, 3000);
      }
    };

    setLoading(true);
    setError(null);
    loadProjects();

    return () => {
      isMounted = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [pathname]);

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((project) => {
      return (
        project.name.toLowerCase().includes(needle) ||
        project.id.toLowerCase().includes(needle) ||
        (project.description || '').toLowerCase().includes(needle)
      );
    });
  }, [projects, query]);

  const handleOpenFolder = async () => {
    // Try Tauri dialog for native folder picker
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      try {
        const { open } = await import('@tauri-apps/api/dialog');
        const selected = await open({ directory: true, multiple: false, title: 'Open Research Folder' });
        if (!selected || Array.isArray(selected)) return;
        // Use the folder name as the project name
        const folderName = selected.split(/[\\/]/).pop() || selected;
        setCreatingProject(true);
        try {
          const created = await api.createProject(folderName.trim());
          setProjects((previous) => [created, ...previous]);
          setNavigatingToId(created.id);
          setNavigatingToName(created.name);
          router.push(`/project/${encodeURIComponent(created.id)}`);
        } catch (e: any) {
          setCreatingProject(false);
          setNavigatingToId(null);
          setError(e.message || 'Failed to open folder');
        }
      } catch {
        // Fallback if dialog fails
        setShowCreateForm(true);
      }
    } else {
      // Browser fallback — show name input
      setShowCreateForm(true);
    }
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    try {
      const created = await api.createProject(newProjectName.trim());
      setProjects((previous) => [created, ...previous]);
      setNewProjectName('');
      setShowCreateForm(false);
      setNavigatingToId(created.id);
      setNavigatingToName(created.name);
      router.push(`/project/${encodeURIComponent(created.id)}`);
    } catch (e: any) {
      setCreatingProject(false);
      setNavigatingToId(null);
      setError(e.message || 'Failed to create project');
    }
  };

  const handleDeleteProject = async (e: React.MouseEvent, project: ProjectInfo) => {
    e.preventDefault();
    e.stopPropagation();
    const confirmed = window.confirm(`Remove "${project.name}" from recents? This cannot be undone.`);
    if (!confirmed) return;

    setDeletingProjectId(project.id);
    try {
      await api.deleteProject(project.id);
      setProjects((previous) => previous.filter((item) => item.id !== project.id));
    } catch (e: any) {
      setError(e.message || 'Failed to remove project');
    } finally {
      setDeletingProjectId(null);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays === 0) return 'Today';
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays} days ago`;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <main className="min-h-screen bg-background text-foreground selection:bg-accent/20">
      {/* Title Bar */}
      <div data-tauri-drag-region className="relative top-0 right-0 left-0 h-8 flex justify-between px-2 items-center bg-card/80 backdrop-blur-sm z-[100] border-b border-border/40">
        <div className="flex h-full items-center gap-1.5 no-drag select-none text-muted-foreground">
          <div className="flex w-4 h-4 items-center justify-center rounded bg-accent/10 border border-accent/20 ml-2">
            <Zap className="h-3 w-3 text-accent" />
          </div>
          <span className="text-[12px] font-medium tracking-wide">Atlas</span>
        </div>
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-[12px] text-muted-foreground/80 font-medium tracking-wide">
          Dashboard
        </div>
        <div className="h-full shrink-0 no-drag">
          <WindowControls />
        </div>
      </div>

      {/* Hero Section */}
      <div className="border-b border-border/40 bg-card/30 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 pt-14 pb-10 sm:px-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 border border-accent/20">
              <Zap className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground tracking-tight">Atlas Framework</h1>
              <p className="text-xs text-muted-foreground">Local-first research platform</p>
            </div>
          </div>
          <p className="max-w-xl text-[13px] text-muted-foreground leading-relaxed">
            Open a folder to start. Your documents, knowledge graph, and agent sessions are stored together — just like a project directory.
          </p>

          {/* Quick stats row */}
          <div className="flex items-center gap-6 mt-6">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <FolderKanban className="h-3.5 w-3.5 text-accent/70" />
              <span><span className="text-foreground font-medium">{projects.length}</span> projects</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Puzzle className="h-3.5 w-3.5 text-accent/70" />
              <span>Plugin workbench</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <HardDrive className="h-3.5 w-3.5 text-accent/70" />
              <span>Offline-first</span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        {/* Actions Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">Recent Projects</h2>
            <span className="rounded bg-surface px-2 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
              {projects.length}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {projects.length > 0 && (
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Filter projects..."
                  className="h-8 w-56 rounded border border-border/50 bg-background pl-8 pr-3 text-[13px] text-foreground outline-none transition-all placeholder:text-muted-foreground/60 focus:border-accent/50 focus:ring-1 focus:ring-accent/25"
                />
              </div>
            )}
            <button
              onClick={handleOpenFolder}
              className="inline-flex h-8 items-center gap-2 rounded bg-accent px-3 text-[13px] font-medium text-white transition-all hover:bg-accent/90"
            >
              <FolderOpen className="h-3.5 w-3.5" />
              Open Folder
            </button>
          </div>
        </div>

        {/* Create Project Panel (browser fallback) */}
        {showCreateForm && (
          <div className="mb-6 rounded border border-accent/20 bg-accent/5 p-5">
            <h3 className="font-display text-[13px] font-medium text-foreground mb-3">Open Project Folder</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Enter a name for your project. In the desktop app, you can pick a folder directly.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleCreateProject()}
                placeholder="Project name (e.g. CRISPR Pathway Analysis)"
                autoFocus
                className="h-9 flex-1 rounded border border-border/50 bg-background px-3 text-[13px] text-foreground outline-none transition-all placeholder:text-muted-foreground/50 focus:border-accent/50 focus:ring-1 focus:ring-accent/25"
              />
              <button
                onClick={handleCreateProject}
                disabled={creatingProject || !newProjectName.trim()}
                className="inline-flex h-9 items-center gap-2 rounded bg-accent px-4 text-[13px] font-medium text-white transition-all hover:bg-accent/90 disabled:opacity-40"
              >
                {creatingProject ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Create
              </button>
              <button
                onClick={() => { setShowCreateForm(false); setNewProjectName(''); }}
                className="h-9 rounded border border-border/50 px-3 text-[13px] text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 flex items-start gap-3 rounded border border-destructive/30 bg-destructive/5 px-4 py-3 text-[13px] text-destructive">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div className="flex-1">{error}</div>
            <button onClick={() => setError(null)} className="text-destructive/60 hover:text-destructive">
              &times;
            </button>
          </div>
        )}

        {/* Projects Grid */}
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-36 animate-pulse rounded border border-border/40 bg-card/30" />
            ))}
          </div>
        ) : projects.length === 0 && !showCreateForm ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/50 bg-card/10 py-20 px-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 border border-accent/15 mb-5">
              <FolderOpen className="h-7 w-7 text-accent/60" />
            </div>
            <h3 className="font-display text-base font-medium text-foreground mb-1">No Projects Yet</h3>
            <p className="max-w-sm text-[13px] text-muted-foreground leading-relaxed mb-6">
              Open a folder to create your first project. Your documents, knowledge graph, and sessions will live inside it.
            </p>
            <button
              onClick={handleOpenFolder}
              className="inline-flex h-9 items-center gap-2 rounded bg-accent px-4 text-[13px] font-medium text-white transition-all hover:bg-accent/90"
            >
              <FolderOpen className="h-3.5 w-3.5" />
              Open Folder
            </button>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="flex h-36 flex-col items-center justify-center rounded border border-border/40 bg-card/30 text-center">
            <Search className="mb-2 h-5 w-5 text-muted-foreground/40" />
            <p className="text-[13px] text-foreground/70">No matching projects</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredProjects.map((project) => (
              <div
                key={project.id}
                role="button"
                tabIndex={0}
                onClick={() => {
                  setNavigatingToId(project.id);
                  setNavigatingToName(project.name);
                  router.push(`/project/${encodeURIComponent(project.id)}`);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setNavigatingToId(project.id);
                    setNavigatingToName(project.name);
                    router.push(`/project/${encodeURIComponent(project.id)}`);
                  }
                }}
                className={`group relative flex h-36 cursor-pointer flex-col justify-between rounded-lg border border-border/40 bg-card/30 p-5 text-left transition-all hover:border-accent/40 hover:bg-card/50 ${navigatingToId === project.id ? 'border-accent/60 bg-card/60 ring-1 ring-accent/20' : ''
                  }`}
              >
                {/* Delete button */}
                <button
                  type="button"
                  onClick={(event) => handleDeleteProject(event, project)}
                  disabled={deletingProjectId === project.id}
                  className="absolute right-3 top-3 z-10 inline-flex h-6 w-6 items-center justify-center rounded border border-transparent text-muted-foreground/0 transition-all group-hover:border-border/50 group-hover:bg-surface group-hover:text-muted-foreground hover:!bg-destructive/10 hover:!text-destructive hover:!border-destructive/30 disabled:opacity-50"
                  title="Remove from recents"
                >
                  {deletingProjectId === project.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                </button>

                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded bg-accent/10 border border-accent/10">
                      <FolderKanban className="h-3.5 w-3.5 text-accent" />
                    </div>
                    <p className="line-clamp-1 font-display text-[15px] font-medium text-foreground group-hover:text-accent transition-colors">
                      {project.name}
                    </p>
                  </div>
                  <p className="line-clamp-2 text-xs text-muted-foreground leading-relaxed pl-8">
                    {project.description || "No description provided."}
                  </p>
                </div>

                <div className="flex items-center justify-between pl-8">
                  <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/50">
                    <Clock className="h-2.5 w-2.5" />
                    {project.created_at ? formatDate(project.created_at) : ''}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-accent/0 transition-all group-hover:text-accent">
                    Open <ArrowRight className="h-3 w-3" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Navigation loading overlay */}
      {navigatingToId && (
        <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-background/95 backdrop-blur-md animate-in fade-in duration-150">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-accent/5 blur-3xl" />
          </div>

          <div className="relative flex flex-col items-center gap-8">
            <div className="relative flex items-center justify-center">
              <div className="absolute h-20 w-20 rounded-full border border-accent/20 animate-ping" style={{ animationDuration: '2s' }} />
              <div className="absolute h-16 w-16 rounded-full border border-accent/30" />
              <div className="h-14 w-14 rounded-full border-2 border-accent/10 border-t-accent animate-spin" style={{ animationDuration: '0.9s' }} />
              <div className="absolute flex items-center justify-center">
                <Zap className="h-5 w-5 text-accent" />
              </div>
            </div>

            <div className="flex flex-col items-center gap-2 text-center">
              <p className="text-[13px] font-medium text-foreground tracking-wide">
                Opening <span className="text-accent">{navigatingToName}</span>
              </p>
              <p className="text-[11px] text-muted-foreground/60">Loading project environment...</p>
            </div>

            <div className="flex items-center gap-6">
              {[
                { icon: Database, label: 'Library' },
                { icon: GitBranch, label: 'Graph' },
                { icon: Brain, label: 'Orchestrator' },
              ].map(({ icon: Icon, label }, i) => (
                <div
                  key={label}
                  className="flex flex-col items-center gap-1.5 opacity-0 animate-in fade-in duration-300"
                  style={{ animationDelay: `${150 + i * 120}ms`, animationFillMode: 'forwards' }}
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/40 bg-card/50">
                    <Icon className="h-3.5 w-3.5 text-accent/70" />
                  </div>
                  <span className="text-[10px] text-muted-foreground/50 tracking-wider uppercase">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
