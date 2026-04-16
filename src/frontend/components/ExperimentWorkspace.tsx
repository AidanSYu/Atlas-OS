'use client';

import React from 'react';
import {
  ArrowRight,
  Database,
  FileText,
  FlaskConical,
  Sparkles,
} from 'lucide-react';

import { DiscoveryWorkspaceTab } from '@/components/DiscoveryWorkspaceTab';

interface ExperimentWorkspaceProps {
  projectId: string;
  activeSessionId: string | null;
  onStartExperiment: () => void;
}

const EXPERIMENT_PILLARS = [
  {
    title: 'Plan',
    body: 'Atlas proposes an execution plan before it touches tools, so you can approve the route instead of reading backend logs.',
    icon: Sparkles,
  },
  {
    title: 'Run',
    body: 'Discovery, orchestration, and plugin work stay in one surface with progress, files, and outputs aligned to the same session.',
    icon: Database,
  },
  {
    title: 'Ship',
    body: 'Generated artifacts and candidate results stay attached to the task so real work can move forward without context switching.',
    icon: FileText,
  },
];

export function ExperimentWorkspace({
  projectId,
  activeSessionId,
  onStartExperiment,
}: ExperimentWorkspaceProps) {
  if (activeSessionId) {
    return <DiscoveryWorkspaceTab sessionId={activeSessionId} projectId={projectId} />;
  }

  return (
    <div className="relative flex h-full min-h-0 items-center justify-center overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.08) 1px, transparent 0)',
            backgroundSize: '24px 24px',
            maskImage: 'linear-gradient(to bottom, rgba(0,0,0,0.75), rgba(0,0,0,0.15))',
          }}
        />
        <div className="absolute left-1/2 top-24 h-72 w-72 -translate-x-1/2 rounded-full bg-accent/8 blur-3xl" />
        <div className="absolute bottom-16 right-20 h-56 w-56 rounded-full bg-emerald-500/8 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-col gap-10 px-8 py-10">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            <FlaskConical className="h-3.5 w-3.5 text-emerald-400" />
            Task
          </div>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-foreground">
            Atlas is ready to run real tasks.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
            Start a discovery session to let Atlas propose a plan, run plugins, track progress, and keep generated
            files attached to the same workspace.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onStartExperiment}
              className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition-colors hover:bg-emerald-500/15"
            >
              <FlaskConical className="h-4 w-4" />
              Start task
            </button>
            <div className="inline-flex items-center gap-2 rounded-2xl border border-border/70 bg-card/70 px-4 py-2.5 text-xs text-muted-foreground">
              <ArrowRight className="h-3.5 w-3.5 text-accent" />
              Plans move into the progress rail after Atlas drafts them
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {EXPERIMENT_PILLARS.map(({ title, body, icon: Icon }) => (
            <div
              key={title}
              className="rounded-3xl border border-border/70 bg-card/65 p-5 backdrop-blur-sm"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border/70 bg-background/60">
                <Icon className="h-4.5 w-4.5 text-foreground/80" />
              </div>
              <h2 className="mt-4 text-base font-semibold text-foreground">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
