'use client';

import { ShieldCheck, ShieldAlert, ShieldQuestion, Lightbulb } from 'lucide-react';

interface ClaimBadgeProps {
  status: 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';
  claim: string;
  source?: string;
  onClick?: () => void;
  size?: 'sm' | 'md' | 'lg';
}

export function ClaimBadge({ status, claim, source, onClick, size = 'md' }: ClaimBadgeProps) {
  const sizeClasses = {
    sm: 'h-2 w-2',
    md: 'h-3 w-3',
    lg: 'h-4 w-4',
  };

  const badgeConfig = {
    GROUNDED: {
      color: 'bg-success',
      icon: ShieldCheck,
      label: 'Grounded',
      description: 'Directly supported by source',
      className: 'text-success border-success/20 bg-success/10 hover:bg-success/20',
    },
    SUPPORTED: {
      color: 'bg-warning',
      icon: ShieldAlert,
      label: 'Supported',
      description: 'Paraphrased from source',
      className: 'text-warning border-warning/20 bg-warning/10 hover:bg-warning/20',
    },
    UNVERIFIED: {
      color: 'bg-destructive',
      icon: ShieldQuestion,
      label: 'Unverified',
      description: 'No matching source found',
      className: 'text-destructive border-destructive/20 bg-destructive/10 hover:bg-destructive/20',
    },
    INFERRED: {
      color: 'bg-muted-foreground',
      icon: Lightbulb,
      label: 'Inferred',
      description: 'AI synthesis/inference',
      className: 'text-muted-foreground border-border bg-muted hover:bg-muted/80',
    },
  };

  const config = badgeConfig[status];
  const Icon = config.icon;

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-all ${
        config.className
      } ${onClick ? 'cursor-pointer' : ''}`}
      title={`${config.label}: ${config.description}${source ? ` (${source})` : ''}`}
    >
      <Icon className={sizeClasses[size]} />
      <span>{config.label}</span>
    </div>
  );
}

export function ClaimDot({ status, onClick }: { status: ClaimBadgeProps['status']; onClick?: () => void }) {
  const dotConfig = {
    GROUNDED: 'bg-success',
    SUPPORTED: 'bg-warning',
    UNVERIFIED: 'bg-destructive',
    INFERRED: 'bg-muted-foreground',
  };

  return (
    <div
      onClick={onClick}
      className={`inline-block h-2 w-2 rounded-full ${dotConfig[status]} ${
        onClick ? 'cursor-pointer' : ''
      } transition-transform hover:scale-125`}
      title={status}
    />
  );
}
