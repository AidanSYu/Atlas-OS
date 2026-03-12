/**
 * SpectroscopyArtifact.tsx
 *
 * Spectroscopy validation artifact for Stage 6 (SPECTROSCOPY_VALIDATION).
 * Displays predicted vs. observed peaks with a spectrum chart.
 *
 * This is a presentation component — no local validation logic.
 * All verdicts come from the validation prop.
 */

import React from 'react';
import type {
    SpectroscopyValidation,
    SpectroscopyPeak,
    PeakMatch,
    SpectroscopyVerdict,
} from '../lib/discovery-types';
import { useDiscoveryStore } from '../stores/discoveryStore';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SpectroscopyArtifactProps {
    validation: SpectroscopyValidation;
}

// ---------------------------------------------------------------------------
// Helper Functions
// ---------------------------------------------------------------------------

/**
 * Get verdict display configuration.
 */
function getVerdictConfig(verdict: SpectroscopyVerdict): {
    icon: string;
    label: string;
    className: string;
} {
    switch (verdict) {
        case 'full_match':
            return { icon: '✓', label: 'FULL MATCH', className: 'verdict-full' };
        case 'partial_match':
            return { icon: '⚠', label: 'PARTIAL MATCH', className: 'verdict-partial' };
        case 'no_match':
            return { icon: '✗', label: 'NO MATCH', className: 'verdict-no-match' };
        case 'no_prediction_available':
            return { icon: '—', label: 'NO PREDICTION AVAILABLE', className: 'verdict-none' };
        default:
            return { icon: '?', label: 'UNKNOWN', className: 'verdict-unknown' };
    }
}

/**
 * Format peak position for display.
 */
function formatPeak(peak: SpectroscopyPeak): string {
    const assignment = peak.assignment ? ` (${peak.assignment})` : '';
    return `δ ${peak.position.toFixed(2)}${assignment}`;
}

/**
 * Format observed peak or show "NOT FOUND".
 */
function formatObserved(match: PeakMatch): { text: string; status: 'matched' | 'missing' } {
    if (match.observed) {
        const deviation = match.deviation ? ` (Δ${match.deviation > 0 ? '+' : ''}${match.deviation.toFixed(2)})` : '';
        return {
            text: `${formatPeak(match.observed)}${deviation}`,
            status: 'matched',
        };
    }
    return { text: 'NOT FOUND', status: 'missing' };
}

/**
 * LTTB (Largest-Triangle-Three-Buckets) downsampling.
 * Reduces a large array of peaks to at most `threshold` visually
 * representative points, preserving extremes and visual shape.
 * This prevents the SVG from creating tens of thousands of DOM nodes.
 */
const MAX_SVG_PEAKS = 500;

function downsampleLTTB(peaks: SpectroscopyPeak[], threshold: number = MAX_SVG_PEAKS): SpectroscopyPeak[] {
    if (peaks.length <= threshold) return peaks;

    const sorted = [...peaks].sort((a, b) => a.position - b.position);
    const sampled: SpectroscopyPeak[] = [];
    const bucketSize = (sorted.length - 2) / (threshold - 2);

    // Always keep the first point
    sampled.push(sorted[0]);

    for (let i = 0; i < threshold - 2; i++) {
        const bucketStart = Math.floor((i) * bucketSize) + 1;
        const bucketEnd = Math.min(Math.floor((i + 1) * bucketSize) + 1, sorted.length - 1);

        // Average of the *next* bucket (used as the reference triangle vertex)
        const nextBucketStart = Math.floor((i + 1) * bucketSize) + 1;
        const nextBucketEnd = Math.min(Math.floor((i + 2) * bucketSize) + 1, sorted.length - 1);
        let avgX = 0, avgY = 0, count = 0;
        for (let j = nextBucketStart; j < nextBucketEnd; j++) {
            avgX += sorted[j].position;
            avgY += sorted[j].intensity;
            count++;
        }
        if (count > 0) { avgX /= count; avgY /= count; }

        const prev = sampled[sampled.length - 1];
        let maxArea = -1;
        let maxIdx = bucketStart;

        for (let j = bucketStart; j < bucketEnd; j++) {
            // Triangle area with previous selected point and next-bucket average
            const area = Math.abs(
                (prev.position - avgX) * (sorted[j].intensity - prev.intensity) -
                (prev.position - sorted[j].position) * (avgY - prev.intensity)
            ) * 0.5;
            if (area > maxArea) {
                maxArea = area;
                maxIdx = j;
            }
        }

        sampled.push(sorted[maxIdx]);
    }

    // Always keep the last point
    sampled.push(sorted[sorted.length - 1]);
    return sampled;
}

/**
 * Calculate scaling for the chart.
 */
function calculateChartDimensions(
    observedPeaks: SpectroscopyPeak[],
    predictedPeaks: SpectroscopyPeak[]
): {
    minX: number;
    maxX: number;
    maxY: number;
} {
    const allPeaks = [...observedPeaks, ...predictedPeaks];
    if (allPeaks.length === 0) {
        return { minX: 0, maxX: 10, maxY: 1 };
    }

    const positions = allPeaks.map((p) => p.position);
    const intensities = allPeaks.map((p) => p.intensity);

    const minX = Math.min(...positions);
    const maxX = Math.max(...positions);
    const maxY = Math.max(...intensities, 1);

    // Add padding
    const padding = (maxX - minX) * 0.1 || 1;
    return {
        minX: minX - padding,
        maxX: maxX + padding,
        maxY: maxY * 1.1,
    };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * SpectrumChart: Minimal SVG line chart for spectroscopy data.
 */
function SpectrumChart({
    observedPeaks,
    predictedPeaks,
    matches,
}: {
    observedPeaks: SpectroscopyPeak[];
    predictedPeaks: SpectroscopyPeak[];
    matches: PeakMatch[];
}): JSX.Element {
    const svgWidth = 600;
    const svgHeight = 200;
    const padding = { top: 10, right: 20, bottom: 30, left: 50 };
    const chartWidth = svgWidth - padding.left - padding.right;
    const chartHeight = svgHeight - padding.top - padding.bottom;

    // Downsample large peak arrays to prevent DOM crash.
    // Use full arrays for dimension calc (preserves axis range),
    // but render only downsampled points.
    const { minX, maxX, maxY } = calculateChartDimensions(observedPeaks, predictedPeaks);
    const dsObserved = React.useMemo(() => downsampleLTTB(observedPeaks), [observedPeaks]);
    const dsPredicted = React.useMemo(() => downsampleLTTB(predictedPeaks), [predictedPeaks]);

    // Scale functions
    const scaleX = (x: number): number => {
        return padding.left + ((x - minX) / (maxX - minX)) * chartWidth;
    };
    const scaleY = (y: number): number => {
        return padding.top + chartHeight - (y / maxY) * chartHeight;
    };

    // Generate observed peaks path (smooth curve approximation)
    const generateObservedPath = (): string => {
        if (dsObserved.length === 0) return '';

        // Sort peaks by position (already sorted by LTTB, but ensure)
        const sorted = [...dsObserved].sort((a, b) => a.position - b.position);
        
        // Create a simple line connecting peaks
        let path = `M ${scaleX(sorted[0].position)} ${scaleY(0)}`;
        sorted.forEach((peak) => {
            path += ` L ${scaleX(peak.position)} ${scaleY(0)}`;
            path += ` L ${scaleX(peak.position)} ${scaleY(peak.intensity)}`;
            path += ` L ${scaleX(peak.position)} ${scaleY(0)}`;
        });
        
        return path;
    };

    // X-axis ticks
    const xTicks = 5;
    const tickValues = Array.from({ length: xTicks + 1 }, (_, i) => 
        minX + (maxX - minX) * (i / xTicks)
    );

    return (
        <div className="spectrum-chart-container">
            <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="spectrum-chart"
                preserveAspectRatio="xMidYMid meet"
            >
                {/* Grid lines */}
                {tickValues.map((tick, i) => (
                    <line
                        key={`grid-${i}`}
                        x1={scaleX(tick)}
                        y1={padding.top}
                        x2={scaleX(tick)}
                        y2={padding.top + chartHeight}
                        stroke="var(--border-subtle)"
                        strokeWidth={1}
                        strokeDasharray="2,2"
                    />
                ))}

                {/* X-axis */}
                <line
                    x1={padding.left}
                    y1={padding.top + chartHeight}
                    x2={padding.left + chartWidth}
                    y2={padding.top + chartHeight}
                    stroke="var(--text-muted)"
                    strokeWidth={1}
                />

                {/* Y-axis */}
                <line
                    x1={padding.left}
                    y1={padding.top}
                    x2={padding.left}
                    y2={padding.top + chartHeight}
                    stroke="var(--text-muted)"
                    strokeWidth={1}
                />

                {/* X-axis label */}
                <text
                    x={padding.left + chartWidth / 2}
                    y={svgHeight - 5}
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize={12}
                >
                    Chemical Shift (ppm)
                </text>

                {/* Y-axis label */}
                <text
                    x={15}
                    y={padding.top + chartHeight / 2}
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize={12}
                    transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}
                >
                    Intensity
                </text>

                {/* Observed peaks (solid bars) — downsampled */}
                {dsObserved.map((peak, i) => (
                    <line
                        key={`obs-${i}`}
                        x1={scaleX(peak.position)}
                        y1={scaleY(0)}
                        x2={scaleX(peak.position)}
                        y2={scaleY(peak.intensity)}
                        stroke="var(--spectrum-observed)"
                        strokeWidth={2}
                    />
                ))}

                {/* Predicted peaks (outlined/dashed bars) — downsampled */}
                {dsPredicted.map((peak, i) => (
                    <line
                        key={`pred-${i}`}
                        x1={scaleX(peak.position)}
                        y1={scaleY(0)}
                        x2={scaleX(peak.position)}
                        y2={scaleY(peak.intensity)}
                        stroke="var(--spectrum-predicted)"
                        strokeWidth={2}
                        strokeDasharray="4,2"
                    />
                ))}

                {/* X-axis ticks */}
                {tickValues.map((tick, i) => (
                    <text
                        key={`tick-${i}`}
                        x={scaleX(tick)}
                        y={padding.top + chartHeight + 15}
                        textAnchor="middle"
                        fill="var(--text-muted)"
                        fontSize={10}
                    >
                        {tick.toFixed(1)}
                    </text>
                ))}
            </svg>

            {/* Legend */}
            <div className="spectrum-legend">
                <span className="legend-item">
                    <span className="legend-color observed" />
                    Observed
                </span>
                {predictedPeaks.length > 0 && (
                    <span className="legend-item">
                        <span className="legend-color predicted" />
                        Predicted
                    </span>
                )}
            </div>
        </div>
    );
}

/**
 * PeakTable: Two-column table of predicted vs observed peaks.
 */
function PeakTable({ matches, missing }: { matches: PeakMatch[]; missing: SpectroscopyPeak[] }): JSX.Element {
    return (
        <div className="peak-table-container">
            <div className="peak-columns">
                <div className="peak-column">
                    <h4 className="column-header">Predicted Signal</h4>
                    <ul className="peak-list">
                        {matches.map((match, i) => (
                            <li key={`pred-${i}`} className="peak-item">
                                {formatPeak(match.predicted)}
                            </li>
                        ))}
                        {missing.map((peak, i) => (
                            <li key={`miss-${i}`} className="peak-item missing">
                                {formatPeak(peak)}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="peak-column">
                    <h4 className="column-header">Observed Signal</h4>
                    <ul className="peak-list">
                        {matches.map((match, i) => {
                            const { text, status } = formatObserved(match);
                            return (
                                <li key={`obs-${i}`} className={`peak-item ${status}`}>
                                    {text}
                                    <span className={`match-indicator ${match.matched ? 'pass' : 'fail'}`}>
                                        {match.matched ? '✓ match' : '✗ missing'}
                                    </span>
                                </li>
                            );
                        })}
                        {missing.map((_, i) => (
                            <li key={`miss-obs-${i}`} className="peak-item missing">
                                NOT FOUND
                                <span className="match-indicator fail">✗ missing</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
}

/**
 * VerdictBox: Color-coded verdict display.
 */
function VerdictBox({
    verdict,
    verdictText,
}: {
    verdict: SpectroscopyVerdict;
    verdictText: string;
}): JSX.Element {
    const config = getVerdictConfig(verdict);

    return (
        <div className={`verdict-box ${config.className}`}>
            <div className="verdict-header">
                <span className="verdict-icon">{config.icon}</span>
                <span className="verdict-label">VERDICT: {config.label}</span>
            </div>
            <p className="verdict-text">{verdictText}</p>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function SpectroscopyArtifact({ validation }: SpectroscopyArtifactProps): JSX.Element {
    const advanceToStage = useDiscoveryStore((state) => state.advanceToStage);
    const hasPrediction = validation.predictedPeaks.length > 0;

    const handleProceedToStage7 = () => {
        advanceToStage(7);
    };

    const handleFlagForReevaluation = () => {
        // Placeholder: In a full implementation, this would set a flag
        console.log('Flagged for re-evaluation:', validation.id);
    };

    const handleExportReport = () => {
        const report = JSON.stringify(validation, null, 2);
        const blob = new Blob([report], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `spectroscopy_validation_${validation.id.slice(0, 8)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    return (
        <article className="spectroscopy-artifact" data-validation-id={validation.id}>
            {/* Header */}
            <header className="validation-header">
                <h3 className="validation-title">SPECTROSCOPY VALIDATION</h3>
                <div className="validation-meta">
                    <span className="meta-item">Hit: {validation.hitId}</span>
                    <span className="meta-separator">·</span>
                    <span className="meta-item">Run: #{validation.runId.slice(0, 4)}</span>
                </div>
            </header>

            {/* Chart Section */}
            <div className="validation-chart-section">
                {hasPrediction ? (
                    <SpectrumChart
                        observedPeaks={validation.observedPeaks}
                        predictedPeaks={validation.predictedPeaks}
                        matches={validation.matches}
                    />
                ) : (
                    <div className="no-prediction-notice">
                        <p className="notice-title">No prediction available</p>
                        <p className="notice-text">
                            Upload will be processed when NMR predictor is configured.
                        </p>
                        {validation.observedPeaks.length > 0 && (
                            <>
                                <p className="notice-subtitle">Observed peaks only:</p>
                                <SpectrumChart
                                    observedPeaks={validation.observedPeaks}
                                    predictedPeaks={[]}
                                    matches={[]}
                                />
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* Peak Table */}
            <PeakTable matches={validation.matches} missing={validation.missing} />

            {/* Verdict Box */}
            <VerdictBox verdict={validation.verdict} verdictText={validation.verdictText} />

            {/* Footer Actions */}
            <footer className="validation-footer">
                <button
                    className="btn btn-primary"
                    onClick={handleProceedToStage7}
                    title="Proceed to experimental feedback stage"
                >
                    Proceed to Stage 7: Feedback Loop
                </button>
                <button
                    className="btn btn-secondary"
                    onClick={handleFlagForReevaluation}
                    title="Flag this result for re-evaluation or synthesis review"
                >
                    Flag for Re-evaluation
                </button>
                <button
                    className="btn btn-tertiary"
                    onClick={handleExportReport}
                    title="Download validation report as JSON"
                >
                    Export Validation Report
                </button>
            </footer>
        </article>
    );
}

export default SpectroscopyArtifact;
