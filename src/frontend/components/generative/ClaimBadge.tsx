'use client';

import React from 'react';
import { Check, AlertTriangle, HelpCircle, Lightbulb } from 'lucide-react';

export type GroundingStatus = 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';

interface ClaimBadgeProps {
  status: GroundingStatus;
  claim?: string;
  source?: string;
  confidence?: number;
  compact?: boolean;
  onClick?: () => void;
}

const STATUS_CONFIG: Record<GroundingStatus, {
  label: string;
  color: string;
  bg: string;
  border: string;
  icon: typeof Check;
}> = {
  GROUNDED: {
    label: 'Grounded',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    icon: Check,
  },
  SUPPORTED: {
    label: 'Supported',
    color: 'text-sky-400',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/30',
    icon: Check,
  },
  UNVERIFIED: {
    label: 'Unverified',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    icon: AlertTriangle,
  },
  INFERRED: {
    label: 'Inferred',
    color: 'text-violet-400',
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/30',
    icon: Lightbulb,
  },
};

export default function ClaimBadge({ status, claim, source, confidence, compact, onClick }: ClaimBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.UNVERIFIED;
  const Icon = config.icon;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${config.bg} ${config.color} ${config.border} border cursor-default`}
        title={`${config.label}${source ? ` - ${source}` : ''}${confidence != null ? ` (${Math.round(confidence * 100)}%)` : ''}`}
      >
        <Icon className="h-2.5 w-2.5" />
        {config.label}
      </span>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`group flex items-start gap-2 rounded-lg border p-2 text-left transition-all hover:scale-[1.01] ${config.bg} ${config.border}`}
    >
      <div className={`mt-0.5 rounded-full p-1 ${config.bg} ${config.color}`}>
        <Icon className="h-3 w-3" />
      </div>
      <div className="min-w-0 flex-1">
        {claim && (
          <p className="text-xs text-foreground/90 leading-relaxed line-clamp-2">{claim}</p>
        )}
        <div className="mt-1 flex items-center gap-2">
          <span className={`text-[10px] font-medium ${config.color}`}>{config.label}</span>
          {source && (
            <span className="text-[10px] text-muted-foreground truncate">{source}</span>
          )}
          {confidence != null && (
            <span className="text-[10px] text-muted-foreground">{Math.round(confidence * 100)}%</span>
          )}
        </div>
      </div>
    </button>
  );
}
