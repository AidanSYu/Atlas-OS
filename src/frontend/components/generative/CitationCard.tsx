'use client';

import React from 'react';
import { FileText, ChevronRight } from 'lucide-react';
import { ClaimDot } from './ClaimBadge';

type GroundingStatus = 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';

interface CitationCardProps {
  source: string;
  page: number;
  excerpt?: string;
  relevance?: number;
  groundingStatus?: GroundingStatus;
  abstract?: string;
  keyFindings?: string[];
  onClick?: () => void;
}

export default function CitationCard({
  source,
  page,
  excerpt,
  relevance,
  groundingStatus,
  abstract,
  keyFindings,
  onClick,
}: CitationCardProps) {
  return (
    <button
      onClick={onClick}
      className="group w-full rounded-lg border border-border bg-card/50 p-3 text-left transition-all hover:border-accent/40 hover:bg-card"
    >
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 rounded-md bg-primary/10 p-1.5 text-primary">
          <FileText className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-xs font-medium text-foreground">{source}</p>
            <span className="shrink-0 rounded bg-surface px-1.5 py-0.5 text-[10px] text-muted-foreground">
              p.{page}
            </span>
          </div>

          {excerpt && (
            <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
              {excerpt}
            </p>
          )}

          <div className="mt-2 flex items-center gap-2">
            {groundingStatus && (
              <div className="flex items-center gap-1.5">
                <ClaimDot status={groundingStatus} onClick={onClick} />
                <span className="text-[10px] text-muted-foreground">{groundingStatus}</span>
              </div>
            )}
            {relevance != null && (
              <div className="flex items-center gap-1">
                <div className="h-1 w-12 overflow-hidden rounded-full bg-surface">
                  <div
                    className="h-full rounded-full bg-accent/60"
                    style={{ width: `${Math.min(100, relevance * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">{Math.round(relevance * 100)}%</span>
              </div>
            )}
          </div>

          {keyFindings && keyFindings.length > 0 && (
            <div className="mt-2 border-t border-border pt-2">
              <p className="text-[10px] font-medium text-muted-foreground mb-1">Key Findings:</p>
              <ul className="space-y-0.5">
                {keyFindings.map((finding, i) => (
                  <li key={i} className="text-[11px] text-foreground flex items-start gap-1.5">
                    <span className="text-accent mt-0.5">•</span>
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
    </button>
  );
}
