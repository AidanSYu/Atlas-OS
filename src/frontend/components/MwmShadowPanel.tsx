'use client';

import React, { useMemo, useState } from 'react';
import { AlertTriangle, Loader2, Play, ShieldAlert, Sparkles } from 'lucide-react';
import { api, type MwmShadowReplayResponse } from '@/lib/api';

/**
 * Synthetic reflow oven demo data.
 * Mirrors `_generate_reflow_demo` in the plugin so the demo narrative is
 * consistent across the Python self-test and the UI shadow-mode button.
 */
function generateReflowDemo(): number[] {
  const n = 500;
  const rng = mulberry32(42);
  const values: number[] = [];
  for (let t = 0; t < n; t++) {
    const base = 240.0 + 3.0 * Math.sin((2.0 * Math.PI * t) / 60.0);
    const noise = gaussian(rng) * 0.5;
    let drift = 0;
    if (t >= 350 && t < 400) drift = (5.0 * (t - 350)) / 50.0;
    else if (t >= 400) drift = 5.0;
    let spike = 0;
    if (t === 420) spike = 25.0;
    else if (t === 421) spike = 12.0;
    values.push(base + noise + drift + spike);
  }
  return values;
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand: () => number): number {
  const u1 = Math.max(rand(), 1e-9);
  const u2 = rand();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

interface ChartProps {
  values: number[];
  thresholdHigh?: number | null;
  thresholdLow?: number | null;
  mwmFlagged: number[];
  thresholdBreaches: number[];
  firstMwmAlert?: number | null;
  firstThresholdAlert?: number | null;
}

function ReplayChart({
  values,
  thresholdHigh,
  thresholdLow,
  mwmFlagged,
  thresholdBreaches,
  firstMwmAlert,
  firstThresholdAlert,
}: ChartProps) {
  const width = 960;
  const height = 260;
  const pad = { top: 16, right: 16, bottom: 24, left: 48 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const { min, max } = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const v of values) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    if (thresholdHigh != null) hi = Math.max(hi, thresholdHigh);
    if (thresholdLow != null) lo = Math.min(lo, thresholdLow);
    const pad = (hi - lo) * 0.05 || 1;
    return { min: lo - pad, max: hi + pad };
  }, [values, thresholdHigh, thresholdLow]);

  const xFor = (i: number) => pad.left + (i / Math.max(1, values.length - 1)) * innerW;
  const yFor = (v: number) => pad.top + (1 - (v - min) / (max - min)) * innerH;

  const path = useMemo(() => {
    if (values.length === 0) return '';
    return values
      .map((v, i) => `${i === 0 ? 'M' : 'L'}${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`)
      .join(' ');
  }, [values, min, max]);

  const flaggedSet = useMemo(() => new Set(mwmFlagged), [mwmFlagged]);
  const breachSet = useMemo(() => new Set(thresholdBreaches), [thresholdBreaches]);

  return (
    <svg width={width} height={height} className="w-full h-auto">
      <rect x={0} y={0} width={width} height={height} fill="transparent" />
      {thresholdHigh != null && (
        <line
          x1={pad.left}
          x2={pad.left + innerW}
          y1={yFor(thresholdHigh)}
          y2={yFor(thresholdHigh)}
          stroke="currentColor"
          strokeDasharray="4 4"
          className="text-destructive opacity-70"
          strokeWidth={1}
        />
      )}
      {thresholdLow != null && (
        <line
          x1={pad.left}
          x2={pad.left + innerW}
          y1={yFor(thresholdLow)}
          y2={yFor(thresholdLow)}
          stroke="currentColor"
          strokeDasharray="4 4"
          className="text-destructive opacity-70"
          strokeWidth={1}
        />
      )}
      <path d={path} fill="none" className="text-foreground" stroke="currentColor" strokeWidth={1.2} />
      {Array.from(flaggedSet).map((i) => (
        <circle key={`mwm-${i}`} cx={xFor(i)} cy={yFor(values[i])} r={2.5}
                className="text-warning" fill="currentColor" opacity={0.8} />
      ))}
      {Array.from(breachSet).map((i) => (
        <circle key={`br-${i}`} cx={xFor(i)} cy={yFor(values[i])} r={3.5}
                className="text-destructive" fill="currentColor" opacity={0.9} />
      ))}
      {firstMwmAlert != null && (
        <line x1={xFor(firstMwmAlert)} x2={xFor(firstMwmAlert)}
              y1={pad.top} y2={pad.top + innerH}
              className="text-warning" stroke="currentColor" strokeWidth={1.5} opacity={0.8} />
      )}
      {firstThresholdAlert != null && (
        <line x1={xFor(firstThresholdAlert)} x2={xFor(firstThresholdAlert)}
              y1={pad.top} y2={pad.top + innerH}
              className="text-destructive" stroke="currentColor" strokeWidth={1.5} opacity={0.8} />
      )}
      <text x={pad.left} y={12} className="fill-muted-foreground" fontSize={10}>
        {max.toFixed(1)}
      </text>
      <text x={pad.left} y={pad.top + innerH + 16} className="fill-muted-foreground" fontSize={10}>
        {min.toFixed(1)}
      </text>
    </svg>
  );
}

export function MwmShadowPanel() {
  const [values, setValues] = useState<number[]>([]);
  const [thresholdHigh, setThresholdHigh] = useState<string>('250');
  const [thresholdLow, setThresholdLow] = useState<string>('235');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MwmShadowReplayResponse | null>(null);

  const loadSynthetic = () => {
    setValues(generateReflowDemo());
    setResult(null);
    setError(null);
  };

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const resp = await api.runMwmShadowReplay({
        values,
        threshold_high: thresholdHigh === '' ? null : Number(thresholdHigh),
        threshold_low: thresholdLow === '' ? null : Number(thresholdLow),
      });
      setResult(resp);
      if (!resp.ok) setError(resp.error || 'Replay returned ok=false');
    } catch (exc: any) {
      setError(exc?.message ?? String(exc));
    } finally {
      setRunning(false);
    }
  };

  const hasData = values.length > 0;
  const advance = result?.advance_warning_points ?? null;
  const advanceColor =
    advance != null && advance > 0
      ? 'text-accent'
      : advance != null && advance <= 0
        ? 'text-destructive'
        : 'text-muted-foreground';

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-accent" />
            Shadow-Mode Replay
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Replay a sensor trace through the MWM and compare its anomaly flags
            to a traditional PLC threshold alarm. Reports the advance warning.
          </p>
        </div>
        <button
          onClick={loadSynthetic}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted/50"
          disabled={running}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Load synthetic reflow
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Threshold high</span>
          <input
            value={thresholdHigh}
            onChange={(e) => setThresholdHigh(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 font-mono"
            disabled={running}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Threshold low</span>
          <input
            value={thresholdLow}
            onChange={(e) => setThresholdLow(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1 font-mono"
            disabled={running}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Samples loaded</span>
          <div className="rounded border border-border bg-muted/30 px-2 py-1 font-mono">
            {values.length}
          </div>
        </label>
      </div>

      <button
        onClick={run}
        disabled={!hasData || running}
        className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs text-accent-foreground disabled:opacity-50"
      >
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
        {running ? 'Replaying…' : 'Run shadow replay'}
      </button>

      {error && (
        <div className="flex items-start gap-2 rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {hasData && (
        <ReplayChart
          values={values}
          thresholdHigh={thresholdHigh === '' ? null : Number(thresholdHigh)}
          thresholdLow={thresholdLow === '' ? null : Number(thresholdLow)}
          mwmFlagged={result?.mwm_flagged_indices ?? []}
          thresholdBreaches={result?.threshold_breach_indices ?? []}
          firstMwmAlert={result?.first_mwm_alert}
          firstThresholdAlert={result?.first_threshold_alert}
        />
      )}

      {result?.ok && (
        <div className="grid grid-cols-4 gap-3 text-xs">
          <Metric label="First MWM alert" value={result.first_mwm_alert ?? '—'} />
          <Metric label="First threshold" value={result.first_threshold_alert ?? '—'} />
          <Metric
            label="Advance warning"
            value={advance != null ? `${advance} pts` : '—'}
            className={advanceColor}
          />
          <Metric label="Backend" value={result.backend_used ?? '—'} />
        </div>
      )}

      {result?.summary && (
        <p className="text-xs text-muted-foreground border-l-2 border-accent/50 pl-3">
          {result.summary}
        </p>
      )}

      {result?.narration && (
        <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
          <div className="text-[10px] uppercase tracking-wide text-accent mb-1">
            Orchestrator narration
          </div>
          <p className="text-sm leading-relaxed text-foreground">{result.narration}</p>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  className = '',
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="rounded border border-border bg-muted/20 p-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`text-sm font-mono ${className}`}>{value}</div>
    </div>
  );
}
