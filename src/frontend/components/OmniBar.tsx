'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { Command } from 'cmdk';
import { useRouter } from 'next/navigation';
import {
  Search,
  Upload,
  MessageSquare,
  Network,
  PenTool,
  Download,
  Home,
  BookOpen,
  Brain,
  Zap,
  Loader2,
  History,
  Layers,
} from 'lucide-react';
import type { ChatMode } from '@/hooks/useRunManager';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Mode metadata
// ---------------------------------------------------------------------------

const MODE_CONFIG: Record<ChatMode, { label: string; icon: typeof BookOpen; color: string; desc: string }> = {
  librarian: { label: 'Librarian', icon: BookOpen, color: 'text-primary', desc: 'Document Q&A with citations' },
  cortex: { label: 'Cortex', icon: Brain, color: 'text-accent', desc: 'Deeper grounded graph reasoning' },
  moe: { label: 'MoE', icon: Network, color: 'text-blue-500', desc: 'Expert team synthesis' },
};

const INTENT_TO_MODE: Record<string, ChatMode> = {
  SIMPLE: 'librarian',
  DEEP_DISCOVERY: 'cortex',
  BROAD_RESEARCH: 'moe',
  MULTI_STEP: 'moe',
  DISCOVERY: 'cortex',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OmniBarProps {
  projectId?: string;
  onUpload?: () => void;
  onExport?: (type: 'bibtex' | 'markdown' | 'chat') => void;
  onSwitchView?: (view: 'document' | 'editor' | 'graph' | 'chat' | 'canvas') => void;
  onSubmitQuery?: (query: string, mode: ChatMode) => void;
  onOpenRunHistory?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function looksLikeQuery(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 6) return false;
  if (trimmed.endsWith('?')) return true;
  const questionStarters = /^(what|how|why|where|when|who|which|can|does|is|are|do|find|compare|analyze|explain|predict|search|describe|tell|show|list|identify|summarize)/i;
  if (questionStarters.test(trimmed)) return true;
  // Multi-word phrases that aren't commands
  if (trimmed.split(/\s+/).length >= 3) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OmniBar({ projectId, onUpload, onExport, onSwitchView, onSubmitQuery, onOpenRunHistory }: OmniBarProps) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [detectedMode, setDetectedMode] = useState<ChatMode | null>(null);
  const [isRouting, setIsRouting] = useState(false);
  const router = useRouter();
  const routeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  // Reset state when closing
  const close = useCallback(() => {
    setOpen(false);
    setInputValue('');
    setDetectedMode(null);
    setIsRouting(false);
    if (routeTimerRef.current) clearTimeout(routeTimerRef.current);
  }, []);

  // Debounced auto-routing
  useEffect(() => {
    if (routeTimerRef.current) clearTimeout(routeTimerRef.current);

    if (!inputValue || !looksLikeQuery(inputValue) || !projectId) {
      setDetectedMode(null);
      setIsRouting(false);
      return;
    }

    setIsRouting(true);
    routeTimerRef.current = setTimeout(async () => {
      try {
        const result = await api.routeIntent(inputValue, projectId);
        setDetectedMode(INTENT_TO_MODE[result.intent] || 'librarian');
      } catch {
        setDetectedMode('librarian');
      } finally {
        setIsRouting(false);
      }
    }, 400);

    return () => {
      if (routeTimerRef.current) clearTimeout(routeTimerRef.current);
    };
  }, [inputValue, projectId]);

  const handleQuerySubmit = useCallback((mode: ChatMode) => {
    if (!inputValue.trim() || !onSubmitQuery) return;
    onSubmitQuery(inputValue.trim(), mode);
    close();
  }, [inputValue, onSubmitQuery, close]);

  const showQueryGroup = looksLikeQuery(inputValue) && projectId;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[18vh]">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
        onClick={close}
      />

      {/* Command Palette */}
      <div className="relative z-[201] w-full max-w-[640px] overflow-hidden rounded-2xl border border-border/60 bg-card/95 backdrop-blur-xl shadow-2xl shadow-black/40">
        <Command
          label="Atlas Command Surface"
          className="flex w-full flex-col bg-transparent"
          shouldFilter={!showQueryGroup}
        >
          {/* Input */}
          <div className="flex items-center gap-3 border-b border-border/50 px-4 py-3.5">
            {isRouting ? (
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
            ) : showQueryGroup ? (
              <Zap className="h-4 w-4 text-accent" />
            ) : (
              <Search className="h-4 w-4 text-muted-foreground" />
            )}
            <Command.Input
              placeholder="Ask a question or type a command..."
              className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/60"
              value={inputValue}
              onValueChange={setInputValue}
            />
            {inputValue && (
              <kbd className="hidden sm:inline-flex items-center rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ↵
              </kbd>
            )}
          </div>

          <Command.List className="max-h-[50vh] overflow-y-auto p-1.5">
            <Command.Empty className="px-4 py-8 text-center text-sm text-muted-foreground/60">
              No results found.
            </Command.Empty>

            {/* ---- Ask Atlas: query submission group ---- */}
            {showQueryGroup && (
              <Command.Group
                heading={
                  <span className="flex items-center gap-2">
                    <Zap className="h-3 w-3 text-accent" />
                    Ask Atlas
                    {detectedMode && !isRouting && (
                      <span className="ml-auto text-[10px] font-normal text-muted-foreground">
                        auto-detected
                      </span>
                    )}
                  </span>
                }
                className="mb-1"
              >
                {(['librarian', 'cortex', 'moe'] as ChatMode[]).map((mode) => {
                  const config = MODE_CONFIG[mode];
                  const Icon = config.icon;
                  const isRecommended = detectedMode === mode;
                  return (
                    <Command.Item
                      key={`ask-${mode}`}
                      value={`ask ${config.label} ${inputValue}`}
                      onSelect={() => handleQuerySubmit(mode)}
                      className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all aria-selected:bg-primary/10 ${
                        isRecommended
                          ? 'bg-primary/5 border border-primary/15'
                          : 'hover:bg-primary/5 border border-transparent'
                      }`}
                    >
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                        isRecommended ? 'bg-accent/15' : 'bg-surface'
                      }`}>
                        <Icon className={`h-4 w-4 ${config.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium ${isRecommended ? 'text-foreground' : 'text-foreground/80'}`}>
                            Run with {config.label}
                          </span>
                          {isRecommended && (
                            <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent">
                              recommended
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate">{config.desc}</div>
                      </div>
                    </Command.Item>
                  );
                })}
              </Command.Group>
            )}

            {/* ---- Views ---- */}
            {projectId && !showQueryGroup && (
              <>
                <Command.Group heading="Views" className="mb-1">
                  <CommandItem icon={BookOpen} onSelect={() => { onSwitchView?.('document'); close(); }}>
                    Documents
                  </CommandItem>
                  <CommandItem icon={PenTool} onSelect={() => { onSwitchView?.('editor'); close(); }}>
                    Editor
                  </CommandItem>
                  <CommandItem icon={Network} onSelect={() => { onSwitchView?.('graph'); close(); }}>
                    Knowledge Graph
                  </CommandItem>
                  <CommandItem icon={MessageSquare} onSelect={() => { onSwitchView?.('chat'); close(); }}>
                    Deep Chat
                  </CommandItem>
                  <CommandItem icon={Layers} onSelect={() => { onSwitchView?.('canvas'); close(); }}>
                    Canvas
                  </CommandItem>
                </Command.Group>

                <Command.Group heading="Actions" className="mb-1">
                  <CommandItem icon={Upload} onSelect={() => { onUpload?.(); close(); }}>
                    Upload Documents
                  </CommandItem>
                  <CommandItem icon={Download} onSelect={() => { onExport?.('bibtex'); close(); }}>
                    Export as BibTeX
                  </CommandItem>
                  <CommandItem icon={Download} onSelect={() => { onExport?.('markdown'); close(); }}>
                    Export as Markdown
                  </CommandItem>
                  <CommandItem icon={Download} onSelect={() => { onExport?.('chat'); close(); }}>
                    Export Chat History
                  </CommandItem>
                  {onOpenRunHistory && (
                    <CommandItem icon={History} onSelect={() => { onOpenRunHistory(); close(); }}>
                      Run History
                    </CommandItem>
                  )}
                </Command.Group>
              </>
            )}

            <Command.Group heading="Navigation">
              <CommandItem icon={Home} onSelect={() => { router.push('/'); close(); }}>
                Back to Dashboard
              </CommandItem>
            </Command.Group>
          </Command.List>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-border/50 px-4 py-2 bg-surface/30">
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground/60">
              <span><kbd className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[10px]">↑↓</kbd> navigate</span>
              <span><kbd className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[10px]">↵</kbd> select</span>
              <span><kbd className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[10px]">esc</kbd> close</span>
            </div>
            {showQueryGroup && detectedMode && !isRouting && (
              <div className="flex items-center gap-1.5 text-[11px] text-accent">
                <Zap className="h-3 w-3" />
                <span>Enter to ask with {MODE_CONFIG[detectedMode].label}</span>
              </div>
            )}
          </div>
        </Command>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CommandItem
// ---------------------------------------------------------------------------

function CommandItem({
  icon: Icon,
  children,
  onSelect,
}: {
  icon: any;
  children: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm text-foreground/80 hover:bg-primary/5 aria-selected:bg-primary/10 aria-selected:text-foreground transition-colors"
    >
      <Icon className="h-4 w-4 text-muted-foreground" />
      {children}
    </Command.Item>
  );
}
