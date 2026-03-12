'use client';

import React, { useEffect, useState } from 'react';
import {
  Loader2,
  Search,
  Brain,
  BookOpen,
  Network,
  Clock,
  Share2,
} from 'lucide-react';
import type { Run } from '@/stores/runStore';
import type { NormalizedEvent } from '@/lib/stream-adapter';

// ---------------------------------------------------------------------------
// Types — compatible with legacy StreamProgress shape
// ---------------------------------------------------------------------------

interface GraphData {
  summary?: string;
  paths?: string[][];
  clusters?: string[][];
  nodes?: any[];
}

export interface StreamProgress {
  currentNode: string;
  message: string;
  thinkingSteps: string[];
  evidenceFound: number;
  routing?: { brain: string; intent: string };
  graphData?: GraphData;
  activeTool?: { name: string; input: any };
  toolResults?: { tool: string; output: any }[];
  candidates?: any[];
}

export interface RunProgressDisplayProps {
  streamProgress?: StreamProgress | null;
  streamingText?: string;
  isLoading?: boolean;
  startTime?: number | null;
  run?: Run | null;
}

// ---------------------------------------------------------------------------
// deriveStreamProgress — reconstructs StreamProgress from a Run
// ---------------------------------------------------------------------------

export function deriveStreamProgress(run: Run | null): StreamProgress | null {
  if (!run || ['completed', 'failed', 'cancelled', 'queued'].includes(run.status)) {
    return null;
  }

  const progress: StreamProgress = {
    currentNode: 'router',
    message: 'Processing...',
    thinkingSteps: [],
    evidenceFound: 0,
    toolResults: [],
    candidates: [],
  };

  for (const event of run.events) {
    switch (event.type) {
      case 'routing':
        progress.routing = { brain: event.mode, intent: event.intent };
        progress.message = `Routing to ${event.mode} (${event.intent})...`;
        progress.currentNode = 'router';
        progress.thinkingSteps.push(`Request routed to ${event.mode}`);
        break;

      case 'progress':
        progress.currentNode = event.node;
        progress.message = event.message;
        break;

      case 'thinking':
        progress.thinkingSteps.push(event.content);
        break;

      case 'graph_analysis':
        progress.graphData = event.data;
        progress.thinkingSteps.push('Graph structure analyzed.');
        break;

      case 'evidence':
        progress.evidenceFound += event.count;
        break;

      case 'tool_call':
        progress.activeTool = { name: event.tool, input: event.input };
        progress.currentNode = 'execute';
        progress.message = `Executing ${event.tool}...`;
        progress.thinkingSteps.push(
          `Calling **${event.tool}**(${JSON.stringify(event.input).slice(0, 80)}...)`,
        );
        break;

      case 'tool_result': {
        const output = event.output;
        let summary = JSON.stringify(output).slice(0, 100);

        if (event.tool === 'predict_properties' && output.valid) {
          summary = `MW: ${output.MolWt}, LogP: ${output.LogP}, QED: ${output.QED}`;
          const existing = progress.candidates!.findIndex((c: any) => c.smiles === output.smiles);
          if (existing >= 0) progress.candidates![existing] = { ...progress.candidates![existing], properties: output };
          else progress.candidates!.push({ smiles: output.smiles, properties: output });
        } else if (event.tool === 'check_toxicity' && output.valid) {
          summary = output.clean ? 'Clean (no alerts)' : `${output.alert_count} alert(s)`;
          const existing = progress.candidates!.findIndex((c: any) => c.smiles === output.smiles);
          if (existing >= 0) progress.candidates![existing] = { ...progress.candidates![existing], toxicity: output };
          else progress.candidates!.push({ smiles: output.smiles, toxicity: output });
        } else if (event.tool === 'verify_spectrum' && output.valid) {
          summary = `Match: ${output.match_score != null ? (output.match_score * 100).toFixed(0) + '%' : 'N/A'}, ${output.peak_count} peaks observed`;
        } else if (event.tool === 'search_literature') {
          summary = `Found ${output.total_results} passages`;
        }

        progress.thinkingSteps.push(`Result: ${summary}`);
        progress.message = 'Reasoning about results...';
        progress.currentNode = 'think';
        progress.activeTool = undefined;
        progress.toolResults!.push({ tool: event.tool, output });
        break;
      }

      case 'grounding':
        progress.thinkingSteps.push(
          `Grounding: "${event.claim.slice(0, 40)}..." → ${event.status} (${(event.confidence * 100).toFixed(0)}%)`,
        );
        break;

      case 'chunk':
        break;
    }
  }

  return progress;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunProgressDisplay({
  streamProgress: streamProgressProp,
  streamingText: streamingTextProp,
  isLoading: isLoadingProp,
  startTime: startTimeProp,
  run,
}: RunProgressDisplayProps) {
  const isRunBased = run != null;
  const isLoading = isRunBased
    ? run != null && !['completed', 'failed', 'cancelled', 'queued'].includes(run.status)
    : (isLoadingProp ?? false);
  const startTime = isRunBased ? (run?.startedAt ?? null) : (startTimeProp ?? null);
  const streamProgress = isRunBased ? deriveStreamProgress(run) : (streamProgressProp ?? null);

  const streamingText = isRunBased
    ? run.events
        .filter((e): e is Extract<typeof e, { type: 'chunk' }> => e.type === 'chunk')
        .map((e) => e.content)
        .join('')
    : (streamingTextProp ?? '');

  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (isLoading && startTime) {
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setElapsedSeconds(0);
    }
  }, [isLoading, startTime]);

  if (!isLoading || !streamProgress) return null;

  return (
    <div className="flex gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-accent/30 bg-gradient-to-br from-accent/20 to-accent/10">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
      </div>
      <div className="max-w-[80%]">
        <div className="rounded-2xl rounded-bl-sm border border-accent/20 bg-card px-4 py-3.5 space-y-3">
          {/* Routing Indicator */}
          {streamProgress.routing && (
            <div className="flex items-center gap-2.5 pb-2.5 border-b border-border/50">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
                {streamProgress.routing.brain === 'navigator' ? (
                  <Search className="h-3.5 w-3.5 text-accent" />
                ) : streamProgress.routing.brain === 'cortex' ? (
                  <Brain className="h-3.5 w-3.5 text-accent" />
                ) : streamProgress.routing.brain.includes('moe') ? (
                  <Network className="h-3.5 w-3.5 text-blue-500" />
                ) : (
                  <BookOpen className="h-3.5 w-3.5 text-primary" />
                )}
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-foreground">
                  {streamProgress.routing.brain === 'navigator' ? 'Deep Discovery' :
                    streamProgress.routing.brain === 'cortex' ? 'Research Cortex' :
                      streamProgress.routing.brain.includes('moe') ? 'MoE Supervisor' : 'Librarian'}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {streamProgress.routing.intent.replace(/_/g, ' ')}
                </span>
              </div>
            </div>
          )}

          {/* Processing Header with Elapsed Time */}
          <div className="flex items-center justify-between pb-2 border-b border-border/30">
            <div className="text-xs font-medium text-foreground">
              Processing Query
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>{elapsedSeconds}s</span>
            </div>
          </div>

          {/* Current Action */}
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-2.5 w-2.5 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent"></span>
            </div>
            <span className="text-xs font-medium text-accent break-words">{streamProgress.message}</span>
          </div>

          {/* Graph Analysis Card */}
          {streamProgress.graphData && (
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
              <div className="flex items-center gap-2 mb-2 text-primary">
                <Share2 className="h-3.5 w-3.5" />
                <span className="text-[11px] font-semibold">Knowledge Graph Insight</span>
              </div>
              <div className="text-[11px] text-foreground/80 leading-relaxed">
                {streamProgress.graphData.summary || "Analyzing network structure..."}
              </div>
              {streamProgress.graphData.clusters && streamProgress.graphData.clusters.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {streamProgress.graphData.clusters.slice(0, 3).map((cluster, i) => (
                    <span key={i} className="inline-flex items-center rounded-full bg-background/50 border border-primary/10 px-1.5 py-0.5 text-[9px] text-primary/80">
                      {cluster.slice(0, 3).join(", ")}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Thinking Log */}
          {streamProgress.thinkingSteps.length > 0 && (
            <div className="rounded-lg bg-zinc-950/50 p-2.5 font-mono text-[10px]">
              <div className="max-h-[120px] overflow-y-auto space-y-1 custom-scrollbar">
                {streamProgress.thinkingSteps.map((step, i) => (
                  <div key={i} className="flex gap-2 text-zinc-400">
                    <span className="shrink-0 text-accent/40">{'>'}</span>
                    <span className="leading-tight">{step}</span>
                  </div>
                ))}
                <div className="h-2 w-1.5 animate-pulse bg-accent/50 rounded-sm" />
              </div>
            </div>
          )}

          {/* Streaming Response */}
          {streamingText && (
            <div className="mt-3 rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground mb-1.5">Generating Response...</div>
              <div className="text-sm text-foreground whitespace-pre-wrap font-serif leading-relaxed">
                {streamingText}
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent" />
              </div>
            </div>
          )}

          {/* Evidence Counter */}
          {streamProgress.evidenceFound > 0 && (
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground pt-1.5 border-t border-border/50">
              <Search className="h-3 w-3 text-primary" />
              <span>Found <span className="font-medium text-foreground">{streamProgress.evidenceFound}</span> relevant sources</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
