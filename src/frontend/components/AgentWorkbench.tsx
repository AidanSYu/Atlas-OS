'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal, Activity, FileText, ShieldCheck, Loader2, GitMerge, Brain, CheckCircle2, MapPin } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Run } from '@/stores/runStore';
import { deriveStreamProgress } from './chat/RunProgressDisplay';

interface StreamProgress {
    currentNode: string;
    message: string;
    thinkingSteps: string[];
    evidenceFound: number;
    routing?: { brain: string; intent: string };
    graphData?: any;
}

interface AgentWorkbenchProps {
    streamProgress?: StreamProgress | null;
    streamingText?: string;
    isLoading?: boolean;
    run?: Run | null;
}

export function AgentWorkbench({
    streamProgress: streamProgressProp,
    streamingText: streamingTextProp,
    isLoading: isLoadingProp,
    run,
}: AgentWorkbenchProps) {
    const isRunBased = run != null;
    const streamProgress = isRunBased ? deriveStreamProgress(run) : (streamProgressProp ?? null);
    const streamingText = isRunBased
        ? run.events
            .filter((e): e is Extract<typeof e, { type: 'chunk' }> => e.type === 'chunk')
            .map((e) => e.content)
            .join('')
        : (streamingTextProp ?? '');
    const isLoading = isRunBased
        ? run != null && !['completed', 'failed', 'cancelled', 'queued'].includes(run.status)
        : (isLoadingProp ?? false);
    const terminalEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll the terminal to the bottom as new thoughts stream in
    useEffect(() => {
        terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [streamProgress?.thinkingSteps]);

    if (!isLoading && !streamProgress && !streamingText) {
        return (
            <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center bg-card/30">
                <div className="rounded-2xl bg-surface/50 p-6 mb-4">
                    <Terminal className="h-10 w-10 text-muted-foreground/40" />
                </div>
                <p className="font-serif text-lg text-foreground/60">Agent Workbench Idle</p>
                <p className="mt-2 text-xs text-muted-foreground max-w-[250px]">
                    Start a query in the MoE chat to watch the Swarm agents actively research, verify, and write in real-time.
                </p>
            </div>
        );
    }

    return (
        <div className="flex h-full w-full flex-col overflow-hidden bg-card/30 border-l border-border/50">
            <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border/50 bg-background/50 px-4">
                <Activity className="h-4 w-4 text-blue-500" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Live Agent Telemetry
                </span>
                {isLoading && <Loader2 className="ml-auto h-4 w-4 animate-spin text-blue-500" />}
            </div>

            <div className="flex flex-1 flex-col overflow-hidden p-4 gap-4">
                {/* Top: Current State / Routing */}
                <div className="shrink-0 flex flex-col gap-2 p-3 rounded-lg border border-border/50 bg-surface/40">
                    <div className="flex items-center gap-2 mb-1">
                        <MapPin className="h-3.5 w-3.5 text-accent" />
                        <span className="text-xs font-medium text-foreground">Current State</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <div className="text-[10px] uppercase text-muted-foreground mb-1">Active Node</div>
                            <div className="flex items-center gap-1.5 text-sm text-foreground">
                                <Brain className="h-4 w-4 text-primary" />
                                <span className="font-medium capitalize">{streamProgress?.currentNode || 'Waiting...'}</span>
                            </div>
                        </div>
                        {streamProgress?.routing && (
                            <div>
                                <div className="text-[10px] uppercase text-muted-foreground mb-1">Intent</div>
                                <div className="flex items-center gap-1.5 text-sm text-accent">
                                    <GitMerge className="h-4 w-4" />
                                    <span className="font-medium">{streamProgress.routing.intent}</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Middle: Terminal Output & Thoughts */}
                <div className="flex-1 flex flex-col min-h-0 rounded-lg border border-border/50 bg-zinc-950 text-zinc-300 font-mono text-xs shadow-inner">
                    <div className="flex items-center justify-between shrink-0 px-3 py-1.5 border-b border-white/10 bg-white/5">
                        <div className="flex items-center gap-2">
                            <Terminal className="h-3.5 w-3.5 text-zinc-400" />
                            <span className="text-zinc-400 font-sans text-xs">Swarm Activity Log</span>
                        </div>
                        <div className="flex items-center gap-3">
                            {streamProgress && streamProgress.evidenceFound > 0 && (
                                <div className="flex items-center gap-1 text-success">
                                    <ShieldCheck className="h-3 w-3" />
                                    <span>{streamProgress.evidenceFound} sources</span>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-3 space-y-2">
                        {streamProgress?.thinkingSteps.map((step, idx) => (
                            <div key={idx} className="flex gap-2">
                                <span className="text-zinc-500 select-none">{`>`}</span>
                                <span className={
                                    step.includes('Grounding audit:') ? 'text-emerald-400' :
                                        step.includes('Error') ? 'text-red-400' :
                                            step.includes('Plan initialized') ? 'text-blue-400' :
                                                'text-zinc-300'
                                }>
                                    {step}
                                </span>
                            </div>
                        ))}
                        {streamProgress?.message && (
                            <div className="flex gap-2 text-zinc-400 animate-pulse">
                                <span className="select-none">{`>`}</span>
                                <span>{streamProgress.message}</span>
                            </div>
                        )}
                        <div ref={terminalEndRef} />
                    </div>
                </div>

                {/* Bottom: Live Draft preview */}
                {(streamingText || (streamProgress && ['writer', 'hypothesis'].includes(streamProgress.currentNode))) && (
                    <div className="shrink-0 h-1/3 flex flex-col rounded-lg border border-blue-500/30 bg-blue-500/5 overflow-hidden">
                        <div className="flex items-center gap-2 px-3 py-2 border-b border-blue-500/20 bg-blue-500/10">
                            <FileText className="h-4 w-4 text-blue-500" />
                            <span className="text-xs font-medium text-blue-500">Live Workspace Draft</span>
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 text-sm text-foreground/90 prose-sm p-4">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {streamingText || '*Agent is preparing to write...*'}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
