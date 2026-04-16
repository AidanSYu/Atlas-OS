/**
 * useStructureCompletion — Stage-Aware Structural Ghost Text Hook
 *
 * Triggers structural completion suggestions (citation blocks, section headers,
 * data table placeholders) after a 2000ms pause when the cursor sits at a
 * structural boundary. Never fires mid-sentence.
 *
 * Exit-gate contract (verified at runtime):
 * - Rejects mid-sentence triggers (char before cursor not in ['.', '\n', '#', ':'])
 * - Rejects suggestions containing more than one '.' (prose continuation guard)
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getApiBase } from '../lib/api';
import { useDiscoveryStore } from '../stores/discoveryStore';
import type { StageContextBundle } from '../lib/discovery-types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StructureCompletionResult {
  suggestion: string | null;
  isLoading: boolean;
  onAccept: () => void;
}

interface SuggestStructureRequest {
  text: string;
  cursor_position: number;
  stage_context: Partial<StageContextBundle> | null;
}

interface SuggestStructureResponse {
  suggestion: string | null;
}

// ---------------------------------------------------------------------------
// Structural boundary detection
// ---------------------------------------------------------------------------

/**
 * Returns true only when the cursor is at a position where a structural
 * suggestion would be semantically meaningful.
 *
 * Boundary conditions (any one suffices):
 *   1. Cursor is at or past the end of the text.
 *   2. Text before cursor ends with a blank line (markdown paragraph break).
 *   3. Text before cursor ends with a heading line (`^#{1,6} ...`).
 *   4. Text before cursor ends with a period (sentence/paragraph end).
 *   5. Text before cursor ends with a colon (list/table introduction).
 *
 * Hard gate (short-circuit BEFORE boundary checks):
 *   The character immediately before the cursor must be one of '.', '\n',
 *   '#', or ':'. Any other character signals a mid-sentence position.
 */
export function isAtStructuralBoundary(text: string, cursor: number): boolean {
  if (cursor === 0) return false;

  const before = text.slice(0, cursor);
  const charBefore = before.at(-1) ?? '';

  // ── Hard gate: reject mid-sentence positions ──────────────────────────────
  if (!['.', '\n', '#', ':'].includes(charBefore)) return false;

  // ── Boundary condition 1: end of entire text ──────────────────────────────
  if (cursor >= text.length) return true;

  // ── Boundary condition 2: after a blank line (paragraph break) ────────────
  // Matches: ...content\n\n  or  ...content\n   \n
  if (/\n[ \t]*\n[ \t]*$/.test(before)) return true;

  // ── Boundary condition 3: cursor is right after a heading line ────────────
  // e.g. "## Introduction\n|" or the very end of a heading fragment
  if (/(?:^|\n)#{1,6} [^\n]*\n$/.test(before)) return true;
  // Also trigger when cursor sits directly after a heading with no trailing \n
  if (/(?:^|\n)#{1,6} [^\n]*$/.test(before)) return true;

  // ── Boundary condition 4: end of a sentence/paragraph (period + whitespace) ─
  if (/\.\s*$/.test(before)) return true;

  // ── Boundary condition 5: colon at end of content (list/table intro) ──────
  if (/:\s*$/.test(before)) return true;

  return false;
}

// ---------------------------------------------------------------------------
// Structural form validators
// ---------------------------------------------------------------------------

/** Matches: [Insert: ...] */
const RE_CITATION_OR_TABLE = /^\[Insert:/;

/** Matches a markdown heading (1–6 #) possibly preceded by whitespace/newlines */
const RE_HEADING = /^[\n\r\s]*#{1,6} /;

/**
 * Returns true only when the suggestion is a recognised structural element.
 *
 * Acceptance priority:
 *   1. Recognised structural prefix → accept immediately (citation, table
 *      placeholder, or section header). Dot count is irrelevant for these.
 *   2. Unknown form → apply prose-continuation guard: reject if more than
 *      one '.' appears (heuristic for multiple sentences).
 */
function isStructuralSuggestion(suggestion: string): boolean {
  const trimmed = suggestion.trimStart();

  // Explicit structural forms are always valid
  if (RE_CITATION_OR_TABLE.test(trimmed)) return true;
  if (RE_HEADING.test(suggestion)) return true;

  // Fallback prose guard for anything else
  const dotCount = (suggestion.match(/\./g) ?? []).length;
  return dotCount <= 1;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const DEBOUNCE_MS = 2000;

/**
 * @param editorText  The full current text content of the editor.
 * @param cursorPosition  Zero-based byte offset of the cursor inside editorText.
 */
export function useStructureCompletion(
  editorText: string,
  cursorPosition: number,
): StructureCompletionResult {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Read minimal stage context from discoveryStore (no selector resubscription spam)
  const epochs = useDiscoveryStore((s) => s.epochs);
  const activeEpochId = useDiscoveryStore((s) => s.activeEpochId);
  const activeEpoch = activeEpochId ? epochs.get(activeEpochId) ?? null : null;

  const fetchSuggestion = useCallback(
    async (text: string, cursor: number) => {
      // Build a minimal StageContextBundle from available store data
      const stageContext: Partial<StageContextBundle> | null = activeEpoch
        ? {
            activeEpochId,
            activeStage: activeEpoch.currentStage,
            targetParams: activeEpoch.targetParams,
            activeArtifact: null,
            focusedCandidateId: null,
            focusedCandidate: null,
            recentToolInvocations: [],
          }
        : null;

      const body: SuggestStructureRequest = {
        text,
        cursor_position: cursor,
        stage_context: stageContext,
      };

      abortRef.current = new AbortController();
      setIsLoading(true);

      try {
        const res = await fetch(`${getApiBase()}/editor/suggest-structure`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          setSuggestion(null);
          return;
        }

        const data: SuggestStructureResponse = await res.json();

        if (data.suggestion && isStructuralSuggestion(data.suggestion)) {
          setSuggestion(data.suggestion);
        } else {
          setSuggestion(null);
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.warn('[useStructureCompletion] fetch failed:', err.message);
        }
        setSuggestion(null);
      } finally {
        setIsLoading(false);
      }
    },
    [activeEpochId, activeEpoch],
  );

  useEffect(() => {
    // Clear any pending debounce + in-flight request
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (abortRef.current) abortRef.current.abort();

    // Always clear the stale suggestion on each keystroke
    setSuggestion(null);

    // Short-circuit: only proceed if cursor is at a structural boundary
    if (!isAtStructuralBoundary(editorText, cursorPosition)) return;

    debounceRef.current = setTimeout(() => {
      fetchSuggestion(editorText, cursorPosition);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [editorText, cursorPosition, fetchSuggestion]);

  const onAccept = useCallback(() => {
    // Clear suggestion and cancel any in-flight request.
    // The consumer is responsible for inserting `suggestion` into editor state.
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (abortRef.current) abortRef.current.abort();
    setSuggestion(null);
    setIsLoading(false);
  }, []);

  return { suggestion, isLoading, onAccept };
}
