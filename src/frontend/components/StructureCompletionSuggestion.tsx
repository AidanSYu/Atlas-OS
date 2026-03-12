/**
 * StructureCompletionSuggestion — Ghost Text Renderer
 *
 * Renders a structural completion suggestion as ghost text inline with the
 * editor cursor. Uses opacity: 0.5 and var(--text-muted) to visually
 * distinguish the suggestion from authored content.
 *
 * Usage:
 *   Slot this <span> immediately after the cursor's DOM position. The consumer
 *   (the editor integration) is responsible for positioning and Tab-key
 *   acceptance via the `onAccept` callback from useStructureCompletion.
 *
 * This component is intentionally stateless — all state lives in the hook.
 */

import React from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StructureCompletionSuggestionProps {
  /** The structural suggestion text to display. If null/empty, nothing renders. */
  suggestion: string;
  /** Optional extra class names for host integration. */
  className?: string;
  /** Whether the suggestion is actively loading (shows a subtle pulse). */
  isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StructureCompletionSuggestion({
  suggestion,
  className,
  isLoading = false,
}: StructureCompletionSuggestionProps): React.ReactElement | null {
  if (!suggestion && !isLoading) return null;

  return (
    <span
      className={[
        'structure-completion-suggestion',
        isLoading ? 'structure-completion-suggestion--loading' : '',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
      aria-hidden="true"
      data-testid="structure-completion-suggestion"
      style={{
        color: 'var(--text-muted, #6b7280)',
        opacity: 0.5,
        pointerEvents: 'none',
        userSelect: 'none',
        fontStyle: 'italic',
        whiteSpace: 'pre-wrap',
      }}
    >
      {isLoading && !suggestion ? (
        <LoadingPulse />
      ) : (
        suggestion
      )}

      <style>{GHOST_TEXT_STYLES}</style>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Loading indicator (CSS-only pulse, no JS animation)
// ---------------------------------------------------------------------------

function LoadingPulse(): React.ReactElement {
  return (
    <span
      className="structure-completion-suggestion__pulse"
      aria-hidden="true"
    >
      {'\u00A0\u00A0\u00A0'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Scoped CSS (injected once via <style> tag — no external dependencies)
// ---------------------------------------------------------------------------

const GHOST_TEXT_STYLES = `
  .structure-completion-suggestion {
    display: inline;
    transition: opacity 120ms ease;
  }

  .structure-completion-suggestion--loading {
    animation: structure-completion-pulse 1.2s ease-in-out infinite;
  }

  .structure-completion-suggestion__pulse {
    display: inline-block;
    background: currentColor;
    border-radius: 2px;
    height: 0.85em;
    width: 2.4em;
    vertical-align: middle;
    opacity: 0.35;
  }

  @keyframes structure-completion-pulse {
    0%, 100% { opacity: 0.3; }
    50%       { opacity: 0.6; }
  }

  /* Tab-key hint tooltip rendered via CSS ::after — visible on focus context */
  .structure-completion-suggestion:not(.structure-completion-suggestion--loading)::after {
    content: ' [Tab]';
    font-size: 0.7em;
    opacity: 0.5;
    letter-spacing: 0.05em;
    font-style: normal;
    font-family: monospace;
  }
`;
