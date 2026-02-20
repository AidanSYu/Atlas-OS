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
    <main className="min-h-screen bg-background text-foreground">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-border">
        <div className="absolute inset-0 atlas-dot-grid opacity-40" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-primary/8 via-accent/5 to-transparent rounded-full blur-3xl" />

        <div className="relative mx-auto max-w-6xl px-6 pt-16 pb-12 sm:px-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent glow-md">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="gradient-text font-serif text-4xl sm:text-5xl font-bold tracking-tight">Atlas</h1>
            </div>
          </div>
          <p className="max-w-xl text-lg text-muted-foreground leading-relaxed">
            Research-native intelligence. Upload papers, discover connections,
            and let multi-agent AI do the heavy lifting.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                <Brain className="h-3.5 w-3.5 text-primary" />
              </div>
              <span>Multi-Agent Swarm</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
                <Network className="h-3.5 w-3.5 text-accent" />
              </div>
              <span>Knowledge Graphs</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                <BookOpen className="h-3.5 w-3.5 text-primary" />
              </div>
              <span>Deep Document Analysis</span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        {/* Actions Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
          <div className="flex items-center gap-3">
            <h2 className="font-serif text-xl text-foreground">Workspaces</h2>
            <span className="rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
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
                  placeholder="Search workspaces..."
                  className="h-9 w-56 rounded-lg border border-border bg-card pl-9 pr-3 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary/50 focus:ring-1 focus:ring-primary/25"
                />
              </div>
            )}
            <button
              onClick={() => setShowCreateForm(true)}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary/80 px-4 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:opacity-90 hover:shadow-md glow-sm"
            >
              <Plus className="h-4 w-4" />
              New Workspace
            </button>
          </div>
        </div>

        {/* Create Project Modal Overlay */}
        {showCreateForm && (
          <div className="mb-8 rounded-xl border border-primary/20 bg-card p-6 glow-sm">
            <h3 className="font-serif text-lg text-foreground mb-4">Create New Workspace</h3>
            <div className="flex gap-3">
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleCreateProject()}
                placeholder="e.g., Literature Review: Neural Architecture Search"
                autoFocus
                className="h-10 flex-1 rounded-lg border border-border bg-background px-4 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary/50 focus:ring-1 focus:ring-primary/25"
              />
              <button
                onClick={handleCreateProject}
                disabled={creatingProject || !newProjectName.trim()}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 disabled:opacity-40"
              >
                {creatingProject ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Create
              </button>
              <button
                onClick={() => { setShowCreateForm(false); setNewProjectName(''); }}
                className="h-10 rounded-lg border border-border px-4 text-sm text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-4 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
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
              <div key={index} className="h-44 animate-pulse rounded-xl border border-border bg-card" />
            ))}
          </div>
        ) : projects.length === 0 && !showCreateForm ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/50 py-20 px-8 text-center">
            <div className="relative mb-6">
              <div className="rounded-2xl bg-gradient-to-br from-primary/10 to-accent/10 p-6">
                <Sparkles className="h-10 w-10 text-primary" />
              </div>
              <div className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-accent glow-accent" />
            </div>
            <h3 className="font-serif text-2xl text-foreground mb-2">Start Your Research</h3>
            <p className="max-w-md text-sm text-muted-foreground leading-relaxed mb-8">
              Create your first workspace to upload papers, build knowledge graphs,
              and let Atlas's multi-agent system accelerate your research.
            </p>
            <button
              onClick={() => setShowCreateForm(true)}
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-primary to-accent px-6 text-sm font-medium text-white shadow-lg transition-all hover:opacity-90 hover:shadow-xl glow-md"
            >
              <Plus className="h-4 w-4" />
              Create First Workspace
            </button>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center rounded-xl border border-border bg-card text-center">
            <FolderKanban className="mb-3 h-7 w-7 text-muted-foreground/40" />
            <p className="text-sm text-foreground/70">No matching workspaces</p>
            <p className="mt-1 text-xs text-muted-foreground">Try a different search term</p>
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
                className="group relative flex h-44 cursor-pointer flex-col justify-between rounded-xl border border-border bg-card p-5 text-left transition-all hover:border-primary/40 hover:bg-card/80 hover:shadow-lg hover:shadow-primary/5"
              >
                {/* Delete button */}
                <button
                  type="button"
                  onClick={(event) => handleDeleteProject(event, project)}
                  disabled={deletingProjectId === project.id}
                  className="absolute right-3 top-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-lg border border-transparent text-muted-foreground/0 transition-all group-hover:border-border group-hover:bg-surface group-hover:text-muted-foreground hover:!bg-destructive/10 hover:!text-destructive hover:!border-destructive/30 disabled:opacity-50"
                  title="Delete workspace"
                >
                  {deletingProjectId === project.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                </button>

                <div>
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <FolderKanban className="h-4 w-4 text-primary" />
                    </div>
                    <p className="line-clamp-1 font-serif text-lg text-foreground group-hover:text-primary transition-colors">
                      {project.name}
                    </p>
                  </div>
                  <p className="line-clamp-2 text-xs text-muted-foreground leading-relaxed pl-[42px]">
                    {project.description || 'No description'}
                  </p>
                </div>

                <div className="flex items-center justify-between pl-[42px]">
                  <span className="text-[11px] text-muted-foreground/60">
                    {project.created_at ? formatDate(project.created_at) : ''}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs text-primary/0 transition-all group-hover:text-primary">
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
