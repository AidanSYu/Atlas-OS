'use client';

import React, { useRef, useEffect, useCallback, useMemo, useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import type { ModelRegistryResponse, ModelStatusResponse, RegistryModel } from '@/lib/api';
import type { ChatMode } from '@/hooks/useRunManager';

// Re-export for consumers that import from here
export type { ChatMode };

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CommandSurfaceProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onLoadModel?: (modelName: string) => Promise<void>;
  isLoading: boolean;
  disabled: boolean;
  chatMode: ChatMode;
  modelRegistry?: ModelRegistryResponse | null;
  modelStatus?: ModelStatusResponse | null;
  isModelSwitching?: boolean;
  streamingText?: string;
  onStopWithPartial?: (partialText: string) => void;
}

// ---------------------------------------------------------------------------
// Placeholder text per mode
// ---------------------------------------------------------------------------

const PLACEHOLDERS: Record<ChatMode, string> = {
  librarian: 'Ask about your documents...',
  cortex: 'Deep research question...',
  moe: 'Complex synthesis query...',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CommandSurface({
  value,
  onChange,
  onSubmit,
  onCancel,
  onLoadModel,
  isLoading,
  disabled,
  chatMode,
  modelRegistry,
  modelStatus,
  isModelSwitching = false,
  streamingText = '',
  onStopWithPartial,
}: CommandSurfaceProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [selectedModel, setSelectedModel] = useState('');

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 140)}px`;
    }
  }, [value]);

  const activeModel = modelStatus?.active_model ?? modelRegistry?.active?.active_model ?? '';
  const localModels = modelRegistry?.local ?? [];
  const apiModels = modelRegistry?.api ?? [];
  const hasModelChoices = localModels.length > 0 || apiModels.length > 0;
  const hasSelectableModels = localModels.length > 0 || apiModels.some((model) => model.has_key !== false);

  useEffect(() => {
    if (activeModel) {
      setSelectedModel(activeModel);
    } else {
      setSelectedModel('');
    }
  }, [activeModel]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  }, [onSubmit]);

  const handleStop = useCallback(() => {
    if (onStopWithPartial) {
      onStopWithPartial(streamingText);
    } else {
      onCancel();
    }
  }, [onCancel, onStopWithPartial, streamingText]);

  const renderModelOptionLabel = useCallback((model: RegistryModel) => {
    const prefix = model.source === 'api' ? 'API' : 'Local';
    if (model.source === 'api' && model.has_key === false) {
      return `${prefix} | ${model.name} (missing key)`;
    }
    return `${prefix} | ${model.name}`;
  }, []);

  const handleModelChange = useCallback(async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextModel = e.target.value;
    if (!nextModel) return;

    const previousModel = selectedModel;
    setSelectedModel(nextModel);

    if (!onLoadModel || nextModel === activeModel) {
      return;
    }

    try {
      await onLoadModel(nextModel);
    } catch {
      setSelectedModel(previousModel);
    }
  }, [activeModel, onLoadModel, selectedModel]);

  const placeholder = PLACEHOLDERS[chatMode];
  const modelPickerDisabled = disabled || isLoading || isModelSwitching || !hasSelectableModels;
  const selectValue = useMemo(() => {
    if (selectedModel) return selectedModel;
    if (activeModel) return activeModel;
    return '';
  }, [activeModel, selectedModel]);

  return (
    <div className="shrink-0 border-t border-border/50 bg-card/80 backdrop-blur-sm">
      <div className="relative mx-auto max-w-3xl px-4 py-3">
        <div className="mb-1.5 flex justify-end">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/50">
              Model
            </span>
            <div className="relative">
              <select
                value={selectValue}
                onChange={handleModelChange}
                disabled={modelPickerDisabled}
                className="h-8 w-40 appearance-none rounded-lg border border-border/50 bg-background/70 py-1.5 pl-3 pr-8 text-xs text-foreground outline-none transition-colors hover:border-border focus:border-border disabled:cursor-not-allowed disabled:opacity-60"
                title={activeModel ? `Active model: ${activeModel}` : 'Choose model'}
              >
                {!hasModelChoices && (
                  <option value="">No models detected</option>
                )}
                {hasModelChoices && !selectValue && (
                  <option value="">Choose model</option>
                )}
                {localModels.length > 0 && (
                  <optgroup label="Local models">
                    {localModels.map((model) => (
                      <option key={model.name} value={model.name}>
                        {renderModelOptionLabel(model)}
                      </option>
                    ))}
                  </optgroup>
                )}
                {apiModels.length > 0 && (
                  <optgroup label="API models">
                    {apiModels.map((model) => (
                      <option
                        key={model.name}
                        value={model.name}
                        disabled={model.has_key === false}
                      >
                        {renderModelOptionLabel(model)}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
                {isModelSwitching ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
                ) : (
                  <span className="text-[10px] text-muted-foreground/60">v</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-end gap-2 rounded-2xl border border-border/40 bg-surface/30 transition-all focus-within:border-border/80 focus-within:bg-surface/50">

          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 resize-none bg-transparent py-3.5 pl-4 pr-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/40"
            rows={1}
            disabled={isLoading || disabled}
          />

          <div className="flex items-center gap-1 pr-2 pb-2">
            {isLoading ? (
              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 rounded-lg bg-destructive/10 px-3 py-1.5 text-xs font-medium text-destructive transition-all hover:bg-destructive/20"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={onSubmit}
                disabled={!value.trim()}
                className={`rounded-xl p-2 transition-all ${
                  !value.trim()
                    ? 'text-muted-foreground/30'
                    : 'bg-accent text-white shadow-sm shadow-accent/20 hover:bg-accent/90'
                }`}
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="mt-1.5 flex items-center justify-between px-1">
          <span className="text-[10px] text-muted-foreground/40">
            <kbd className="font-mono">Shift+Enter</kbd> for new line
          </span>
          {!isLoading && (
            <span className="text-[10px] text-muted-foreground/40">
              <kbd className="font-mono">Ctrl+K</kbd> ask from anywhere
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
