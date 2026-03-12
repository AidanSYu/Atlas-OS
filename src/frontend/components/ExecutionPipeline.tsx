'use client';

import React, { useState, useCallback, useRef, useMemo } from 'react';
import {
  Activity,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Download,
  FileJson2,
  Loader2,
  AlertCircle,
  Clock,
  CheckCircle2,
  Circle,
  Pause,
} from 'lucide-react';
import type { Run, ToolInvocation } from '@/stores/runStore';
import { STAGE_LABELS, type GoldenPathStage } from '@/lib/discovery-types';
import {
  truncatePayload,
  downloadBlob,
  PIPELINE_RENDER_LIMITS,
  type TruncatedPayload,
} from '@/lib/truncate-payload';

// ---------------------------------------------------------------------------
// Stage grouping: derive pipeline stages from tool invocations
// ---------------------------------------------------------------------------

interface PipelineStage {
  label: string;
  tools: ToolInvocation[];
  status: 'pending' | 'running' | 'completed' | 'failed';
  elapsedMs: number | null;
}

function derivePipelineStages(run: Run): PipelineStage[] {
  if (run.toolInvocations.length === 0) {
    const stageLabel =
      run.mode === 'discovery' ? 'DISCOVERY' : run.mode.toUpperCase();
    return [
      {
        label: stageLabel,
        tools: [],
        status: mapRunStatus(run.status),
        elapsedMs: run.completedAt
          ? run.completedAt - run.startedAt
          : Date.now() - run.startedAt,
      },
    ];
  }

  const stageMap: Record<string, ToolInvocation[]> = {};
  for (const tool of run.toolInvocations) {
    const prefix = tool.tool.split('_')[0] || tool.tool;
    const stageKey = prefix.toUpperCase();
    if (!stageMap[stageKey]) stageMap[stageKey] = [];
    stageMap[stageKey].push(tool);
  }

  const stages: PipelineStage[] = [];
  for (const label of Object.keys(stageMap)) {
    const tools: ToolInvocation[] = stageMap[label];
    const hasRunning = tools.some((t: ToolInvocation) => t.status === 'running');
    const hasFailed = tools.some((t: ToolInvocation) => t.status === 'failed');
    const allComplete = tools.every((t: ToolInvocation) => t.status === 'completed');

    const earliest = Math.min(...tools.map((t: ToolInvocation) => t.startedAt));
    const latest = Math.max(
      ...tools.map((t: ToolInvocation) => t.completedAt ?? Date.now()),
    );

    stages.push({
      label,
      tools,
      status: hasFailed
        ? 'failed'
        : hasRunning
          ? 'running'
          : allComplete
            ? 'completed'
            : 'pending',
      elapsedMs: latest - earliest,
    });
  }

  return stages;
}

function mapRunStatus(
  status: Run['status'],
): PipelineStage['status'] {
  switch (status) {
    case 'completed':
      return 'completed';
    case 'failed':
      return 'failed';
    case 'running':
    case 'routing':
    case 'awaiting_override':
    case 'awaiting_input':
      return 'running';
    default:
      return 'pending';
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusIcon({ status }: { status: PipelineStage['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
    case 'running':
      return <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />;
    case 'failed':
      return <AlertCircle className="h-3.5 w-3.5 text-red-400" />;
    case 'pending':
    default:
      return <Circle className="h-3.5 w-3.5 text-zinc-500" />;
  }
}

function ToolStatusIcon({ status }: { status: ToolInvocation['status'] }) {
  switch (status) {
    case 'completed':
      return <Check className="h-3 w-3 text-emerald-400" />;
    case 'running':
      return <Loader2 className="h-3 w-3 text-blue-400 animate-spin" />;
    case 'failed':
      return <AlertCircle className="h-3 w-3 text-red-400" />;
  }
}

function formatElapsed(ms: number | null): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ---------------------------------------------------------------------------
// Payload viewer with truncation
// ---------------------------------------------------------------------------

function PayloadBlock({
  label,
  value,
  runId,
  toolName,
}: {
  label: string;
  value: Record<string, any> | null;
  runId: string;
  toolName: string;
}) {
  const truncated = useMemo<TruncatedPayload | null>(() => {
    if (value === null || value === undefined) return null;
    const filename = `${runId}_${toolName}_${label.toLowerCase()}.json`;
    return truncatePayload(value, filename);
  }, [value, runId, toolName, label]);

  if (!truncated) {
    return (
      <div className="text-[10px] text-zinc-500 italic ml-4">
        {label}: null
      </div>
    );
  }

  return (
    <div className="ml-4 mt-1">
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="text-[10px] uppercase text-zinc-500">{label}</span>
        {truncated.isTruncated && (
          <button
            onClick={() => downloadBlob(truncated, value)}
            className="flex items-center gap-0.5 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
          >
            <Download className="h-2.5 w-2.5" />
            <span>
              Download ({truncated.fullSizeBytes > 1024
                ? `${(truncated.fullSizeBytes / 1024).toFixed(0)} KB`
                : `${truncated.fullSizeBytes} B`})
            </span>
          </button>
        )}
      </div>
      <pre className="text-[10px] leading-relaxed text-zinc-400 bg-black/30 rounded px-2 py-1.5 overflow-x-auto max-h-40 whitespace-pre-wrap break-all">
        {truncated.preview}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tool invocation row
// ---------------------------------------------------------------------------

function ToolRow({
  tool,
  runId,
}: {
  tool: ToolInvocation;
  runId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const elapsed = tool.completedAt
    ? tool.completedAt - tool.startedAt
    : Date.now() - tool.startedAt;

  return (
    <div className="ml-5 border-l border-zinc-700/50 pl-3 py-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 w-full text-left group"
      >
        {expanded ? (
          <ChevronDown className="h-2.5 w-2.5 text-zinc-500" />
        ) : (
          <ChevronRight className="h-2.5 w-2.5 text-zinc-500" />
        )}
        <ToolStatusIcon status={tool.status} />
        <span className="text-[11px] text-zinc-300 font-mono group-hover:text-zinc-100 transition-colors">
          {tool.tool}
        </span>
        <span className="ml-auto text-[10px] text-zinc-600 tabular-nums">
          {formatElapsed(elapsed)}
        </span>
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          <PayloadBlock
            label="Input"
            value={tool.input}
            runId={runId}
            toolName={tool.tool}
          />
          <PayloadBlock
            label="Output"
            value={tool.output}
            runId={runId}
            toolName={tool.tool}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline stage row
// ---------------------------------------------------------------------------

function StageRow({
  stage,
  runId,
}: {
  stage: PipelineStage;
  runId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const toolCount = stage.tools.length;
  const completedCount = stage.tools.filter(
    (t) => t.status === 'completed',
  ).length;

  return (
    <div className="py-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left group px-1 py-0.5 rounded hover:bg-white/[0.03] transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-zinc-500" />
        ) : (
          <ChevronRight className="h-3 w-3 text-zinc-500" />
        )}
        <StatusIcon status={stage.status} />
        <span className="text-xs font-semibold text-zinc-200 tracking-wide">
          {stage.label}
        </span>
        {toolCount > 0 && (
          <span className="text-[10px] text-zinc-500 tabular-nums">
            {completedCount}/{toolCount}
          </span>
        )}
        <span className="ml-auto text-[10px] text-zinc-600 tabular-nums">
          {formatElapsed(stage.elapsedMs)}
        </span>
      </button>
      {expanded && stage.tools.length > 0 && (
        <div className="mt-0.5">
          {stage.tools.map((tool, idx) => (
            <ToolRow
              key={`${tool.tool}-${idx}`}
              tool={tool}
              runId={runId}
            />
          ))}
        </div>
      )}
      {expanded && stage.tools.length === 0 && (
        <div className="ml-8 text-[10px] text-zinc-600 italic py-1">
          No tool invocations recorded
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Full JSON log dialog
// ---------------------------------------------------------------------------

function JsonLogDialog({
  run,
  open,
  onClose,
}: {
  run: Run;
  open: boolean;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  React.useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const truncated = useMemo(
    () => truncatePayload(run.events, `run_${run.id}_events.json`),
    [run.events, run.id],
  );

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="w-[80vw] max-w-3xl max-h-[80vh] bg-zinc-900 text-zinc-200 rounded-xl border border-zinc-700 shadow-2xl p-0 backdrop:bg-black/60"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700">
        <span className="text-sm font-semibold">
          Full Event Log — Run {run.id.slice(0, 8)}
        </span>
        <button
          onClick={onClose}
          className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-white/10 transition-colors"
        >
          Close
        </button>
      </div>
      <div className="p-4 overflow-auto max-h-[70vh]">
        <pre className="text-[11px] font-mono leading-relaxed text-zinc-300 whitespace-pre-wrap break-all">
          {truncated.preview}
        </pre>
        {truncated.isTruncated && (
          <button
            onClick={() => downloadBlob(truncated, run.events)}
            className="mt-3 flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download full log ({(truncated.fullSizeBytes / 1024).toFixed(0)} KB)
          </button>
        )}
      </div>
    </dialog>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ExecutionPipelineProps {
  run: Run | null;
}

export function ExecutionPipeline({ run }: ExecutionPipelineProps) {
  const [copied, setCopied] = useState(false);
  const [logOpen, setLogOpen] = useState(false);

  const copyRunId = useCallback(() => {
    if (!run) return;
    navigator.clipboard.writeText(run.id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [run]);

  const exportReport = useCallback(() => {
    if (!run) return;
    const report = {
      id: run.id,
      mode: run.mode,
      intent: run.intent,
      query: run.query,
      status: run.status,
      startedAt: new Date(run.startedAt).toISOString(),
      completedAt: run.completedAt
        ? new Date(run.completedAt).toISOString()
        : null,
      durationMs: run.completedAt
        ? run.completedAt - run.startedAt
        : null,
      toolInvocations: run.toolInvocations,
      eventCount: run.events.length,
      error: run.error,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `run_${run.id.slice(0, 8)}_report.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [run]);

  // Empty state
  if (!run) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center bg-card/30">
        <div className="rounded-2xl bg-surface/50 p-6 mb-4">
          <Activity className="h-10 w-10 text-muted-foreground/40" />
        </div>
        <p className="font-serif text-lg text-foreground/60">
          Execution Pipeline
        </p>
        <p className="mt-2 text-xs text-muted-foreground max-w-[220px]">
          Run a query or launch a workflow to see the live execution trace here.
        </p>
      </div>
    );
  }

  const stages = derivePipelineStages(run);
  const isActive = ['running', 'routing', 'awaiting_override', 'awaiting_input'].includes(run.status);
  const elapsed = run.completedAt
    ? run.completedAt - run.startedAt
    : Date.now() - run.startedAt;

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-card/30 border-l border-border/50">
      {/* Header */}
      <div className="flex items-center gap-2 shrink-0 h-12 border-b border-border/50 bg-background/50 px-4">
        <Activity className="h-4 w-4 text-blue-500" />
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Pipeline
        </span>
        {isActive && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
        )}

        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-zinc-500">
            {run.id.slice(0, 8)}
          </span>
          <button
            onClick={copyRunId}
            className="p-1 rounded hover:bg-white/10 transition-colors"
            title="Copy run ID"
          >
            {copied ? (
              <Check className="h-3 w-3 text-emerald-400" />
            ) : (
              <Copy className="h-3 w-3 text-zinc-500 hover:text-zinc-300" />
            )}
          </button>
        </div>
      </div>

      {/* Run summary bar */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-border/30 bg-surface/20">
        <span className="text-[10px] uppercase text-zinc-500">
          {run.mode}
        </span>
        <span className="text-[10px] text-zinc-600">·</span>
        <span className="text-[10px] text-zinc-400 truncate max-w-[140px]">
          {run.intent || run.query.slice(0, 50)}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Clock className="h-3 w-3 text-zinc-600" />
          <span className="text-[10px] text-zinc-500 tabular-nums">
            {formatElapsed(elapsed)}
          </span>
        </div>
      </div>

      {/* Stage list */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {stages.map((stage, idx) => (
          <StageRow
            key={`${stage.label}-${idx}`}
            stage={stage}
            runId={run.id}
          />
        ))}

        {/* Error display */}
        {run.error && (
          <div className="mt-3 mx-1 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20">
            <div className="flex items-center gap-1.5 mb-1">
              <AlertCircle className="h-3.5 w-3.5 text-red-400" />
              <span className="text-[11px] font-medium text-red-300">
                {run.error.category}
              </span>
            </div>
            <p className="text-[11px] text-red-300/80 ml-5">
              {run.error.message}
            </p>
          </div>
        )}

        {/* Awaiting user input */}
        {run.status === 'awaiting_input' && (
          <div className="mt-3 mx-1 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <div className="flex items-center gap-1.5">
              <Pause className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-[11px] text-amber-300">
                Waiting for researcher input…
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-t border-border/30 bg-background/30">
        <button
          onClick={() => setLogOpen(true)}
          className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <FileJson2 className="h-3 w-3" />
          View full JSON log
        </button>
        <button
          onClick={exportReport}
          className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors ml-auto"
        >
          <Download className="h-3 w-3" />
          Export run report
        </button>
      </div>

      {/* Log dialog */}
      <JsonLogDialog
        run={run}
        open={logOpen}
        onClose={() => setLogOpen(false)}
      />
    </div>
  );
}
