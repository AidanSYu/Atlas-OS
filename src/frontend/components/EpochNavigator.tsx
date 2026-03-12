'use client';

import { useCallback, useMemo, useState } from 'react';
import type { Epoch } from '../lib/discovery-types';
import { STAGE_LABELS } from '../lib/discovery-types';
import { useDiscoveryStore } from '../stores/discoveryStore';

function shortId(id: string): string {
  return id.slice(0, 8);
}

// ---------------------------------------------------------------------------
// EpochBreadcrumb
// ---------------------------------------------------------------------------

export interface EpochBreadcrumbProps {
  onViewTree?: () => void;
}

export function EpochBreadcrumb({ onViewTree }: EpochBreadcrumbProps) {
  const epochs = useDiscoveryStore((s) => s.epochs);
  const activeEpochId = useDiscoveryStore((s) => s.activeEpochId);
  const switchToEpoch = useDiscoveryStore((s) => s.switchToEpoch);

  const ancestry = useMemo(() => {
    const chain: Epoch[] = [];
    let id: string | null = activeEpochId;
    const visited = new Set<string>();
    while (id && chain.length < 100) {
      if (visited.has(id)) break; // cycle guard
      visited.add(id);
      const epoch = epochs.get(id);
      if (!epoch) break;
      chain.push(epoch);
      id = epoch.parentEpochId;
    }
    return chain.reverse();
  }, [activeEpochId, epochs]);

  const currentEpoch = ancestry.length > 0 ? ancestry[ancestry.length - 1] : null;

  const handleBackToParent = useCallback(() => {
    if (currentEpoch?.parentEpochId) {
      switchToEpoch(currentEpoch.parentEpochId);
    }
  }, [currentEpoch?.parentEpochId, switchToEpoch]);

  if (!activeEpochId || ancestry.length === 0 || !currentEpoch) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-400">
        No active epoch
      </div>
    );
  }

  const stageLabel = STAGE_LABELS[currentEpoch.currentStage] ?? `Stage ${currentEpoch.currentStage}`;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-1 text-sm text-neutral-300">
        {ancestry.map((epoch, i) => (
          <span key={epoch.id} className="flex items-center gap-1">
            {i > 0 && <span className="text-neutral-500">→</span>}
            <span>
              Epoch {shortId(epoch.id)} ({epoch.parentEpochId == null ? 'root' : epoch.forkReason})
            </span>
          </span>
        ))}
        <span className="text-neutral-500">·</span>
        <span>
          Stage {currentEpoch.currentStage}: {stageLabel}
        </span>
      </div>
      <div className="flex gap-2">
        {currentEpoch.parentEpochId && (
          <button
            type="button"
            onClick={handleBackToParent}
            className="rounded border border-neutral-600 bg-neutral-800 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-700"
          >
            ← Back to parent
          </button>
        )}
        <button
          type="button"
          onClick={onViewTree}
          className="rounded border border-neutral-600 bg-neutral-800 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-700"
        >
          View tree
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EpochTreeViewer
// ---------------------------------------------------------------------------

interface TreeNode {
  epoch: Epoch;
  children: TreeNode[];
}

function buildTree(epochs: Map<string, Epoch>, rootId: string | null): TreeNode[] {
  if (!rootId) return [];
  const rootEpoch = epochs.get(rootId);
  if (!rootEpoch) return [];

  function node(epoch: Epoch, depth: number): TreeNode {
    if (depth > 100) return { epoch, children: [] }; // depth guard
    const children = Array.from(epochs.values())
      .filter((e) => e.parentEpochId === epoch.id)
      .map((e) => node(e, depth + 1));
    return { epoch, children };
  }

  return [node(rootEpoch, 0)];
}

export interface EpochTreeViewerProps {
  open: boolean;
  onClose: () => void;
}

export function EpochTreeViewer({ open, onClose }: EpochTreeViewerProps) {
  const epochs = useDiscoveryStore((s) => s.epochs);
  const rootEpochId = useDiscoveryStore((s) => s.rootEpochId);
  const activeEpochId = useDiscoveryStore((s) => s.activeEpochId);
  const switchToEpoch = useDiscoveryStore((s) => s.switchToEpoch);

  const tree = useMemo(() => buildTree(epochs, rootEpochId), [epochs, rootEpochId]);

  const handleSelectEpoch = useCallback(
    (id: string) => {
      switchToEpoch(id);
      onClose();
    },
    [switchToEpoch, onClose]
  );

  const renderNode = useCallback(
    (node: TreeNode) => {
      const { epoch } = node;
      const stageLabel = STAGE_LABELS[epoch.currentStage] ?? `Stage ${epoch.currentStage}`;
      const isActive = epoch.id === activeEpochId;
      const status = epoch.stageRuns && Object.keys(epoch.stageRuns).length > 0 ? 'complete' : 'running';

      return (
        <li key={epoch.id} className="list-none">
          <button
            type="button"
            onClick={() => handleSelectEpoch(epoch.id)}
            className={`w-full rounded px-2 py-1.5 text-left text-sm hover:bg-neutral-700 ${
              isActive ? 'bg-primary-600/30 text-primary-200' : 'text-neutral-200'
            }`}
          >
            <span className="font-mono">{shortId(epoch.id)}</span>
            <span className="mx-2 text-neutral-500">·</span>
            <span>{epoch.forkReason}</span>
            <span className="mx-2 text-neutral-500">·</span>
            <span className="text-neutral-400">{stageLabel}</span>
            <span className="ml-2 text-xs text-neutral-500">({status})</span>
          </button>
          {node.children.length > 0 && (
            <ul className="ml-4 border-l border-neutral-600 pl-2">
              {node.children.map((child) => renderNode(child))}
            </ul>
          )}
        </li>
      );
    },
    [activeEpochId, handleSelectEpoch]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label="Epoch tree"
    >
      <div className="flex max-h-[80vh] w-full max-w-md flex-col rounded-lg border border-neutral-700 bg-neutral-900 shadow-xl">
        <header className="flex items-center justify-between border-b border-neutral-700 px-4 py-3">
          <h2 className="text-lg font-semibold text-neutral-100">Epoch tree</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-neutral-400 hover:bg-neutral-700 hover:text-neutral-200"
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="flex-1 overflow-x-auto overflow-y-auto px-4 py-3">
          {tree.length === 0 ? (
            <p className="text-sm text-neutral-400">No epochs</p>
          ) : (
            <ul className="space-y-0.5">
              {tree.map((node) => renderNode(node))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EpochNavigator (composes breadcrumb + tree modal)
// ---------------------------------------------------------------------------

export function EpochNavigator() {
  const [treeOpen, setTreeOpen] = useState(false);
  return (
    <>
      <EpochBreadcrumb onViewTree={() => setTreeOpen(true)} />
      <EpochTreeViewer open={treeOpen} onClose={() => setTreeOpen(false)} />
    </>
  );
}
