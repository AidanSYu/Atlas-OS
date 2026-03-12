'use client';

import React, { useState } from 'react';
import { X, Check, Edit3, AlertTriangle } from 'lucide-react';

interface ScriptApprovalModalProps {
  script: {
    filename: string;
    code: string;
    description: string;
    requiredPackages: string[];
  };
  sessionId: string;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  onEdit: (editedCode: string) => Promise<void>;
  onClose: () => void;
}

export function ScriptApprovalModal({
  script,
  sessionId,
  onApprove,
  onReject,
  onEdit,
  onClose,
}: ScriptApprovalModalProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedCode, setEditedCode] = useState(script.code);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleApprove = async () => {
    setIsProcessing(true);
    try {
      await onApprove();
      onClose();
    } catch (err) {
      console.error('Approval failed:', err);
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    setIsProcessing(true);
    try {
      await onReject();
      onClose();
    } catch (err) {
      console.error('Rejection failed:', err);
      setIsProcessing(false);
    }
  };

  const handleEditAndExecute = async () => {
    setIsProcessing(true);
    try {
      await onEdit(editedCode);
      onClose();
    } catch (err) {
      console.error('Edit submission failed:', err);
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-card border border-border rounded-lg shadow-2xl">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between border-b border-border bg-surface/30 px-6 py-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-orange-500" />
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Script Approval Required
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {script.filename}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="rounded-lg p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Description */}
        <div className="shrink-0 border-b border-border/50 bg-surface/10 px-6 py-3">
          <p className="text-sm text-foreground/90">{script.description}</p>
          {script.requiredPackages.length > 0 && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Required packages:</span>
              <div className="flex flex-wrap gap-1">
                {script.requiredPackages.map((pkg, idx) => (
                  <span
                    key={idx}
                    className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
                  >
                    {pkg}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Code Editor */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <div className="h-full overflow-y-auto px-6 py-4">
            {isEditing ? (
              <textarea
                value={editedCode}
                onChange={(e) => setEditedCode(e.target.value)}
                className="w-full h-full min-h-[400px] resize-none rounded border border-border bg-surface/50 p-4 font-mono text-xs text-foreground focus:border-primary focus:outline-none"
                spellCheck={false}
              />
            ) : (
              <pre className="w-full h-full min-h-[400px] overflow-auto rounded border border-border bg-surface/50 p-4 font-mono text-xs text-foreground">
                <code>{script.code}</code>
              </pre>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="shrink-0 flex items-center justify-between border-t border-border bg-surface/30 px-6 py-4">
          <button
            onClick={() => setIsEditing(!isEditing)}
            disabled={isProcessing}
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-primary/10 disabled:opacity-50"
          >
            <Edit3 className="h-3.5 w-3.5" />
            {isEditing ? 'Cancel Edit' : 'Edit Script'}
          </button>

          <div className="flex items-center gap-3">
            <button
              onClick={handleReject}
              disabled={isProcessing}
              className="rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
            >
              Reject
            </button>

            {isEditing ? (
              <button
                onClick={handleEditAndExecute}
                disabled={isProcessing}
                className="flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-orange-600 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                Save & Execute
              </button>
            ) : (
              <button
                onClick={handleApprove}
                disabled={isProcessing}
                className="flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                Approve & Execute
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
