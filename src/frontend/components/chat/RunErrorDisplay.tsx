'use client';

import React from 'react';
import { AlertCircle, RotateCw, PenTool } from 'lucide-react';
import type { FailureCategory } from '@/lib/stream-adapter';

// ---------------------------------------------------------------------------
// Failure taxonomy — maps category to user-facing message + action
// ---------------------------------------------------------------------------

interface FailureConfig {
  message: string;
  action: 'retry' | 'edit';
}

const FAILURE_CONFIGS: Record<FailureCategory, FailureConfig> = {
  connectivity: {
    message: 'Cannot reach the backend. Is the server running?',
    action: 'retry',
  },
  timeout: {
    message: 'The request took too long. The backend may be overloaded.',
    action: 'retry',
  },
  stream_parse: {
    message: 'Received an unexpected response format.',
    action: 'retry',
  },
  backend_validation: {
    message: 'The backend rejected the request.',
    action: 'edit',
  },
  backend_runtime: {
    message: 'The backend encountered an error.',
    action: 'retry',
  },
  user_cancelled: {
    message: 'You stopped this run.',
    action: 'retry',
  },
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface RunErrorDisplayProps {
  category: FailureCategory | string;
  message: string;
  onRetry?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunErrorDisplay({ category, message, onRetry }: RunErrorDisplayProps) {
  const config = FAILURE_CONFIGS[category as FailureCategory] || {
    message: 'An unexpected error occurred.',
    action: 'retry' as const,
  };

  const displayMessage = message || config.message;

  return (
    <div className="flex gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-destructive/30 bg-gradient-to-br from-destructive/20 to-destructive/10">
        <AlertCircle className="h-4 w-4 text-destructive" />
      </div>
      <div className="max-w-[80%]">
        <div className="rounded-2xl rounded-bl-sm border border-destructive/20 bg-card px-4 py-3 space-y-2">
          <div className="text-sm text-foreground">{displayMessage}</div>
          <div className="flex items-center gap-3 pt-1">
            {config.action === 'retry' && onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <RotateCw className="h-3 w-3" />
                Run again
              </button>
            )}
            {config.action === 'edit' && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <PenTool className="h-3 w-3" />
                Edit your query and resubmit
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
