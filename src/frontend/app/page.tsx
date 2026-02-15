'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api, ProjectInfo } from '@/lib/api';
import { FolderKanban, Search, ArrowRight, Plus, AlertCircle, Trash2, Loader2 } from 'lucide-react';

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
      router.push(`/project/${encodeURIComponent(created.id)}`);
    } catch (e: any) {
      alert(e.message || 'Failed to create project');
    } finally {
      setCreatingProject(false);
    }
  };

  const handleDeleteProject = async (project: ProjectInfo) => {
    const confirmed = window.confirm(`Delete project "${project.name}"? This cannot be undone.`);
    if (!confirmed) return;

    setDeletingProjectId(project.id);
    try {
      await api.deleteProject(project.id);
      setProjects((previous) => previous.filter((item) => item.id !== project.id));
    } catch (e: any) {
      alert(e.message || 'Failed to delete project');
    } finally {
      setDeletingProjectId(null);
    }
  };

  return (
    <main className="min-h-screen atlas-dot-grid bg-background text-foreground">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-10 sm:px-10">
        <header className="mb-8 border border-border bg-card px-6 py-5">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Atlas</p>
          <h1 className="mt-2 font-serif text-3xl text-foreground sm:text-4xl">Research Workspaces</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Select an existing project or create a new one to enter the focused Atlas workspace.
          </p>
        </header>

        <section className="mb-6 border border-border bg-card px-4 py-4 sm:px-5">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search projects by name, ID, or description"
                className="h-10 w-full border border-border bg-background pl-10 pr-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-accent"
              />
            </label>

            <div className="flex gap-2">
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleCreateProject()}
                placeholder="New project name"
                className="h-10 w-full min-w-[220px] border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-accent"
              />
              <button
                onClick={handleCreateProject}
                disabled={creatingProject || !newProjectName.trim()}
                className="inline-flex h-10 items-center gap-1 border border-border bg-surface px-3 text-sm font-medium text-foreground transition-colors hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Plus className="h-4 w-4" />
                New
              </button>
            </div>
          </div>
        </section>

        <section className="flex-1">
          {error && (
            <div className="mb-4 flex items-start gap-2 border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-36 animate-pulse border border-border bg-card" />
              ))}
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center border border-border bg-card text-center">
              <FolderKanban className="mb-3 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-foreground">No matching projects</p>
              <p className="mt-1 text-xs text-muted-foreground">Try another search or create a new workspace.</p>
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
                  className="group relative flex h-36 cursor-pointer flex-col justify-between border border-border bg-card p-4 text-left transition-colors hover:border-accent"
                >
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      handleDeleteProject(project);
                    }}
                    disabled={deletingProjectId === project.id}
                    className="absolute right-2 top-2 z-10 inline-flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive disabled:opacity-50"
                    title="Delete project"
                  >
                    {deletingProjectId === project.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>

                  <div>
                    <p className="line-clamp-1 font-serif text-xl text-foreground">{project.name}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {project.description || 'No description available.'}
                    </p>
                  </div>

                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="line-clamp-1">{project.id}</span>
                    <span className="inline-flex items-center gap-1 text-accent transition-transform group-hover:translate-x-0.5">
                      Open <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
