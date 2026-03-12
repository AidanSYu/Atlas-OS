/**
 * CandidateArtifact.tsx
 *
 * Polymorphic candidate artifact card for Stage 4 (SURFACE).
 * Displays domain-agnostic hit data with domain-specific rendering.
 *
 * This is a presentation component — no local chemistry validation logic.
 * All validation state comes from the hit prop.
 */

import React, { useState } from 'react';
import type {
    CandidateArtifact,
    PredictedProperty,
    CandidateRenderType,
} from '../lib/discovery-types';
import { useDiscoveryStore } from '../stores/discoveryStore';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CandidateArtifactProps {
    hit: CandidateArtifact;
}

// ---------------------------------------------------------------------------
// Helper Functions
// ---------------------------------------------------------------------------

/**
 * Get score badge color based on score value.
 * Green > 0.8, yellow 0.5–0.8, red < 0.5
 */
function getScoreBadgeClass(score: number): string {
    if (score > 0.8) return 'score-high';
    if (score >= 0.5) return 'score-medium';
    return 'score-low';
}

/**
 * Get human-readable label for render type.
 */
function getRenderTypeLabel(renderType: CandidateRenderType): string {
    switch (renderType) {
        case 'molecule_2d':
            return '2D Structure';
        case 'crystal_3d':
            return '3D Crystal Lattice';
        case 'polymer_chain':
            return 'Polymer Chain';
        case 'data_table':
            return 'Data Table';
        default:
            return 'Unknown';
    }
}

/**
 * Format property value with unit.
 */
function formatPropertyValue(value: number | string | boolean, unit?: string): string {
    if (typeof value === 'boolean') {
        return value ? 'Yes' : 'No';
    }
    if (unit) {
        return `${value} ${unit}`;
    }
    return String(value);
}

/**
 * Get status indicator for a predicted property.
 * Pass = checkmark, Fail = X, null/undefined = dash
 */
function getConstraintIndicator(passesConstraint: boolean | null): React.ReactNode {
    if (passesConstraint === null || passesConstraint === undefined) {
        return <span className="constraint-neutral">—</span>;
    }
    if (passesConstraint) {
        return <span className="constraint-pass">✓</span>;
    }
    return <span className="constraint-fail">✗</span>;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * StructureViewer: Renders domain-specific visual based on renderType.
 * For molecule_2d, fetches SVG from backend.
 */
function StructureViewer({ hit }: { hit: CandidateArtifact }): JSX.Element {
    const [svgUrl, setSvgUrl] = useState<string | null>(null);
    const [loadError, setLoadError] = useState(false);

    React.useEffect(() => {
        if (hit.renderType === 'molecule_2d' && typeof hit.renderData === 'string') {
            // SMILES string — fetch SVG from backend
            const smiles = encodeURIComponent(hit.renderData);
            const url = `/api/domain/render?data=${smiles}&type=molecule_2d`;
            setSvgUrl(url);
        }
    }, [hit.renderType, hit.renderData]);

    if (hit.renderType === 'molecule_2d') {
        if (loadError) {
            return (
                <div className="structure-viewer structure-error">
                    <div className="structure-placeholder">
                        <span className="structure-icon">⚗️</span>
                        <span className="structure-text">{String(hit.renderData)}</span>
                    </div>
                </div>
            );
        }

        return (
            <div className="structure-viewer">
                {svgUrl ? (
                    <img
                        src={svgUrl}
                        alt={`Molecular structure for hit ${hit.rank}`}
                        className="structure-image"
                        onError={() => setLoadError(true)}
                    />
                ) : (
                    <div className="structure-loading">Loading...</div>
                )}
            </div>
        );
    }

    // Other render types: placeholder (deferred to future implementation)
    return (
        <div className="structure-viewer structure-placeholder-container">
            <div className="structure-placeholder">
                <span className="structure-icon">📦</span>
                <span className="structure-label">{getRenderTypeLabel(hit.renderType)}</span>
                <span className="structure-text-preview">
                    {typeof hit.renderData === 'string'
                        ? hit.renderData.slice(0, 100) + (hit.renderData.length > 100 ? '...' : '')
                        : 'Data'}
                </span>
            </div>
        </div>
    );
}

/**
 * PropertiesTable: Displays predicted properties with pass/warn/fail indicators.
 */
function PropertiesTable({ 
    properties, 
    renderData 
}: { 
    properties: PredictedProperty[];
    renderData: any;
}): JSX.Element {
    return (
        <div className="properties-table-container">
            <h4 className="properties-heading">Predicted Properties</h4>
            <table className="properties-table">
                <tbody>
                    {properties.map((prop, index) => (
                        <tr key={`${prop.name}-${index}`} className="property-row">
                            <td className="property-name">{prop.name}</td>
                            <td className="property-value">
                                {formatPropertyValue(prop.value, prop.unit)}
                            </td>
                            <td className="property-constraint">
                                {getConstraintIndicator(prop.passesConstraint)}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <div className="raw-data-section">
                <span className="raw-data-label">Raw Data:</span>
                <code className="raw-data-value">
                    {typeof renderData === 'string' ? renderData : '[Data]'}
                </code>
            </div>
        </div>
    );
}

/**
 * SourceReasoning: Collapsible section showing LLM explanation.
 */
function SourceReasoning({ reasoning }: { reasoning: string }): JSX.Element {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className="source-reasoning">
            <button
                className="reasoning-toggle"
                onClick={() => setIsExpanded(!isExpanded)}
                aria-expanded={isExpanded}
            >
                <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
                Source Reasoning
            </button>
            {isExpanded && (
                <blockquote className="reasoning-text">{reasoning}</blockquote>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function CandidateArtifactCard({ hit }: CandidateArtifactProps): JSX.Element {
    const approveHit = useDiscoveryStore((state) => state.approveHit);
    const rejectHit = useDiscoveryStore((state) => state.rejectHit);
    const [isFlagged, setIsFlagged] = useState(hit.status === 'flagged');
    const [isApproving, setIsApproving] = useState(false);

    const isRejected = hit.status === 'rejected';
    const isApproved = hit.status === 'approved';

    const handleApprove = () => {
        if (isApproving || isApproved) return;
        setIsApproving(true);
        approveHit(hit.id);
    };

    const handleReject = () => {
        rejectHit(hit.id);
    };

    const handleFlag = () => {
        setIsFlagged(!isFlagged);
    };

    return (
        <article
            className={`candidate-artifact ${isRejected ? 'rejected' : ''} ${isFlagged ? 'flagged' : ''}`}
            data-hit-id={hit.id}
            data-hit-status={hit.status}
        >
            {/* Header: Rank, Score, Actions */}
            <header className="artifact-header">
                <div className="header-left">
                    <span className="rank-badge">HIT #{hit.rank}</span>
                    <span className={`score-badge ${getScoreBadgeClass(hit.score)}`}>
                        Score: {hit.score.toFixed(2)}
                    </span>
                </div>
                <div className="header-actions">
                    <button
                        className="btn btn-primary btn-approve"
                        onClick={handleApprove}
                        disabled={isRejected || isApproving || isApproved}
                        title="Approve and proceed to synthesis planning"
                    >
                        {isApproving ? 'Approving…' : isApproved ? 'Approved ✓' : 'Approve → Synthesis Plan'}
                    </button>
                    <button
                        className="btn btn-secondary btn-reject"
                        onClick={handleReject}
                        disabled={isRejected}
                        title="Reject this candidate"
                    >
                        Reject
                    </button>
                    <button
                        className={`btn btn-tertiary btn-flag ${isFlagged ? 'active' : ''}`}
                        onClick={handleFlag}
                        title="Flag for review"
                    >
                        {isFlagged ? 'Flagged' : 'Flag for Review'}
                    </button>
                </div>
            </header>

            {/* Main Content: Structure + Properties */}
            <div className="artifact-body">
                <div className="structure-section">
                    <StructureViewer hit={hit} />
                </div>
                <div className="properties-section">
                    <PropertiesTable properties={hit.properties} renderData={hit.renderData} />
                </div>
            </div>

            {/* Source Reasoning */}
            <SourceReasoning reasoning={hit.sourceReasoning} />

            {/* Footer Actions */}
            <footer className="artifact-footer">
                <button className="footer-link" title="View in knowledge graph">
                    View in Graph
                </button>
                <button className="footer-link" title="Find similar structures in corpus">
                    Find Similar in Corpus
                </button>
                <button className="footer-link" title="Export candidate data">
                    Export Data
                </button>
            </footer>

            {/* Rejected Overlay */}
            {isRejected && (
                <div className="rejected-overlay">
                    <span className="rejected-label">Rejected</span>
                </div>
            )}
        </article>
    );
}

export default CandidateArtifactCard;
