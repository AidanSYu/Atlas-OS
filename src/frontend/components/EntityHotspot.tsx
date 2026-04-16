'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { getApiBase } from '@/lib/api';
import type { DomainSchema } from '../lib/discovery-types';

// Module-level LRU cache for SVG preview blob URLs.
// Keyed by entity string. Entries are { url, refCount } so we only
// revoke when no mounted component references the URL.
const previewCache = new Map<string, { url: string; refCount: number }>();
const MAX_CACHE = 64;

function acquirePreview(entity: string, url: string): string {
  const existing = previewCache.get(entity);
  if (existing) {
    existing.refCount++;
    return existing.url;
  }
  // Evict oldest if at capacity
  if (previewCache.size >= MAX_CACHE) {
    let evictKey: string | null = null;
    previewCache.forEach((entry, key) => {
      if (!evictKey && entry.refCount <= 0) evictKey = key;
    });
    if (evictKey) {
      const evicted = previewCache.get(evictKey);
      if (evicted) URL.revokeObjectURL(evicted.url);
      previewCache.delete(evictKey);
    }
  }
  previewCache.set(entity, { url, refCount: 1 });
  return url;
}

function releasePreview(entity: string): void {
  const entry = previewCache.get(entity);
  if (entry) {
    entry.refCount = Math.max(0, entry.refCount - 1);
  }
}

export type EntityHotspotType = 'smiles' | 'alloy' | 'generic';

export interface EntityHotspotProps {
  entity: string;
  entityType: EntityHotspotType;
  domain?: DomainSchema;
  children: React.ReactNode;
}

export function EntityHotspot({ entity, entityType, children }: EntityHotspotProps) {
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const icon = entityType === 'smiles' ? '⬡' : '⚙';

  // Fetch SVG preview for smiles on hover (debounced, cached)
  useEffect(() => {
    if (entityType !== 'smiles' || !tooltipVisible || !entity.trim()) return;

    // Check cache first
    const cached = previewCache.get(entity);
    if (cached) {
      cached.refCount++;
      setPreviewUrl(cached.url);
      setPreviewError(false);
      return () => {
        releasePreview(entity);
      };
    }

    setPreviewError(false);
    let cancelled = false;

    // Debounce 350ms to prevent network spam on fast scroll
    const timer = setTimeout(() => {
      const url = `${getApiBase()}/api/domain/render?data=${encodeURIComponent(entity)}&type=molecule_2d`;
      fetch(url)
        .then((res) => {
          if (!res.ok) throw new Error('Render failed');
          return res.blob();
        })
        .then((blob) => {
          if (cancelled) return;
          const objectUrl = URL.createObjectURL(blob);
          const finalUrl = acquirePreview(entity, objectUrl);
          setPreviewUrl(finalUrl);
        })
        .catch(() => {
          if (!cancelled) setPreviewError(true);
        });
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      releasePreview(entity);
      setPreviewUrl(null);
    };
  }, [entityType, entity, tooltipVisible]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      const el = containerRef.current;
      if (el && !el.contains(e.target as Node)) setDropdownOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dropdownOpen]);

  // Close dropdown on Escape
  useEffect(() => {
    if (!dropdownOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDropdownOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [dropdownOpen]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(entity);
    setDropdownOpen(false);
  }, [entity]);

  const handleRunPropertyScreen = useCallback(() => {
    console.log('[EntityHotspot] Run Property Screen', { entity, entityType });
    setDropdownOpen(false);
  }, [entity, entityType]);

  const handleAddToCandidateList = useCallback(() => {
    console.log('[EntityHotspot] Add to Candidate List', { entity, entityType });
    setDropdownOpen(false);
  }, [entity, entityType]);

  const handleFindSimilarInCorpus = useCallback(() => {
    console.log('[EntityHotspot] Find Similar in Corpus', { entity, entityType });
    setDropdownOpen(false);
  }, [entity, entityType]);

  return (
    <span
      ref={containerRef}
      className="relative inline cursor-pointer border-b border-primary-500/70 text-inherit"
      onMouseEnter={() => setTooltipVisible(true)}
      onMouseLeave={() => setTooltipVisible(false)}
      onClick={(e) => {
        e.stopPropagation();
        setDropdownOpen((open) => !open);
      }}
    >
      <span className="mr-0.5 align-middle" aria-hidden>
        {icon}
      </span>
      {children}

      {/* Hover tooltip */}
      {tooltipVisible && (
        <span
          className="absolute left-0 top-full z-50 mt-1 block pt-1"
          role="tooltip"
        >
          <span className="block rounded border border-neutral-600 bg-neutral-800 p-2 shadow-lg">
            {entityType === 'smiles' ? (
              <>
                {previewError && (
                  <span className="block text-xs text-amber-400">Preview unavailable</span>
                )}
                {previewUrl && (
                  <img
                    src={previewUrl}
                    alt="Structure preview"
                    width={128}
                    height={128}
                    className="block rounded bg-white"
                  />
                )}
                {!previewUrl && !previewError && (
                  <span className="block h-32 w-32 animate-pulse rounded bg-neutral-700 text-xs text-neutral-400">
                    Loading…
                  </span>
                )}
              </>
            ) : (
              <code className="block max-w-xs break-all rounded bg-neutral-900 px-2 py-1 font-mono text-sm text-neutral-200">
                {entity}
              </code>
            )}
          </span>
        </span>
      )}

      {/* Click dropdown */}
      {dropdownOpen && (
        <div
          ref={dropdownRef}
          className="absolute left-0 top-full z-50 mt-1 min-w-[12rem] rounded border border-neutral-600 bg-neutral-800 py-1 shadow-lg"
          role="menu"
        >
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-700"
            onClick={handleRunPropertyScreen}
          >
            Run Property Screen
          </button>
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-700"
            onClick={handleAddToCandidateList}
          >
            Add to Candidate List
          </button>
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-700"
            onClick={handleFindSimilarInCorpus}
          >
            Find Similar in Corpus
          </button>
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-700"
            onClick={handleCopy}
          >
            Copy
          </button>
        </div>
      )}
    </span>
  );
}
