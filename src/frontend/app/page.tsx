'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api, ProjectInfo } from '@/lib/api';
import {
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
} from 'lucide-react';

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

  useEffect(() => {
    const loadProjects = async () => {
      setLoading(true);
      setError(null);
      try {
        const list = await api.listProjects();
        setProjects(list);
      } catch (e: any) {
        setError(e.message || 'Failed to load projects');
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
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

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    try {
      const created = await api.createProject(newProjectName.trim());
      setProjects((previous) => [created, ...previous]);
      setNewProjectName('');
      setShowCreateForm(false);
      router.push(`/project/${encodeURIComponent(created.id)}`);
    } catch (e: any) {
      setError(e.message || 'Failed to create project');
    } finally {
      setCreatingProject(false);
    }
  };

  const handleDeleteProject = async (e: React.MouseEvent, project: ProjectInfo) => {
    e.preventDefault();
    e.stopPropagation();
    const confirmed = window.confirm(`Delete project "${project.name}"? This cannot be undone.`);
    if (!confirmed) return;

    setDeletingProjectId(project.id);
    try {
      await api.deleteProject(project.id);
      setProjects((previous) => previous.filter((item) => item.id !== project.id));
    } catch (e: any) {
      setError(e.message || 'Failed to delete project');
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
    <main className="min-h-screen bg-background text-foreground selection:bg-primary/30">
      {/* Refined Header Section */}
      <div className="border-b border-border/40 bg-card/30 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 pt-16 pb-12 sm:px-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-safety/10 border border-safety/20">
              <Zap className="h-4 w-4 text-safety" />
            </div>
            <h1 className="font-display text-3xl font-medium tracking-tight text-white">Atlas</h1>
          </div>
          <p className="max-w-xl text-[13px] text-text-secondary leading-relaxed">
            Spatial Research Platform. Upload papers, trace relationships through dynamic knowledge graphs, and leverage autonomous agents for deep literature synthesis.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        {/* Actions Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-text-secondary">Workspaces</h2>
            <span className="rounded bg-surface px-2 py-0.5 text-[10px] font-mono font-medium text-text-secondary">
              {projects.length}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {projects.length > 0 && (
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Filter workspaces..."
                  className="h-8 w-56 rounded border border-border/50 bg-background pl-8 pr-3 text-[13px] text-text-primary outline-none transition-all placeholder:text-text-secondary/60 focus:border-safety/50 focus:ring-1 focus:ring-safety/25"
                />
              </div>
            )}
            <button
              onClick={() => setShowCreateForm(true)}
              className="inline-flex h-8 items-center gap-2 rounded bg-safety px-3 text-[13px] font-medium text-white transition-all hover:bg-safety/90"
            >
              <Plus className="h-3.5 w-3.5" />
              New Workspace
            </button>
          </div>
        </div>

        {/* Create Project Panel */}
        {showCreateForm && (
          <div className="mb-8 rounded border border-border/50 bg-card/50 p-5">
            <h3 className="font-display text-[13px] font-medium text-text-primary mb-3">Initialize Workspace</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleCreateProject()}
                placeholder="Workspace Name (e.g. CRISPR Pathway Analysis)"
                autoFocus
                className="h-9 flex-1 rounded border border-border/50 bg-background px-3 text-[13px] text-text-primary outline-none transition-all placeholder:text-text-secondary/50 focus:border-safety/50 focus:ring-1 focus:ring-safety/25"
              />
              <button
                onClick={handleCreateProject}
                disabled={creatingProject || !newProjectName.trim()}
                className="inline-flex h-9 items-center gap-2 rounded bg-safety px-4 text-[13px] font-medium text-white transition-all hover:bg-safety/90 disabled:opacity-40"
              >
                {creatingProject ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Create
              </button>
              <button
                onClick={() => { setShowCreateForm(false); setNewProjectName(''); }}
                className="h-9 rounded border border-border/50 px-3 text-[13px] text-text-secondary transition-colors hover:bg-surface hover:text-text-primary"
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
          <div className="flex flex-col items-center justify-center rounded border border-dashed border-border/50 bg-card/10 py-16 px-8 text-center">
            <FolderKanban className="h-8 w-8 text-text-secondary/30 mb-4" />
            <h3 className="font-display text-sm font-medium text-text-primary mb-1">No Active Workspaces</h3>
            <p className="max-w-sm text-[13px] text-text-secondary leading-relaxed mb-6">
              Create a workspace to isolate your current documents, knowledge graph, and AI agent sessions.
            </p>
            <button
              onClick={() => setShowCreateForm(true)}
              className="inline-flex h-9 items-center gap-2 rounded bg-safety px-4 text-[13px] font-medium text-white transition-all hover:bg-safety/90"
            >
              <Plus className="h-3.5 w-3.5" />
              Initialize Workspace
            </button>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="flex h-36 flex-col items-center justify-center rounded border border-border/40 bg-card/30 text-center">
            <Search className="mb-2 h-5 w-5 text-text-secondary/40" />
            <p className="text-[13px] text-text-primary/70">No matching workspaces</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredProjects.map((project) => (
              <div
                key={project.id}
                role="button"
                tabIndex={0}
                onClick={() => router.push(`/project/${encodeURIComponent(project.id)}`)}
                onKeyDown={(e) => e.key === 'Enter' && router.push(`/project/${encodeURIComponent(project.id)}`)}
                className="group relative flex h-36 cursor-pointer flex-col justify-between rounded border border-border/40 bg-card/30 p-5 text-left transition-all hover:border-safety/40 hover:bg-card/50"
              >
                {/* Delete button */}
                <button
                  type="button"
                  onClick={(event) => handleDeleteProject(event, project)}
                  disabled={deletingProjectId === project.id}
                  className="absolute right-3 top-3 z-10 inline-flex h-6 w-6 items-center justify-center rounded border border-transparent text-text-secondary/0 transition-all group-hover:border-border/50 group-hover:bg-surface group-hover:text-text-secondary hover:!bg-destructive/10 hover:!text-destructive hover:!border-destructive/30 disabled:opacity-50"
                  title="Delete workspace"
                >
                  {deletingProjectId === project.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                </button>

                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded bg-safety/10 border border-safety/10">
                      <FolderKanban className="h-3.5 w-3.5 text-safety" />
                    </div>
                    <p className="line-clamp-1 font-display text-[15px] font-medium text-text-primary group-hover:text-safety transition-colors">
                      {project.name}
                    </p>
                  </div>
                  <p className="line-clamp-2 text-xs text-text-secondary leading-relaxed pl-8">
                    {project.description || "No description provided."}
                  </p>
                </div>

                <div className="flex items-center justify-between pl-8">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-secondary/50">
                    {project.created_at ? formatDate(project.created_at) : ''}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-safety/0 transition-all group-hover:text-safety">
                    Open <ArrowRight className="h-3 w-3" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
