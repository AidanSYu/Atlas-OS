'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useDiscoveryStore } from '@/stores/discoveryStore';
import {
  useDiscoveryConversation,
  type DiscoveryMessage,
  type PlanData,
  type SessionConversation,
} from '@/stores/discoveryConversationStore';
import { DiscoveryChat } from './discovery/DiscoveryChat';
import { PluginManager } from './PluginManager';
import { PipelineRunBlock } from './discovery/PipelineRunBlock';
import { ResultsSummary } from './discovery/ResultsSummary';
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Eye,
  FileText,
  FlaskConical,
  Gauge,
  Loader2,
  Puzzle,
  Sparkles,
  X,
} from 'lucide-react';

import { api } from '@/lib/api';
import { usePanelResize } from '@/hooks/usePanelResize';

interface DiscoveryWorkspaceTabProps {
  sessionId: string;
  projectId: string;
}

const EMPTY_CONVERSATION: SessionConversation = {
  sessionId: '',
  messages: [],
  stage: 'setup',
  isStreaming: false,
  pendingPlan: null,
  candidates: [],
  pipelineRuns: [],
  activeRunId: null,
};

function DragHandle({
  direction,
  onMouseDown,
  isDragging,
}: {
  direction: 'horizontal' | 'vertical';
  onMouseDown: (event: React.MouseEvent) => void;
  isDragging: boolean;
}) {
  const isHorizontal = direction === 'horizontal';
  return (
    <div
      onMouseDown={onMouseDown}
      className={[
        'group relative shrink-0 select-none transition-colors duration-100',
        isHorizontal
          ? 'w-[5px] cursor-col-resize hover:bg-accent/20 active:bg-accent/30'
          : 'h-[5px] cursor-row-resize hover:bg-accent/20 active:bg-accent/30',
        isDragging ? 'bg-accent/30' : 'bg-border/60',
      ].join(' ')}
    >
      <div
        className={[
          'absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border transition-colors group-hover:bg-accent/60',
          isDragging ? 'bg-accent/60' : '',
          isHorizontal ? 'h-8 w-[2px]' : 'h-[2px] w-8',
        ].join(' ')}
      />
    </div>
  );
}

type RightTab = 'progress' | 'results' | 'files' | 'plugins';

export function DiscoveryWorkspaceTab({ sessionId, projectId }: DiscoveryWorkspaceTabProps) {
  const session = useDiscoveryStore((state) => state.sessions[sessionId]);
  const conversation = useDiscoveryConversation((state) => state.conversations[sessionId]) ?? EMPTY_CONVERSATION;
  const toggleRunCollapsed = useDiscoveryConversation((state) => state.toggleRunCollapsed);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<RightTab>('progress');
  const [previewFile, setPreviewFile] = useState<{ filename: string; content: string } | null>(null);

  const { size: rightWidth, handleMouseDown: handleDragStart, isDragging } = usePanelResize({
    initialSize: 430,
    minSize: 320,
    maxSize: 760,
    direction: 'horizontal',
    storageKey: 'atlas-experiment-right-panel-width',
  });

  const latestPlan = useMemo<PlanData | null>(() => {
    if (conversation.pendingPlan) return conversation.pendingPlan;
    const plans = conversation.messages
      .filter((message) => message.type === 'plan' && message.plan)
      .map((message) => message.plan as PlanData);
    return plans.at(-1) ?? null;
  }, [conversation.messages, conversation.pendingPlan]);

  const latestAnalysis = useMemo(() => {
    const analyses = conversation.messages.filter((message) => message.type === 'analysis' && message.analysis);
    return analyses.at(-1)?.analysis ?? null;
  }, [conversation.messages]);

  const toolMessagesByRun = useMemo(() => {
    const messageLookup = new Map<string, DiscoveryMessage>();
    for (const message of conversation.messages) {
      messageLookup.set(message.id, message);
    }

    return conversation.pipelineRuns.map((run) => ({
      run,
      messages: run.messageIds
        .map((id) => messageLookup.get(id))
        .filter((message): message is DiscoveryMessage => Boolean(message)),
    }));
  }, [conversation.messages, conversation.pipelineRuns]);

  const handleViewFile = useCallback(async (filePath: string) => {
    try {
      const file = await api.readSessionFile(sessionId, filePath);
      setPreviewFile({ filename: file.filename, content: file.content });
    } catch (err) {
      console.error('Failed to read session file:', err);
    }
  }, [sessionId]);

  const refreshSessionFiles = useCallback(async () => {
    try {
      const files = await api.getSessionFiles(sessionId);
      useDiscoveryStore.setState((state) => {
        if (!state.sessions[sessionId]) return state;
        return {
          ...state,
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              generatedFiles: files.map((file) => file.path),
            },
          },
        };
      });
    } catch (err) {
      console.error('Failed to refresh session files:', err);
    }
  }, [sessionId]);

  useEffect(() => {
    async function loadSessionFiles() {
      try {
        setIsLoading(true);
        setError(null);
        const files = await api.getSessionFiles(sessionId);
        useDiscoveryStore.setState((state) => {
          if (!state.sessions[sessionId]) return state;
          return {
            ...state,
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...state.sessions[sessionId],
                generatedFiles: files.map((file) => file.path),
              },
            },
          };
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        if (!message.includes('404') && !message.toLowerCase().includes('not found')) {
          setError(message);
          console.error('Failed to load session files:', err);
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadSessionFiles();
  }, [sessionId]);

  const handleCandidatesUpdate = useCallback((_candidates: any[]) => {
    void refreshSessionFiles();
    setRightTab('results');
  }, [refreshSessionFiles]);

  const handleStageChange = useCallback((stage: string) => {
    if (stage === 'ready' || stage === 'complete') {
      void refreshSessionFiles();
    }
  }, [refreshSessionFiles]);

  const candidates = conversation.candidates ?? [];

  if (!session) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Session not found: {sessionId}</p>
          <p className="mt-2 text-xs text-muted-foreground">This task may have been deleted or is still initializing.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-accent" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">Loading task</p>
            <p className="mt-1 text-xs text-muted-foreground">{session.sessionName}</p>
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
          <p className="mt-2 text-xs text-muted-foreground">Failed to load task data.</p>
        </div>
      </div>
    );
  }

  const riskColor = (risk: string) => {
    if (!risk || risk === 'N/A') return 'text-muted-foreground';
    if (risk === 'LOW') return 'text-green-400';
    if (risk === 'MEDIUM') return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <DiscoveryChat
          sessionId={sessionId}
          projectId={projectId}
          onCandidatesUpdate={handleCandidatesUpdate}
          onStageChange={handleStageChange}
        />
      </div>

      <DragHandle direction="horizontal" onMouseDown={handleDragStart} isDragging={isDragging} />

      <div
        className="flex shrink-0 flex-col overflow-hidden border-l border-border bg-card/80"
        style={{ width: rightWidth }}
      >
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-accent" />
            <div>
              <p className="text-sm font-semibold text-foreground">Task cockpit</p>
              <p className="text-[11px] text-muted-foreground">
                Atlas plans, progress, results, files, and plugins stay attached to this run.
              </p>
            </div>
          </div>
        </div>

        <div className="flex h-10 shrink-0 border-b border-border bg-surface/25 px-2">
          {([
            { key: 'progress' as RightTab, label: 'Progress', icon: Gauge, count: conversation.pipelineRuns.length },
            { key: 'results' as RightTab, label: 'Results', icon: Database, count: candidates.length },
            { key: 'files' as RightTab, label: 'Files', icon: FileText, count: session.generatedFiles?.length ?? 0 },
            { key: 'plugins' as RightTab, label: 'Plugins', icon: Puzzle },
          ]).map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              type="button"
              onClick={() => setRightTab(key)}
              className={[
                'flex h-full items-center gap-1.5 rounded-none border-b-2 px-3 text-[11px] font-medium transition-colors',
                rightTab === key
                  ? 'border-accent text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <Icon className="h-3 w-3" />
              {label}
              {count != null && count > 0 && (
                <span className="rounded-full bg-background px-1.5 py-0.5 text-[9px] text-muted-foreground">
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {rightTab === 'progress' && (
            <div className="space-y-4 p-4">
              <div className="grid grid-cols-2 gap-2">
                <ProgressMetric
                  label="Stage"
                  value={formatStageLabel(conversation.stage)}
                  tone={conversation.stage === 'executing' ? 'active' : 'neutral'}
                />
                <ProgressMetric
                  label="Files"
                  value={String(session.generatedFiles?.length ?? 0)}
                  tone="neutral"
                />
                <ProgressMetric
                  label="Plans"
                  value={latestPlan ? latestPlan.status : 'none'}
                  tone={latestPlan?.status === 'accepted' ? 'good' : latestPlan?.status === 'proposed' ? 'active' : 'neutral'}
                />
                <ProgressMetric
                  label="Runs"
                  value={String(conversation.pipelineRuns.length)}
                  tone={conversation.pipelineRuns.length > 0 ? 'active' : 'neutral'}
                />
              </div>

              {latestPlan ? (
                <PlanSnapshot plan={latestPlan} />
              ) : (
                <div className="rounded-3xl border border-dashed border-border bg-background/60 p-4">
                  <div className="flex items-start gap-3">
                    <Sparkles className="mt-0.5 h-4 w-4 text-accent" />
                    <div>
                      <p className="text-sm font-medium text-foreground">Waiting for Atlas to draft a plan</p>
                      <p className="mt-1 text-[12px] leading-6 text-muted-foreground">
                        Once the orchestrator proposes an execution route, it will appear here with stages, timing,
                        warnings, and acceptance status.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {toolMessagesByRun.length > 0 ? (
                <div className="space-y-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    Pipeline runs
                  </div>
                  {toolMessagesByRun
                    .slice()
                    .reverse()
                    .map(({ run, messages }) => (
                      <PipelineRunBlock
                        key={run.runId}
                        run={run}
                        messages={messages}
                        onToggle={() => toggleRunCollapsed(sessionId, run.runId)}
                      />
                    ))}
                </div>
              ) : (
                <div className="rounded-3xl border border-border/70 bg-background/50 p-4">
                  <div className="flex items-start gap-3">
                    <FlaskConical className="mt-0.5 h-4 w-4 text-emerald-400" />
                    <div>
                      <p className="text-sm font-medium text-foreground">No pipeline runs yet</p>
                      <p className="mt-1 text-[12px] leading-6 text-muted-foreground">
                        Atlas will log each tool stage here as soon as an accepted plan starts running.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {rightTab === 'results' && (
            <div className="flex h-full flex-col">
              <div className="border-b border-border px-4 py-3">
                <p className="text-sm font-semibold text-foreground">Candidate results</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Ranked outputs, latest analysis, and generated evidence from this task.
                </p>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto">
                <div className="space-y-4 p-4">
                  {latestAnalysis && <ResultsSummary analysis={latestAnalysis} />}

                  {candidates.length === 0 ? (
                    <div className="flex h-[240px] items-center justify-center rounded-3xl border border-dashed border-border bg-background/60 p-6 text-center">
                      <div>
                        <Database className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
                        <p className="text-xs text-muted-foreground">No candidates yet</p>
                        <p className="mt-1 text-[10px] text-muted-foreground/60">
                          Run the pipeline to populate task results.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="overflow-hidden rounded-3xl border border-border bg-background/65">
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-left text-[11px]">
                          <thead>
                            <tr className="border-b border-border bg-surface/40 text-muted-foreground">
                              <th className="px-3 py-2 font-medium">#</th>
                              <th className="px-3 py-2 font-medium">Compound</th>
                              <th className="px-3 py-2 font-medium">MW</th>
                              <th className="px-3 py-2 font-medium">LogP</th>
                              <th className="px-3 py-2 font-medium">SA</th>
                              <th className="px-3 py-2 font-medium">hERG</th>
                              <th className="px-3 py-2 font-medium">Safety</th>
                            </tr>
                          </thead>
                          <tbody>
                            {candidates.map((candidate: any, index: number) => (
                              <tr
                                key={`${candidate.compound_id ?? candidate.smiles ?? index}-${index}`}
                                className="border-b border-border/70 transition-colors hover:bg-surface/30"
                              >
                                <td className="px-3 py-2 text-muted-foreground">{index + 1}</td>
                                <td
                                  className="max-w-[170px] truncate px-3 py-2 font-mono text-foreground/90"
                                  title={candidate.smiles}
                                >
                                  {candidate.compound_id || candidate.smiles?.slice(0, 24) || '-'}
                                </td>
                                <td className="px-3 py-2 text-muted-foreground">
                                  {candidate.properties?.MolWt != null ? Number(candidate.properties.MolWt).toFixed(0) : '-'}
                                </td>
                                <td className="px-3 py-2 text-muted-foreground">
                                  {candidate.properties?.LogP != null ? Number(candidate.properties.LogP).toFixed(1) : '-'}
                                </td>
                                <td className="px-3 py-2 text-muted-foreground">
                                  {candidate.sa_score != null ? Number(candidate.sa_score).toFixed(1) : '-'}
                                </td>
                                <td className={['px-3 py-2 font-medium', riskColor(candidate.admet?.herg_risk)].join(' ')}>
                                  {candidate.admet?.herg_risk || '-'}
                                </td>
                                <td className="px-3 py-2">
                                  {candidate.toxicity ? (
                                    candidate.toxicity.clean ? (
                                      <span className="flex items-center gap-1 text-[10px] text-green-400">
                                        <CheckCircle2 className="h-3 w-3" />
                                        Pass
                                      </span>
                                    ) : (
                                      <span
                                        className="flex items-center gap-1 text-[10px] text-red-400"
                                        title={`${candidate.toxicity.alert_count} alerts`}
                                      >
                                        <AlertTriangle className="h-3 w-3" />
                                        Fail
                                      </span>
                                    )
                                  ) : (
                                    <span className={['text-[10px] font-medium', riskColor(candidate.admet?.overall)].join(' ')}>
                                      {candidate.admet?.overall || '-'}
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {rightTab === 'files' && (
            <div className="p-4">
              {(session.generatedFiles?.length ?? 0) === 0 ? (
                <div className="rounded-3xl border border-dashed border-border bg-background/60 px-4 py-8 text-center">
                  <FileText className="mx-auto mb-3 h-8 w-8 text-muted-foreground/30" />
                  <p className="text-xs text-muted-foreground">
                    No files generated yet. Atlas will attach artifacts here as the task advances.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {(session.generatedFiles ?? []).map((filePath, index) => {
                    const isViewable = /\.(md|json|txt|csv|py|log)$/i.test(filePath);
                    return (
                      <button
                        key={`${filePath}-${index}`}
                        onClick={() => isViewable && void handleViewFile(filePath)}
                        className={[
                          'group flex w-full items-center gap-2 rounded-2xl border border-border/70 bg-background/55 px-3 py-2 text-left text-xs transition-colors',
                          isViewable ? 'hover:border-border hover:bg-surface/40' : 'cursor-default',
                        ].join(' ')}
                      >
                        <FileText className={['h-3.5 w-3.5 shrink-0', filePath.endsWith('.md') ? 'text-emerald-400' : 'text-muted-foreground'].join(' ')} />
                        <span className="min-w-0 flex-1 truncate font-mono text-foreground/85">{filePath}</span>
                        {isViewable && (
                          <Eye className="h-3.5 w-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {rightTab === 'plugins' && <PluginManager projectId={projectId} />}
        </div>
      </div>

      {previewFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
          <div className="relative mx-4 flex max-h-[80vh] w-full max-w-3xl flex-col rounded-3xl border border-border bg-card shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <FileText className={['h-4 w-4', previewFile.filename.endsWith('.md') ? 'text-emerald-400' : 'text-muted-foreground'].join(' ')} />
                <span className="text-sm font-medium text-foreground">{previewFile.filename}</span>
              </div>
              <button
                onClick={() => setPreviewFile(null)}
                className="rounded-xl p-1.5 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/90">
                {previewFile.content}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ProgressMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'neutral' | 'active' | 'good';
}) {
  const toneClass =
    tone === 'good'
      ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
      : tone === 'active'
        ? 'border-accent/25 bg-accent/10 text-foreground'
        : 'border-border bg-background/60 text-foreground';

  return (
    <div className={['rounded-2xl border px-3 py-2.5', toneClass].join(' ')}>
      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold capitalize">{value}</p>
    </div>
  );
}

function PlanSnapshot({ plan }: { plan: PlanData }) {
  return (
    <div className="rounded-3xl border border-border/80 bg-background/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Current plan</p>
            <p className="text-sm font-medium text-foreground">Iteration {plan.iteration}</p>
          </div>
        </div>
        <span
          className={[
            'rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em]',
            plan.status === 'accepted'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : plan.status === 'rejected'
                ? 'border-destructive/30 bg-destructive/10 text-destructive'
                : 'border-accent/30 bg-accent/10 text-accent',
          ].join(' ')}
        >
          {plan.status}
        </span>
      </div>

      <p className="mt-3 text-sm leading-6 text-foreground/90">{plan.summary}</p>

      <div className="mt-4 space-y-2">
        {plan.stages.map((stage) => (
          <div
            key={`${plan.planId}-${stage.stageId}`}
            className="flex items-start gap-3 rounded-2xl border border-border/70 bg-card/70 px-3 py-2.5"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-background/60 text-[10px] font-semibold text-muted-foreground">
              {stage.stageId}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-medium text-foreground">{stage.description}</p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">
                {stage.plugin} · ~{stage.estimatedSeconds}s
              </p>
            </div>
          </div>
        ))}
      </div>

      {plan.warnings.length > 0 && (
        <div className="mt-4 rounded-2xl border border-warning/25 bg-warning/10 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-warning">Warnings</p>
          <div className="mt-2 space-y-1.5">
            {plan.warnings.map((warning, index) => (
              <div key={`${warning}-${index}`} className="flex items-start gap-2 text-[11px] text-warning">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatStageLabel(stage: string): string {
  switch (stage) {
    case 'setup':
      return 'setup';
    case 'ready':
      return 'ready';
    case 'executing':
      return 'running';
    case 'complete':
      return 'complete';
    default:
      return stage || 'idle';
  }
}
