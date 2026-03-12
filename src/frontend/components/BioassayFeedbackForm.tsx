/**
 * BioassayFeedbackForm.tsx
 *
 * Stage 7 (FEEDBACK) — Experimental result submission form.
 * Collects generic bioassay results and updates the knowledge graph.
 */

import React, { useState } from 'react';
import type { CandidateArtifact, BioassayResult } from '../lib/discovery-types';
import { useDiscoveryStore } from '../stores/discoveryStore';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface BioassayFeedbackFormProps {
  hit: CandidateArtifact;
  epochId: string;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FeedbackFormData {
  resultName: string;
  resultValue: string;
  unit: string;
  passed: boolean;
  notes: string;
}

interface SubmitStatus {
  type: 'idle' | 'submitting' | 'success' | 'error';
  message?: string;
}

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------

async function submitFeedback(
  hitId: string,
  epochId: string,
  data: FeedbackFormData
): Promise<{ status: string; updated_node_ids: string[] }> {
  const response = await fetch('/api/discovery/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      hit_id: hitId,
      epoch_id: epochId,
      result_name: data.resultName,
      result_value: parseFloat(data.resultValue) || 0,
      unit: data.unit,
      passed: data.passed,
      notes: data.notes,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `Error ${response.status}`);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * CandidatePreview: Condensed view of the approved candidate.
 */
function CandidatePreview({ hit }: { hit: CandidateArtifact }): JSX.Element {
  return (
    <div className="candidate-preview">
      <h4 className="preview-heading">Approved Candidate</h4>
      <div className="preview-content">
        <div className="preview-rank">Hit #{hit.rank}</div>
        <div className="preview-score">Score: {hit.score.toFixed(2)}</div>
        {typeof hit.renderData === 'string' && (
          <code className="preview-data">{hit.renderData}</code>
        )}
      </div>
    </div>
  );
}

/**
 * SuccessView: Shown after successful submission.
 */
function SuccessView({
  onRunAnotherCycle,
  onViewGraph,
}: {
  onRunAnotherCycle: () => void;
  onViewGraph: () => void;
}): JSX.Element {
  return (
    <div className="feedback-success">
      <div className="success-icon">✓</div>
      <h3 className="success-title">Feedback Recorded</h3>
      <p className="success-message">Knowledge graph updated.</p>

      <div className="success-actions">
        <button
          className="btn btn-primary btn-cycle"
          onClick={onRunAnotherCycle}
          title="Fork a new epoch and start another generation cycle"
        >
          Run another generation cycle →
        </button>
        <button
          className="btn btn-secondary btn-graph"
          onClick={onViewGraph}
          title="View the updated knowledge graph"
        >
          View updated knowledge graph
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function BioassayFeedbackForm({ hit, epochId }: BioassayFeedbackFormProps): JSX.Element {
  const [formData, setFormData] = useState<FeedbackFormData>({
    resultName: '',
    resultValue: '',
    unit: '',
    passed: true,
    notes: '',
  });
  const [submitStatus, setSubmitStatus] = useState<SubmitStatus>({ type: 'idle' });

  const submitExperimentalResult = useDiscoveryStore((state) => state.submitExperimentalResult);
  const forkEpoch = useDiscoveryStore((state) => state.forkEpoch);
  const switchToEpoch = useDiscoveryStore((state) => state.switchToEpoch);
  const advanceToStage = useDiscoveryStore((state) => state.advanceToStage);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }));
  };

  const handleToggleChange = (passed: boolean) => {
    setFormData((prev) => ({ ...prev, passed }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.resultName.trim() || !formData.resultValue.trim()) {
      setSubmitStatus({
        type: 'error',
        message: 'Please fill in Result Name and Result Value',
      });
      return;
    }

    setSubmitStatus({ type: 'submitting' });

    try {
      // Submit to backend
      const response = await submitFeedback(hit.id, epochId, formData);

      // Create bioassay result for store
      const result: BioassayResult = {
        id: crypto.randomUUID(),
        hitId: hit.id,
        epochId,
        resultName: formData.resultName,
        resultValue: parseFloat(formData.resultValue) || 0,
        unit: formData.unit,
        passed: formData.passed,
        notes: formData.notes,
        submittedAt: Date.now(),
      };

      // Update store
      submitExperimentalResult(hit.id, result);

      setSubmitStatus({ type: 'success' });
    } catch (err: any) {
      setSubmitStatus({
        type: 'error',
        message: err.message || 'Failed to submit feedback',
      });
    }
  };

  const handleRunAnotherCycle = () => {
    // Fork new epoch at Stage 2 with updated graph context
    const newEpochId = forkEpoch(
      epochId,
      'New cycle with updated graph from experimental feedback',
      {}, // Keep same target params
      2   // Start at Stage 2 (GENERATE)
    );
    // Switch to the new epoch
    switchToEpoch(newEpochId);
  };

  const handleViewGraph = () => {
    // Advance to Stage 7 (knowledge graph view)
    advanceToStage(7);
  };

  if (submitStatus.type === 'success') {
    return (
      <SuccessView
        onRunAnotherCycle={handleRunAnotherCycle}
        onViewGraph={handleViewGraph}
      />
    );
  }

  return (
    <article className="bioassay-feedback-form" data-epoch-id={epochId} data-hit-id={hit.id}>
      <header className="feedback-header">
        <h2 className="feedback-title">Experimental Feedback</h2>
        <p className="feedback-subtitle">
          Stage 7: Submit bioassay results to update the knowledge graph
        </p>
      </header>

      <CandidatePreview hit={hit} />

      <form className="feedback-form" onSubmit={handleSubmit}>
        <div className="form-grid">
          {/* Result Name */}
          <div className="form-field">
            <label htmlFor="resultName" className="field-label">
              Result Name <span className="required">*</span>
            </label>
            <input
              type="text"
              id="resultName"
              name="resultName"
              value={formData.resultName}
              onChange={handleInputChange}
              placeholder="e.g., IC50, Cell Viability, Binding Affinity"
              className="field-input"
              required
            />
          </div>

          {/* Result Value */}
          <div className="form-field">
            <label htmlFor="resultValue" className="field-label">
              Result Value <span className="required">*</span>
            </label>
            <input
              type="number"
              id="resultValue"
              name="resultValue"
              value={formData.resultValue}
              onChange={handleInputChange}
              placeholder="e.g., 42.5"
              className="field-input"
              step="any"
              required
            />
          </div>

          {/* Unit */}
          <div className="form-field">
            <label htmlFor="unit" className="field-label">
              Unit
            </label>
            <input
              type="text"
              id="unit"
              name="unit"
              value={formData.unit}
              onChange={handleInputChange}
              placeholder="e.g., μM, %, nM"
              className="field-input"
            />
          </div>

          {/* Pass/Fail Toggle */}
          <div className="form-field">
            <label className="field-label">Test Result</label>
            <div className="toggle-group">
              <button
                type="button"
                className={`toggle-btn ${formData.passed ? 'active pass' : ''}`}
                onClick={() => handleToggleChange(true)}
              >
                ✓ Pass
              </button>
              <button
                type="button"
                className={`toggle-btn ${!formData.passed ? 'active fail' : ''}`}
                onClick={() => handleToggleChange(false)}
              >
                ✗ Fail
              </button>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="form-field full-width">
          <label htmlFor="notes" className="field-label">
            Notes
          </label>
          <textarea
            id="notes"
            name="notes"
            value={formData.notes}
            onChange={handleInputChange}
            placeholder="Additional observations, experimental conditions, or notes..."
            className="field-textarea"
            rows={4}
          />
        </div>

        {/* Error message */}
        {submitStatus.type === 'error' && (
          <div className="form-error">{submitStatus.message}</div>
        )}

        {/* Submit button */}
        <div className="form-actions">
          <button
            type="submit"
            className="btn btn-primary btn-submit"
            disabled={submitStatus.type === 'submitting'}
          >
            {submitStatus.type === 'submitting' ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      </form>
    </article>
  );
}

export default BioassayFeedbackForm;
