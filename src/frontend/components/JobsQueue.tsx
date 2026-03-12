'use client';

import React, { useEffect, useState } from 'react';
import { useDiscoveryStore } from '@/stores/discoveryStore';
import { Loader2, CheckCircle2, AlertCircle, Play, History, GitPullRequest } from 'lucide-react';
import type { BackgroundJob } from '@/lib/discovery-types';

function LiveElapsed({ startedAt }: { startedAt: number }) {
    const [elapsedStr, setElapsedStr] = useState('');

    useEffect(() => {
        const interval = setInterval(() => {
            const elapsedMs = Date.now() - startedAt;
            const s = Math.floor(elapsedMs / 1000);
            const m = Math.floor(s / 60);
            const displayS = s % 60;

            if (m > 0) {
                setElapsedStr(`${m}:${displayS.toString().padStart(2, '0')}`);
            } else {
                setElapsedStr(`0:${displayS.toString().padStart(2, '0')}`);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [startedAt]);

    return <span>{elapsedStr || '0:00'}</span>;
}

function formatElapsed(startedAt: number, completedAt: number | null) {
    if (!completedAt) return '';
    const elapsedMs = completedAt - startedAt;
    const s = Math.floor(elapsedMs / 1000);
    const m = Math.floor(s / 60);
    const displayS = s % 60;

    if (m > 0) return `${m}:${displayS.toString().padStart(2, '0')}`;
    return `0:${displayS.toString().padStart(2, '0')}`;
}

function JobRow({ job }: { job: BackgroundJob }) {
    return (
        <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-surface/30 border border-border/30 hover:bg-surface/50 transition-colors">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {job.status === 'running' && <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />}
                    {job.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                    {job.status === 'failed' && <AlertCircle className="w-3.5 h-3.5 text-red-400" />}
                    {job.status === 'queued' && <Play className="w-3.5 h-3.5 text-zinc-500" />}
                    <span className="text-xs font-semibold text-zinc-200 tracking-wide">{job.label}</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 font-mono bg-black/20 px-1.5 py-0.5 rounded border border-white/5">
                    {job.status === 'running' ? (
                        <LiveElapsed startedAt={job.startedAt} />
                    ) : (
                        <span>{formatElapsed(job.startedAt, job.completedAt)}</span>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-2 ml-5">
                <GitPullRequest className="w-3 h-3 text-zinc-600" />
                <span className="text-[10px] text-zinc-500">Epoch: {job.epochId.slice(0, 8)}</span>
                <span className="text-zinc-700 mx-1">·</span>
                <span className="text-[10px] text-zinc-500">Run: {job.runId.slice(0, 8)}</span>
            </div>

            {(job.resultSummary || job.error) && (
                <div className="mt-1 ml-5">
                    {job.resultSummary && (
                        <div className="text-[11px] text-emerald-300 bg-emerald-500/10 px-2 py-1.5 rounded text-wrap max-w-full">
                            {job.resultSummary}
                        </div>
                    )}
                    {job.error && (
                        <div className="text-[11px] text-red-300 bg-red-500/10 px-2 py-1.5 rounded flex flex-col gap-1">
                            <span className="font-semibold">{job.error}</span>
                            <button className="self-start text-[10px] text-red-400 hover:text-red-300 underline underline-offset-2">see log</button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export function JobsQueue() {
    const backgroundJobs = useDiscoveryStore((state) => state.backgroundJobs);

    // Reverse array to show newest first, limit to 5
    const displayJobs = [...backgroundJobs].reverse().slice(0, 5);

    return (
        <div className="w-full flex-1 min-h-0 flex flex-col overflow-hidden px-4 pb-4 select-none relative z-10">
            <div className="flex flex-col w-full h-full bg-card/60 rounded-xl border border-border/50 shadow-sm overflow-hidden backdrop-blur-md relative overflow-hidden">
                {/* Header */}
                <div className="flex items-center gap-2 p-3 border-b border-border/50 bg-background/50 shrink-0">
                    <History className="h-4 w-4 text-blue-500" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jobs</span>
                    <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/10 text-[10px] font-bold text-blue-400">
                        {backgroundJobs.length}
                    </span>
                </div>

                {/* List Container */}
                <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
                    {displayJobs.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-4">
                            <History className="h-8 w-8 text-muted-foreground/30 mb-2" />
                            <span className="text-xs text-muted-foreground">No active jobs</span>
                        </div>
                    ) : (
                        displayJobs.map((job) => <JobRow key={job.id} job={job} />)
                    )}
                </div>

                {/* Footer action */}
                <div className="p-2 border-t border-border/50 bg-background/30 shrink-0">
                    <button className="w-full py-1.5 rounded hover:bg-white/5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors border border-transparent hover:border-white/10 text-center">
                        View all runs
                    </button>
                </div>
            </div>
        </div>
    );
}
