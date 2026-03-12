/**
 * useGoldenPathPipeline — Run Hit Generation + Screen (Stage 2 → 3 → 4)
 *
 * Calls POST /api/discovery/generate-candidates (SSE), then
 * POST /api/discovery/screen (SSE), then pushes surviving_candidates
 * into the active epoch and updates the Jobs queue.
 */

import { useCallback, useRef } from 'react';
import { getApiBase } from '@/lib/api';
import { useDiscoveryStore } from '@/stores/discoveryStore';
import type { BackgroundJob, CandidateArtifact } from '@/lib/discovery-types';

export interface RunHitGenerationOptions {
  projectId: string;
  sessionId: string;
  epochId: string;
  mock?: boolean;
}

export interface RunHitGenerationResult {
  success: boolean;
  candidatesCount: number;
  error?: string;
}

/**
 * Consume an SSE stream (response from fetch), parse "data: {...}" lines,
 * and call onData for each parsed payload. Events are separated by blank lines.
 */
async function consumeSSE(
  response: Response,
  onData: (payload: Record<string, any>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';
    for (const block of blocks) {
      const line = block.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      const json = line.slice(5).trim();
      if (json === '[DONE]' || !json) continue;
      try {
        const payload = JSON.parse(json) as Record<string, any>;
        onData(payload);
      } catch {
        // ignore parse errors
      }
    }
    if (signal?.aborted) break;
  }
}

/**
 * Run the full Hit Generation + Screen pipeline and update the store.
 * Returns a promise that resolves when the pipeline completes (or fails).
 * Use the returned cancel function to abort.
 */
export function runHitGeneration(
  options: RunHitGenerationOptions,
): { promise: Promise<RunHitGenerationResult>; cancel: () => void } {
  const { projectId, sessionId, epochId, mock = false } = options;
  const abortControllerRef = { current: new AbortController() };

  const addJob = useDiscoveryStore.getState().addJob;
  const updateJob = useDiscoveryStore.getState().updateJob;
  const setCandidatesForEpoch = useDiscoveryStore.getState().setCandidatesForEpoch;

  const jobId = crypto.randomUUID();
  const runId = crypto.randomUUID();
  const job: BackgroundJob = {
    id: jobId,
    epochId,
    runId,
    label: 'Hit Generation + Screen',
    status: 'running',
    startedAt: Date.now(),
    completedAt: null,
    resultSummary: null,
    error: null,
  };
  addJob(job);

  const promise = (async (): Promise<RunHitGenerationResult> => {
    const signal = abortControllerRef.current.signal;
    const base = getApiBase();

    try {
      // ─── Step 1: Generate candidates ─────────────────────────────────────
      const genUrl = `${base}/api/discovery/generate-candidates${mock ? '?mock=true' : ''}`;
      const genRes = await fetch(genUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, epoch_id: epochId, project_id: projectId }),
        signal,
      });

      if (!genRes.ok) {
        const errText = await genRes.text();
        throw new Error(genRes.statusText || errText || 'Generate failed');
      }

      let smilesList: string[] = [];
      await consumeSSE(genRes, (payload) => {
        if (payload.type === 'candidates' && Array.isArray(payload.smiles)) {
          smilesList = payload.smiles;
        }
      }, signal);

      if (signal.aborted) {
        updateJob(jobId, { status: 'cancelled', completedAt: Date.now() });
        return { success: false, candidatesCount: 0 };
      }

      if (smilesList.length === 0) {
        updateJob(jobId, {
          status: 'completed',
          completedAt: Date.now(),
          resultSummary: 'No candidates generated.',
        });
        setCandidatesForEpoch(epochId, []);
        return { success: true, candidatesCount: 0 };
      }

      // ─── Step 2: Screen candidates ──────────────────────────────────────
      const screenRes = await fetch(`${base}/api/discovery/screen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          epoch_id: epochId,
          smiles_list: smilesList,
        }),
        signal,
      });

      if (!screenRes.ok) {
        const errText = await screenRes.text();
        throw new Error(screenRes.statusText || errText || 'Screen failed');
      }

      let surviving: CandidateArtifact[] = [];
      await consumeSSE(screenRes, (payload) => {
        if (payload.type === 'complete' && Array.isArray(payload.surviving_candidates)) {
          surviving = payload.surviving_candidates as CandidateArtifact[];
        }
      }, signal);

      if (signal.aborted) {
        updateJob(jobId, { status: 'cancelled', completedAt: Date.now() });
        return { success: false, candidatesCount: 0 };
      }

      setCandidatesForEpoch(epochId, surviving);
      updateJob(jobId, {
        status: 'completed',
        completedAt: Date.now(),
        resultSummary: `${surviving.length}/${smilesList.length} candidates passed screen.`,
      });
      return { success: true, candidatesCount: surviving.length };
    } catch (err: any) {
      const message = err?.message ?? String(err);
      updateJob(jobId, {
        status: 'failed',
        completedAt: Date.now(),
        error: message,
      });
      return { success: false, candidatesCount: 0, error: message };
    }
  })();

  const cancel = () => {
    abortControllerRef.current.abort();
  };

  return { promise, cancel };
}

/**
 * Hook that exposes runHitGeneration and whether a pipeline job is currently running.
 */
export function useGoldenPathPipeline() {
  const backgroundJobs = useDiscoveryStore((s) => s.backgroundJobs);
  const isRunning = backgroundJobs.some(
    (j) => j.label === 'Hit Generation + Screen' && j.status === 'running',
  );

  const run = useCallback((options: RunHitGenerationOptions) => {
    return runHitGeneration(options);
  }, []);

  return { runHitGeneration: run, isPipelineRunning: isRunning };
}
