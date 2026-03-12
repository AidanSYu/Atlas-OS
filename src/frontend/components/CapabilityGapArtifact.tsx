'use client';

import { useCallback, useRef, useState } from 'react';
import { getApiBase } from '../lib/api';
import type { CapabilityGap, CapabilityGapResolution } from '../lib/discovery-types';
import { STAGE_LABELS } from '../lib/discovery-types';
import { useDiscoveryStore } from '../stores/discoveryStore';

export type ResolutionMethod = CapabilityGapResolution['method'];

export interface CapabilityGapArtifactProps {
  gap: CapabilityGap;
}

function isValidUrl(s: string): boolean {
  try {
    new URL(s);
    return true;
  } catch {
    return false;
  }
}

export function CapabilityGapArtifact({ gap }: CapabilityGapArtifactProps) {
  const resolveCapabilityGap = useDiscoveryStore((s) => s.resolveCapabilityGap);

  const [selectedMethod, setSelectedMethod] = useState<ResolutionMethod | null>(null);
  const [localPath, setLocalPath] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const stageLabel = STAGE_LABELS[gap.stage] ?? `Stage ${gap.stage}`;
  const isResolved = gap.resolution !== null;

  const getResolutionConfig = useCallback((): Record<string, unknown> => {
    switch (selectedMethod) {
      case 'local_script':
        return { path: localPath.trim() };
      case 'api_endpoint':
        return { url: endpointUrl.trim() };
      case 'skip':
        return {};
      case 'plugin':
        return {};
      default:
        return {};
    }
  }, [selectedMethod, localPath, endpointUrl]);

  const canConfirm =
    selectedMethod === 'skip' ||
    (selectedMethod === 'local_script' && localPath.trim().length > 0) ||
    (selectedMethod === 'api_endpoint' && isValidUrl(endpointUrl.trim()));

  const handleConfirm = useCallback(async () => {
    if (!selectedMethod || !canConfirm) return;
    setSubmitError(null);
    setSubmitting(true);
    const config = getResolutionConfig();
    const body = { gap_id: gap.id, method: selectedMethod, config };
    try {
      const res = await fetch(`${getApiBase()}/api/tools/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail ?? res.statusText);
      }
      const resolution: CapabilityGapResolution = { method: selectedMethod, config };
      resolveCapabilityGap(gap.id, resolution);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }, [selectedMethod, canConfirm, getResolutionConfig, gap.id, resolveCapabilityGap]);

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setLocalPath(file.name);
    e.target.value = '';
  }, []);

  if (isResolved && gap.resolution) {
    return (
      <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-5">
        <header className="mb-4 flex items-center gap-2 border-b border-neutral-700 pb-3">
          <span className="text-lg font-semibold text-neutral-100">
            CAPABILITY GAP DETECTED
          </span>
          <span className="text-neutral-500">·</span>
          <span className="text-sm text-neutral-400">Run #{gap.runId.slice(0, 8)}</span>
          <span className="text-neutral-500">·</span>
          <span className="text-sm text-neutral-400">{stageLabel}</span>
        </header>
        <div className="rounded border border-emerald-700 bg-emerald-900/20 px-4 py-3 text-emerald-300">
          Resolved ✓ — {gap.resolution.method.replace('_', ' ')}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-5">
      <header className="mb-4 flex flex-wrap items-center gap-2 border-b border-neutral-700 pb-3">
        <span className="text-lg font-semibold text-neutral-100">
          CAPABILITY GAP DETECTED
        </span>
        <span className="text-neutral-500">·</span>
        <span className="text-sm text-neutral-400">Run #{gap.runId.slice(0, 8)}</span>
        <span className="text-neutral-500">·</span>
        <span className="text-sm text-neutral-400">Stage: {stageLabel}</span>
      </header>

      <div className="mb-4 rounded border border-neutral-600 bg-neutral-800/50 p-4 font-mono text-sm">
        <div className="mb-1 text-neutral-400">FUNCTION:</div>
        <div className="mb-3 text-neutral-200">{gap.requiredFunction}</div>
        <div className="mb-1 text-neutral-400">INPUT:</div>
        <pre className="mb-3 overflow-x-auto text-neutral-300">
          {JSON.stringify(gap.inputSchema, null, 2)}
        </pre>
        <div className="mb-1 text-neutral-400">OUTPUT:</div>
        <pre className="mb-3 overflow-x-auto text-neutral-300">
          {JSON.stringify(gap.outputSchema, null, 2)}
        </pre>
        {gap.standardReference && (
          <>
            <div className="mb-1 text-neutral-400">STANDARD:</div>
            <div className="text-neutral-300">{gap.standardReference}</div>
          </>
        )}
      </div>

      <p className="mb-4 text-sm text-neutral-400">How would you like to resolve this?</p>

      <div className="space-y-4">
        {/* Option A: Local script */}
        <label className="flex cursor-pointer items-start gap-3 rounded border border-neutral-600 bg-neutral-800/50 p-3 transition-colors has-[:checked]:border-primary-500 has-[:checked]:ring-1 has-[:checked]:ring-primary-500">
          <input
            type="radio"
            name="resolution"
            checked={selectedMethod === 'local_script'}
            onChange={() => setSelectedMethod('local_script')}
            className="mt-1"
          />
          <div className="flex-1">
            <span className="font-medium text-neutral-200">[ A ] Configure a local script</span>
            <p className="mt-1 text-sm text-neutral-400">
              Point Atlas to a Python executable that accepts SMILES via stdin and returns JSON.
            </p>
            {selectedMethod === 'local_script' && (
              <div className="mt-3 flex gap-2">
                <input
                  type="text"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  placeholder="Path to script or executable"
                  className="flex-1 rounded border border-neutral-600 bg-neutral-700 px-3 py-2 font-mono text-sm text-neutral-100 placeholder-neutral-500"
                />
                <input
                  ref={fileInputRef}
                  type="file"
                  className="sr-only"
                  accept=".py,.exe,*"
                  onChange={handleFileChange}
                />
                <button
                  type="button"
                  onClick={handleBrowseClick}
                  className="rounded border border-neutral-600 bg-neutral-700 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-600"
                >
                  Browse
                </button>
              </div>
            )}
          </div>
        </label>

        {/* Option B: API endpoint */}
        <label className="flex cursor-pointer items-start gap-3 rounded border border-neutral-600 bg-neutral-800/50 p-3 transition-colors has-[:checked]:border-primary-500 has-[:checked]:ring-1 has-[:checked]:ring-primary-500">
          <input
            type="radio"
            name="resolution"
            checked={selectedMethod === 'api_endpoint'}
            onChange={() => setSelectedMethod('api_endpoint')}
            className="mt-1"
          />
          <div className="flex-1">
            <span className="font-medium text-neutral-200">[ B ] Provide an API endpoint</span>
            <p className="mt-1 text-sm text-neutral-400">
              Enter a REST endpoint URL that accepts the required input and returns the expected output.
            </p>
            {selectedMethod === 'api_endpoint' && (
              <div className="mt-3">
                <input
                  type="url"
                  value={endpointUrl}
                  onChange={(e) => setEndpointUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full rounded border border-neutral-600 bg-neutral-700 px-3 py-2 font-mono text-sm text-neutral-100 placeholder-neutral-500"
                />
                {endpointUrl.trim() && !isValidUrl(endpointUrl.trim()) && (
                  <p className="mt-1 text-sm text-amber-400">Please enter a valid URL.</p>
                )}
              </div>
            )}
          </div>
        </label>

        {/* Option C: Plugin — disabled, Coming soon */}
        <div
          className="flex cursor-not-allowed items-start gap-3 rounded border border-neutral-600 bg-neutral-800/30 p-3 opacity-75"
          title="Coming soon"
        >
          <input
            type="radio"
            name="resolution"
            disabled
            className="mt-1 cursor-not-allowed"
          />
          <div className="flex-1">
            <span className="font-medium text-neutral-500">[ C ] Install a compatible plugin</span>
            <p className="mt-1 text-sm text-neutral-500">
              Browse the Atlas plugin registry (coming soon).
            </p>
            <div className="mt-2">
              <button
                type="button"
                disabled
                title="Coming soon"
                className="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-neutral-500 cursor-not-allowed"
              >
                Browse Registry
              </button>
              <span className="ml-2 text-xs text-neutral-500" title="Coming soon">
                Coming soon
              </span>
            </div>
          </div>
        </div>

        {/* Option D: Skip */}
        <label className="flex cursor-pointer items-start gap-3 rounded border border-neutral-600 bg-neutral-800/50 p-3 transition-colors has-[:checked]:border-primary-500 has-[:checked]:ring-1 has-[:checked]:ring-primary-500">
          <input
            type="radio"
            name="resolution"
            checked={selectedMethod === 'skip'}
            onChange={() => setSelectedMethod('skip')}
            className="mt-1"
          />
          <div className="flex-1">
            <span className="font-medium text-neutral-200">[ D ] Skip this screen and continue without this capability</span>
            <p className="mt-1 text-sm text-amber-400/90">
              This property will show &quot;Not evaluated&quot; on all candidate cards.
            </p>
          </div>
        </label>
      </div>

      {submitError && (
        <p className="mt-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-300" role="alert">
          {submitError}
        </p>
      )}

      <div className="mt-5">
        <button
          type="button"
          onClick={handleConfirm}
          disabled={!canConfirm || submitting}
          className="rounded-lg bg-primary-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Registering…' : 'Confirm Resolution'}
        </button>
      </div>
    </div>
  );
}
