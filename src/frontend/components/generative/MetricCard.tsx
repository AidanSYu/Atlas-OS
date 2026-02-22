'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: number | string;
  change?: number; // Percentage change
  unit?: string;
  color?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetricCard({ label, value, change, unit, color = 'primary' }: MetricCardProps) {
  const colorClasses = {
    primary: 'from-primary/20 to-primary/5 border-primary/20',
    accent: 'from-accent/20 to-accent/5 border-accent/20',
    success: 'from-success/20 to-success/5 border-success/20',
    warning: 'from-warning/20 to-warning/5 border-warning/20',
    destructive: 'from-destructive/20 to-destructive/5 border-destructive/20',
  };

  const valueColorClasses = {
    primary: 'text-primary',
    accent: 'text-accent',
    success: 'text-success',
    warning: 'text-warning',
    destructive: 'text-destructive',
  };

  return (
    <div className={`inline-flex flex-col gap-2 rounded-xl border bg-gradient-to-br p-4 min-w-[140px] ${colorClasses[color]}`}>
      <div className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className={`text-2xl font-semibold ${valueColorClasses[color]}`}>
        {value}
        {unit && <span className="ml-1 text-sm text-muted-foreground">{unit}</span>}
      </div>
      {change !== undefined && (
        <div className="flex items-center gap-1 text-xs">
          {change > 0 ? (
            <TrendingUp className="h-3 w-3 text-success" />
          ) : change < 0 ? (
            <TrendingDown className="h-3 w-3 text-destructive" />
          ) : (
            <Minus className="h-3 w-3 text-muted-foreground" />
          )}
          <span className={change > 0 ? 'text-success' : change < 0 ? 'text-destructive' : 'text-muted-foreground'}>
            {Math.abs(change)}%
          </span>
        </div>
      )}
    </div>
  );
}
