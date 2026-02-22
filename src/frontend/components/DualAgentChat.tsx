'use client';

import React, { useRef, useEffect, useCallback, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore, ChatMessage } from '@/stores/chatStore';
import { api, Citation, SwarmResponse, GroundingEvent } from '@/lib/api';
import {
  Send,
  Bot,
  User,
  FileText,
  Brain,
  BookOpen,
  Loader2,
  Trash2,
  AlertCircle,
  Sparkles,
  Search,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Share2,
  Shield,
  ShieldCheck,
  RotateCw,
  AlertTriangle,
  ArrowRight,
  Zap,
  Clock,
  Network,
  Lightbulb,
  PenTool,
} from 'lucide-react';
import CitationCard from './generative/CitationCard';
import { ClaimBadge, ClaimDot } from './generative/ClaimBadge';
import { ComparisonTable } from './generative/ComparisonTable';
import { MetricCard } from './generative/MetricCard';
import { AgentWorkbench } from './AgentWorkbench';
import { spring, animations } from '@/lib/design-system/motion';

type GroundingStatus = 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';

interface DualAgentChatProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex' | 'moe';
  onChatModeChange: (mode: 'librarian' | 'cortex' | 'moe') => void;
}

interface GraphData {
  summary?: string;
  paths?: string[][];
  clusters?: string[][];
  nodes?: any[];
}

interface StreamProgress {
  currentNode: string;
  message: string;
  thinkingSteps: string[];
  evidenceFound: number;
  routing?: { brain: string; intent: string };
  graphData?: GraphData;
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        em: ({ children }) => <em className="italic text-foreground/90">{children}</em>,
        h1: ({ children }) => <h1 className="text-base font-bold text-foreground mt-3 mb-1.5 font-serif">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-bold text-foreground mt-2.5 mb-1 font-serif">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold text-foreground mt-2 mb-1">{children}</h3>,
        ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="text-foreground/90">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-primary/40 pl-3 my-2 text-muted-foreground italic">{children}</blockquote>
        ),
        code: ({ className, children }) => {
          const isBlock = className?.includes('language-');
          if (isBlock) {
            return (
              <pre className="rounded-lg bg-zinc-950/50 p-3 my-2 overflow-x-auto">
                <code className="text-xs font-mono text-foreground/90">{children}</code>
              </pre>
            );
          }
          return <code className="rounded bg-surface px-1.5 py-0.5 text-xs font-mono text-accent">{children}</code>;
        },
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-xs">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-surface/50 text-muted-foreground">{children}</thead>,
        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold border-b border-border">{children}</th>,
        td: ({ children }) => <td className="px-3 py-2 border-b border-border/50">{children}</td>,
        a: ({ href, children }) => (
          <a href={href} className="text-accent underline underline-offset-2 hover:text-accent/80" target="_blank" rel="noopener noreferrer">{children}</a>
        ),
        hr: () => <hr className="my-3 border-border/50" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function GenerativeRenderer({ content }: { content: string }) {
  const tableRegex = /\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n)+)/;
  const metricRegex = /\*\*([^:]+):\*\*\s*([0-9.,]+)(%|\s*[a-zA-Z\s]+)?/g;

  const tableMatch = content.match(tableRegex);
  const metricMatches: RegExpExecArray[] = [];
  let match;
  while ((match = metricRegex.exec(content)) !== null) {
    metricMatches.push(match);
  }

  let tableConfig = null;
  if (tableMatch) {
    try {
      // Basic markdown table parser for ComparisonTable format
      const headers = tableMatch[1].split('|').map(h => h.trim()).filter(Boolean);
      const rowsRaw = tableMatch[2].trim().split('\n').filter(Boolean);
      const rows = rowsRaw.map(r => {
        const cells = r.split('|').map(c => c.trim()).filter(Boolean);
        return {
          feature: cells[0] || '',
          values: cells.slice(1).map(c => {
            if (c.toLowerCase() === 'yes' || c === '✓') return true;
            if (c.toLowerCase() === 'no' || c === '✗' || c === 'x') return false;
            if (c === '-' || c === '') return null;
            return c;
          }),
        };
      });
      // First header is typically "Feature" so slice it
      tableConfig = { headers: headers.slice(1), rows };
    } catch (e) {
      console.error('Generative UI table parser error:', e);
    }
  }

  const metricsConfig = metricMatches.map(m => ({
    label: m[1].trim(),
    value: m[2].trim(),
    unit: m[3] ? m[3].trim() : undefined,
  }));

  if (!tableConfig && metricsConfig.length === 0) {
    return <MarkdownContent content={content} />;
  }

  // Remove the tables and metrics from the markdown content so we don't duplicate
  let remainingContent = content;
  if (tableMatch) {
    remainingContent = remainingContent.replace(tableMatch[0], '');
  }
  if (metricsConfig.length > 0) {
    remainingContent = remainingContent.replace(metricRegex, '');
  }

  return (
    <div className="space-y-4">
      {remainingContent.trim() && <MarkdownContent content={remainingContent} />}

      {metricsConfig.length > 0 && (
        <div className="flex flex-wrap gap-3 mt-4">
          {metricsConfig.map((m, i) => (
            <MetricCard
              key={i}
              label={m.label}
              value={m.value}
              unit={m.unit}
              color={i % 3 === 0 ? 'primary' : i % 3 === 1 ? 'accent' : 'success'}
            />
          ))}
        </div>
      )}

      {tableConfig && (
        <div className="mt-4">
          <ComparisonTable headers={tableConfig.headers} rows={tableConfig.rows} />
        </div>
      )}
    </div>
  );
}

export default function DualAgentChat({
  onCitationClick,
  projectId,
  chatMode,
  onChatModeChange,
}: DualAgentChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const {
    librarianMessages,
    librarianInput,
    librarianSessionId,
    cortexMessages,
    cortexInput,
    cortexSessionId,
    moeMessages,
    moeInput,
    moeSessionId,
    pendingQuestion,
    pendingHypotheses,
    addLibrarianMessage,
    addCortexMessage,
    addMoeMessage,
    setLibrarianInput,
    setCortexInput,
    setMoeInput,
    clearLibrarianChat,
    clearCortexChat,
    clearMoeChat,
    setActiveProject,
    setPendingQuestion,
    setPendingHypotheses,
  } = useChatStore();

  useEffect(() => {
    setActiveProject(projectId || null);
  }, [projectId, setActiveProject]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [librarianMessages, cortexMessages, moeMessages, chatMode]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  }, [chatMode === 'librarian' ? librarianInput : chatMode === 'cortex' ? cortexInput : moeInput]);

  const [isLoading, setIsLoading] = useState(false);
  const [streamProgress, setStreamProgress] = useState<StreamProgress | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
  const [groundingMap, setGroundingMap] = useState<Map<string, GroundingEvent>>(new Map());
  const [streamingText, setStreamingText] = useState<string>('');
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const currentMessages = chatMode === 'librarian' ? librarianMessages : chatMode === 'cortex' ? cortexMessages : moeMessages;
  const currentInput = chatMode === 'librarian' ? librarianInput : chatMode === 'cortex' ? cortexInput : moeInput;
  const setCurrentInput = chatMode === 'librarian' ? setLibrarianInput : chatMode === 'cortex' ? setCortexInput : setMoeInput;
  const addMessage = chatMode === 'librarian' ? addLibrarianMessage : chatMode === 'cortex' ? addCortexMessage : addMoeMessage;

  // Consume pending question from other views (e.g. "Ask about this page")
  useEffect(() => {
    if (pendingQuestion) {
      setCurrentInput(pendingQuestion);
      setPendingQuestion(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [pendingQuestion, setPendingQuestion, setCurrentInput]);

  // Update elapsed time counter during streaming
  useEffect(() => {
    if (isLoading && startTime) {
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setElapsedSeconds(0);
    }
  }, [isLoading, startTime]);

  const handleSubmit = useCallback(async (selectedHypothesis?: string) => {
    let contentToSubmit = selectedHypothesis || currentInput;
    if (!contentToSubmit.trim() || isLoading || !projectId) return;

    const userContent = contentToSubmit.trim();
    if (!selectedHypothesis) {
      setCurrentInput('');
    }

    // Add user message to UI
    addMessage({ role: 'user', content: userContent });
    setIsLoading(true);
    setStreamProgress(null);
    setStartTime(Date.now());

    try {
      if (chatMode === 'cortex') {
        setStreamProgress({
          currentNode: 'router',
          message: 'Analyzing query...',
          thinkingSteps: [],
          evidenceFound: 0,
        });

        try {
          const abortController = new AbortController();
          abortRef.current = () => abortController.abort();

          const result = await new Promise<SwarmResponse>((resolve, reject) => {
            let finalResult: SwarmResponse | null = null;

            const handleEvent = (type: string, data: any) => {
              switch (type) {
                case 'routing':
                  setStreamProgress((prev) => ({
                    ...(prev || {
                      currentNode: 'router',
                      message: 'Routing...',
                      thinkingSteps: [],
                      evidenceFound: 0,
                    }),
                    routing: { brain: data.brain, intent: data.intent },
                    message: `Routing to ${data.brain} (${data.intent})...`,
                    thinkingSteps: prev ? [...prev.thinkingSteps, `Request routed to ${data.brain}`] : [`Request routed to ${data.brain}`],
                  }));
                  break;
                case 'progress':
                  setStreamProgress((prev) => prev ? {
                    ...prev,
                    currentNode: data.node,
                    message: data.message,
                  } : null);
                  break;
                case 'thinking':
                  setStreamProgress((prev) => prev ? {
                    ...prev,
                    thinkingSteps: [...prev.thinkingSteps, data.content],
                  } : null);
                  break;
                case 'graph_analysis':
                  setStreamProgress((prev) => prev ? {
                    ...prev,
                    graphData: data,
                    thinkingSteps: [...prev.thinkingSteps, 'Graph structure analyzed.'],
                  } : null);
                  break;
                case 'evidence':
                  setStreamProgress((prev) => prev ? {
                    ...prev,
                    evidenceFound: prev.evidenceFound + (data.count || 1),
                  } : null);
                  break;
                case 'grounding':
                  const groundingEvent = data as GroundingEvent;
                  setGroundingMap(prev => {
                    const next = new Map(prev);
                    // Key by source+page or claim hash
                    const key = groundingEvent.source ? `${groundingEvent.source}:${groundingEvent.page}` : groundingEvent.claim;
                    next.set(key, groundingEvent);
                    return next;
                  });
                  break;
                case 'chunk':
                  setStreamingText(prev => prev + data.content);
                  break;
                case 'complete':
                  setStreamingText(''); // Clear streaming text before setting final message
                  finalResult = data as SwarmResponse;
                  resolve(finalResult);
                  break;
                case 'cancelled':
                  resolve({
                    hypothesis: 'Generation was stopped by user.',
                    evidence: [],
                    reasoning_trace: ['Generation cancelled by user.'],
                    brain_used: 'navigator',
                    status: 'cancelled',
                    confidence_score: null,
                  } as any);
                  break;
                case 'error':
                  reject(new Error(data.message));
                  break;
              }
            };

            const sessionId = chatMode === 'cortex' ? cortexSessionId : librarianSessionId;
            api.streamSwarm(userContent, projectId, handleEvent, sessionId, abortController.signal)
              .catch(reject);

            setTimeout(() => { if (!finalResult) reject(new Error('Stream timeout')); }, 300000);
          });

          if (result.status !== 'cancelled') {
            addMessage({
              role: 'assistant',
              content: result.hypothesis || 'No analysis generated.',
              citations: result.evidence?.map((e: any) => ({
                source: e.source,
                page: e.page,
                relevance: e.relevance,
                text: e.excerpt,
              })),
              brainActivity: {
                brain: result.brain_used,
                trace: result.reasoning_trace || [],
                evidence: result.evidence || [],
                confidenceScore: result.confidence_score,
                iterations: result.iterations,
                contradictions: result.contradictions,
              },
            });
          }
        } catch (error: any) {
          if (error?.name === 'AbortError' || error?.message?.includes('abort')) {
            return;
          }
          setStreamProgress({
            currentNode: 'fallback',
            message: 'Processing (non-streaming)...',
            thinkingSteps: [],
            evidenceFound: 0,
          });

          const result = await api.runSwarm(userContent, projectId);
          addMessage({
            role: 'assistant',
            content: result.hypothesis || 'No analysis generated.',
            citations: result.evidence?.map((e: any) => ({
              source: e.source,
              page: e.page,
              relevance: e.relevance,
              text: e.excerpt,
            })),
            brainActivity: {
              brain: result.brain_used,
              trace: result.reasoning_trace || [],
              evidence: result.evidence || [],
              confidenceScore: result.confidence_score,
              iterations: result.iterations,
              contradictions: result.contradictions,
            },
          });
        }
      } else if (chatMode === 'moe') {
        if (!selectedHypothesis) {
          // STEP 1: Generate Hypotheses
          setStreamProgress({
            currentNode: 'supervisor',
            message: 'Analyzing query and planning approach...',
            thinkingSteps: [],
            evidenceFound: 0,
          });

          try {
            const abortController = new AbortController();
            abortRef.current = () => abortController.abort();

            const result = await new Promise<any>((resolve, reject) => {
              let hypothesesItems: any[] = [];
              const handleEvent = (type: string, data: any) => {
                switch (type) {
                  case 'routing':
                  case 'progress':
                    setStreamProgress((prev) => ({
                      ...(prev || { currentNode: 'supervisor', message: 'Routing...', thinkingSteps: [], evidenceFound: 0 }),
                      currentNode: data.node || 'supervisor',
                      message: data.message || `Executing plan (${data.intent})...`,
                    }));
                    break;
                  case 'thinking':
                    setStreamProgress((prev) => prev ? { ...prev, thinkingSteps: [...prev.thinkingSteps, data.content] } : null);
                    break;
                  case 'hypotheses':
                    hypothesesItems = data.items;
                    resolve(data);
                    break;
                  case 'cancelled':
                    resolve({ items: [], cancelled: true });
                    break;
                  case 'error':
                    reject(new Error(data.message));
                    break;
                }
              };

              api.streamMoEHypotheses(userContent, projectId, handleEvent, moeSessionId, abortController.signal)
                .catch(reject);

              setTimeout(() => { if (hypothesesItems.length === 0) reject(new Error('Stream timeout')); }, 300000);
            });

            if (!result.cancelled) {
              setPendingHypotheses(result.items);
              addMessage({
                role: 'assistant',
                content: 'I have analyzed your query and generated several distinct research hypotheses. Please select the one you would like me to investigate, or provide further instructions.',
                brainActivity: {
                  brain: 'MoE Supervisor',
                  trace: ['Generated research hypotheses.'],
                  evidence: [],
                },
              });
            }
          } catch (error: any) {
            if (error?.name === 'AbortError' || error?.message?.includes('abort')) {
              return;
            }
            console.error("MoE Hypotheses Stream Error:", error);
            // Fallback: If streaming fails or fails to generate, we just run the full MoE directly
            setStreamProgress(null);
            addMessage({
              role: 'assistant',
              content: 'Failed to generate hypotheses interactively. Proceeding with standard research...',
            });
            handleSubmit(userContent); // recursively run it again with the same content
          }
        } else {
          // STEP 2: Pursue selected hypothesis
          setPendingHypotheses(null);
          setStreamProgress({
            currentNode: 'supervisor',
            message: 'Executing MoE plan on selected hypothesis...',
            thinkingSteps: [],
            evidenceFound: 0,
          });

          try {
            const abortController = new AbortController();
            abortRef.current = () => abortController.abort();

            const result = await new Promise<any>((resolve, reject) => {
              let finalResult: any = null;

              const handleEvent = (type: string, data: any) => {
                switch (type) {
                  case 'routing':
                    setStreamProgress((prev) => ({
                      ...(prev || { currentNode: 'supervisor', message: 'Routing...', thinkingSteps: [], evidenceFound: 0 }),
                      routing: { brain: data.brain, intent: data.intent },
                      message: `Executing MoE plan (${data.intent})...`,
                      thinkingSteps: prev ? [...prev.thinkingSteps, `Plan initialized for intent: ${data.intent}`] : [`Plan initialized for intent: ${data.intent}`],
                    }));
                    break;
                  case 'progress':
                    setStreamProgress((prev) => prev ? { ...prev, currentNode: data.node, message: data.message } : null);
                    break;
                  case 'thinking':
                    setStreamProgress((prev) => prev ? { ...prev, thinkingSteps: [...prev.thinkingSteps, data.content] } : null);
                    break;
                  case 'evidence':
                    setStreamProgress((prev) => prev ? { ...prev, evidenceFound: prev.evidenceFound + (data.count || 1) } : null);
                    break;
                  case 'grounding':
                    setStreamProgress((prev) => prev ? { ...prev, thinkingSteps: [...prev.thinkingSteps, `Grounding audit: ${data.verdict}`] } : null);
                    break;
                  case 'chunk':
                    setStreamingText((prev) => prev + data.content);
                    break;
                  case 'complete':
                    setStreamingText('');
                    finalResult = data;
                    resolve(finalResult);
                    break;
                  case 'cancelled':
                    resolve({
                      hypothesis: 'Generation was stopped by user.',
                      evidence: [],
                      reasoning_trace: ['Generation cancelled by user.'],
                      brain_used: 'moe_supervisor',
                      status: 'cancelled',
                      confidence_score: null,
                    });
                    break;
                  case 'error':
                    reject(new Error(data.message));
                    break;
                }
              };

              // Send the selected hypothesis to be pursued
              api.streamMoE(userContent, projectId, handleEvent, moeSessionId, abortController.signal)
                .catch(reject);

              setTimeout(() => { if (!finalResult) reject(new Error('Stream timeout')); }, 300000);
            });

            if (result.status !== 'cancelled') {
              addMessage({
                role: 'assistant',
                content: result.final_answer || result.hypothesis || 'No answer generated.',
                citations: result.evidence?.map((e: any) => ({
                  source: e.source,
                  page: e.page,
                  relevance: e.relevance,
                  text: e.text || e.excerpt,
                })),
                brainActivity: {
                  brain: 'MoE Supervisor',
                  trace: result.reasoning_trace || [],
                  evidence: result.evidence || [],
                  confidenceScore: result.confidence_score,
                },
              });
            }
          } catch (error: any) {
            if (error?.name === 'AbortError' || error?.message?.includes('abort')) {
              return;
            }
            console.error("MoE Execute Stream Error:", error);
            setStreamProgress({
              currentNode: 'fallback',
              message: 'Processing MoE (non-streaming)...',
              thinkingSteps: [],
              evidenceFound: 0,
            });

            const result = await api.runMoE(userContent, projectId);
            addMessage({
              role: 'assistant',
              content: result.hypothesis || result.final_answer || 'No analysis generated.',
              citations: result.evidence?.map((e: any) => ({
                source: e.source,
                page: e.page,
                relevance: e.relevance,
                text: e.excerpt || e.text,
              })),
              brainActivity: {
                brain: 'MoE Supervisor',
                trace: result.reasoning_trace || [],
                evidence: result.evidence || [],
                confidenceScore: result.confidence_score,
              },
            });
          }
        }
      } else {
        const abortController = new AbortController();
        abortRef.current = () => abortController.abort();

        setStreamProgress({
          currentNode: 'librarian',
          message: 'Searching document library...',
          thinkingSteps: [],
          evidenceFound: 0,
        });

        const response = await api.chat(userContent, projectId, abortController.signal);
        addMessage({
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
          librarianMetadata: {
            reasoning: response.reasoning,
            relationships: response.relationships,
            contextSources: response.context_sources,
          },
        });
      }
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.message?.includes('abort')) {
        // User cancelled - expected, not an error
        return;
      }
      console.error('Chat error:', error);
      addMessage({
        role: 'assistant',
        content: 'I encountered an error processing your request. Please try again.',
      });
    } finally {
      setIsLoading(false);
      setStreamProgress(null);
      abortRef.current = null;
    }
  }, [currentInput, isLoading, projectId, chatMode, addMessage, setCurrentInput, pendingHypotheses, setPendingHypotheses, moeSessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleHypothesisSelect = (hypothesis: string) => {
    handleSubmit(hypothesis);
  };

  const clearChat = () => {
    if (chatMode === 'cortex') clearCortexChat();
    else if (chatMode === 'moe') {
      clearMoeChat();
      setPendingHypotheses(null);
    }
    else clearLibrarianChat();
  };

  const toggleTrace = (msgId: string) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  const renderCitations = (citations: Citation[], brainEvidence?: any[]) => {
    const evidenceItems = brainEvidence || [];
    return (
      <div className="mt-3 space-y-1.5">
        {citations.map((citation, idx) => {
          const matchingEvidence = evidenceItems.find(
            (e: any) => e.source === citation.source && e.page === citation.page
          );
          const groundingKey = `${citation.source}:${citation.page}`;
          const groundingStatus = groundingMap.get(groundingKey)?.status;
          return (
            <CitationCard
              key={`${citation.source}-${citation.page}-${idx}`}
              source={citation.source}
              page={citation.page}
              excerpt={citation.text || matchingEvidence?.excerpt}
              relevance={citation.relevance || matchingEvidence?.relevance}
              groundingStatus={groundingStatus}
              onClick={() => onCitationClick(citation.source, citation.page, citation.doc_id)}
            />
          );
        })}
      </div>
    );
  };

  if (!projectId) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-muted-foreground">
        <AlertCircle className="mb-2 h-8 w-8 opacity-20" />
        <p className="text-sm">No Project Selected</p>
      </div>
    );
  }

  return (
    <div className="flex h-full max-h-full w-full flex-col overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-border bg-card px-4 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex rounded-xl bg-surface p-0.5">
            <button
              onClick={() => onChatModeChange('librarian')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-all ${chatMode === 'librarian'
                ? 'bg-primary/15 text-primary shadow-sm border border-primary/20'
                : 'text-muted-foreground hover:text-foreground border border-transparent'
                }`}
            >
              <BookOpen className="h-3.5 w-3.5" />
              Librarian
            </button>
            <button
              onClick={() => onChatModeChange('cortex')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-all ${chatMode === 'cortex'
                ? 'bg-accent/15 text-accent shadow-sm border border-accent/20'
                : 'text-muted-foreground hover:text-foreground border border-transparent'
                }`}
            >
              <Brain className="h-3.5 w-3.5" />
              Cortex
            </button>
            <button
              onClick={() => onChatModeChange('moe')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-all ${chatMode === 'moe'
                ? 'bg-blue-500/15 text-blue-500 shadow-sm border border-blue-500/20'
                : 'text-muted-foreground hover:text-foreground border border-transparent'
                }`}
            >
              <Network className="h-3.5 w-3.5" />
              MoE
            </button>
          </div>

          <button
            onClick={clearChat}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 min-w-0">
          {/* Messages */}
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 space-y-5">
            {currentMessages.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full text-center px-8">
                <div className={`rounded-2xl p-6 mb-6 ${chatMode === 'librarian' ? 'bg-gradient-to-br from-primary/20 to-primary/5' : chatMode === 'cortex' ? 'bg-gradient-to-br from-accent/20 to-accent/5' : 'bg-gradient-to-br from-blue-500/20 to-blue-500/5'}`}>
                  {chatMode === 'librarian' ? (
                    <BookOpen className="h-12 w-12 text-primary" />
                  ) : chatMode === 'cortex' ? (
                    <Brain className="h-12 w-12 text-accent" />
                  ) : (
                    <Network className="h-12 w-12 text-blue-500" />
                  )}
                </div>
                <h3 className="font-serif text-lg font-semibold text-foreground mb-2">
                  {chatMode === 'librarian' ? 'Document Librarian' : chatMode === 'cortex' ? 'Deep Research Assistant' : 'Mixture of Experts (MoE)'}
                </h3>
                <p className="text-sm text-muted-foreground max-w-md leading-relaxed mb-8">
                  {chatMode === 'librarian'
                    ? 'Ask questions and get answers backed by your documents with full citations and reasoning traces.'
                    : chatMode === 'cortex' ? 'Complex queries get deep multi-agent analysis. Finds connections, generates hypotheses, cross-checks findings with reflection loops.' : 'Orchestrates a team of highly specialized expert agents (Hypothesis, Retrieval, Writer, Critic). Highly grounded and fact-checked.'}
                </p>
                <div className="grid gap-2 sm:grid-cols-2 max-w-xl">
                  {(chatMode === 'librarian'
                    ? [
                      'What are the key findings?',
                      'Summarize this paper',
                      'What methods were used?',
                      'Find evidence for a claim'
                    ]
                    : chatMode === 'cortex' ? [
                      'Compare methodologies across papers',
                      'Identify contradictions in findings',
                      'Summarize key contributions',
                      'Find connections between concepts'
                    ] : [
                      'Synthesize the main barriers to adoption',
                      'Propose a novel hypothesis combining these domains',
                      'Conduct a grounded audit of recent findings',
                      'Write a comprehensive overview of the field'
                    ]
                  ).map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => { setCurrentInput(suggestion); inputRef.current?.focus(); }}
                      className="rounded-lg border border-border bg-surface px-4 py-3 text-left text-xs hover:border-primary/40 hover:bg-primary/5 transition-all"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <AnimatePresence mode="popLayout">
              {currentMessages.map((message) => (
                <motion.div
                  key={message.id}
                  layout
                  layoutId={message.id}
                  {...animations.slideUp}
                  transition={spring}
                  className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${message.brainActivity
                      ? message.brainActivity.brain.includes('MoE')
                        ? 'bg-gradient-to-br from-blue-500/20 to-blue-500/10 border border-blue-500/20'
                        : 'bg-gradient-to-br from-accent/20 to-accent/10 border border-accent/20'
                      : 'bg-gradient-to-br from-primary/20 to-primary/10 border border-primary/20'
                      }`}>
                      {message.brainActivity ? (
                        message.brainActivity.brain.includes('MoE') ? (
                          <Network className="h-4 w-4 text-blue-500" />
                        ) : (
                          <Brain className="h-4 w-4 text-accent" />
                        )
                      ) : (
                        <Bot className="h-4 w-4 text-primary" />
                      )}
                    </div>
                  )}

                  <div className="max-w-[80%]">
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.role === 'user'
                        ? 'bg-gradient-to-br from-primary to-primary/90 text-primary-foreground rounded-br-sm shadow-sm'
                        : 'rounded-bl-sm border border-border bg-card text-foreground'
                        }`}
                    >
                      {message.role === 'assistant' ? (
                        <div className="prose-sm">
                          <GenerativeRenderer content={message.content} />
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap break-words">{message.content}</div>
                      )}
                    </div>

                    {/* Brain Activity Trace */}
                    {message.brainActivity && message.brainActivity.trace.length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() => toggleTrace(message.id)}
                          className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors group"
                        >
                          {expandedTraces.has(message.id) ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : (
                            <ChevronDown className="h-3 w-3" />
                          )}
                          <Sparkles className="h-3 w-3 text-accent group-hover:text-accent" />
                          <span className="capitalize">{message.brainActivity.brain}</span> reasoning
                          <span className="rounded-full bg-surface px-1.5 py-0.5 text-[9px]">
                            {message.brainActivity.trace.length} steps
                          </span>
                        </button>

                        {/* Confidence & Iterations */}
                        {(message.brainActivity.confidenceScore !== undefined || message.brainActivity.iterations !== undefined) && (
                          <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                            {message.brainActivity.confidenceScore !== undefined && (
                              <div className="flex items-center gap-1.5">
                                <ShieldCheck className="h-3.5 w-3.5 text-success" />
                                <span>Confidence: {(message.brainActivity.confidenceScore * 100).toFixed(0)}%</span>
                              </div>
                            )}
                            {message.brainActivity.iterations !== undefined && (
                              <div className="flex items-center gap-1.5">
                                <RotateCw className="h-3.5 w-3.5 text-accent" />
                                <span>{message.brainActivity.iterations} reflection{message.brainActivity.iterations !== 1 ? 's' : ''}</span>
                              </div>
                            )}
                          </div>
                        )}

                        {expandedTraces.has(message.id) && (
                          <div className="mt-1.5 rounded-xl border border-border/50 bg-zinc-950/30 px-3 py-2.5 space-y-1.5">
                            {message.brainActivity.trace.map((step, i) => (
                              <div key={i} className="flex items-start gap-2 text-[11px]">
                                <span className="shrink-0 flex h-4 w-4 items-center justify-center rounded-full bg-accent/10 text-[9px] font-mono text-accent/60">
                                  {i + 1}
                                </span>
                                <span className="leading-relaxed text-muted-foreground">{step}</span>
                              </div>
                            ))}

                            {/* Contradictions */}
                            {message.brainActivity.contradictions && message.brainActivity.contradictions.length > 0 && (
                              <div className="mt-3 border-t border-border pt-3">
                                <div className="mb-2 text-xs font-medium text-warning">
                                  Contradictions Identified ({message.brainActivity.contradictions.length})
                                </div>
                                {message.brainActivity.contradictions.map((contradiction, i) => (
                                  <div key={i} className="mb-2 rounded-lg bg-warning/5 border border-warning/20 p-3 text-xs">
                                    <div className="mb-1 flex items-center gap-1.5 font-medium text-warning">
                                      <AlertTriangle className="h-3 w-3" />
                                      {contradiction.severity}
                                    </div>
                                    <div className="space-y-1.5 text-muted-foreground">
                                      <div><span className="text-foreground">A:</span> {contradiction.claim_a}</div>
                                      <div><span className="text-foreground">B:</span> {contradiction.claim_b}</div>
                                      {contradiction.resolution && (
                                        <div className="mt-2 border-t border-warning/10 pt-1.5 text-xs text-foreground">
                                          <span className="text-success">Resolution:</span> {contradiction.resolution}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Citations (Generative UI) */}
                    {message.citations && message.citations.length > 0 && (
                      renderCitations(message.citations, message.brainActivity?.evidence)
                    )}

                    {/* Librarian Metadata */}
                    {message.librarianMetadata?.reasoning && (
                      <div className="mt-3 rounded-lg bg-muted/30 p-3 text-xs">
                        <div className="mb-1.5 font-medium text-foreground">Reasoning</div>
                        <div className="text-muted-foreground">{message.librarianMetadata.reasoning}</div>
                      </div>
                    )}

                    {message.librarianMetadata?.relationships && message.librarianMetadata.relationships.length > 0 && (
                      <div className="mt-2 space-y-1">
                        <div className="text-xs font-medium text-muted-foreground">Graph Relationships</div>
                        {message.librarianMetadata.relationships.map((rel, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="text-foreground">{rel.source}</span>
                            <ArrowRight className="h-3 w-3 text-accent" />
                            <span className="rounded bg-accent/10 px-1.5 py-0.5 text-accent">{rel.type}</span>
                            <ArrowRight className="h-3 w-3 text-accent" />
                            <span className="text-foreground">{rel.target}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {message.role === 'user' && (
                    <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/20 border border-primary/30">
                      <User className="h-4 w-4 text-primary" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Streaming Progress */}
            {isLoading && streamProgress && chatMode !== 'moe' && (
              <div className="flex gap-3">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-accent/30 bg-gradient-to-br from-accent/20 to-accent/10">
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                </div>
                <div className="max-w-[80%]">
                  <div className="rounded-2xl rounded-bl-sm border border-accent/20 bg-card px-4 py-3.5 space-y-3">
                    {/* Routing Indicator */}
                    {streamProgress.routing && (
                      <div className="flex items-center gap-2.5 pb-2.5 border-b border-border/50">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
                          {streamProgress.routing.brain === 'navigator' ? (
                            <Search className="h-3.5 w-3.5 text-accent" />
                          ) : streamProgress.routing.brain === 'cortex' ? (
                            <Brain className="h-3.5 w-3.5 text-accent" />
                          ) : streamProgress.routing.brain.includes('moe') ? (
                            <Network className="h-3.5 w-3.5 text-blue-500" />
                          ) : (
                            <BookOpen className="h-3.5 w-3.5 text-primary" />
                          )}
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-semibold text-foreground">
                            {streamProgress.routing.brain === 'navigator' ? 'Deep Discovery' :
                              streamProgress.routing.brain === 'cortex' ? 'Research Cortex' :
                                streamProgress.routing.brain.includes('moe') ? 'MoE Supervisor' : 'Librarian'}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {streamProgress.routing.intent.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Processing Header with Elapsed Time */}
                    <div className="flex items-center justify-between pb-2 border-b border-border/30">
                      <div className="text-xs font-medium text-foreground">
                        Processing Query
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>{elapsedSeconds}s</span>
                      </div>
                    </div>

                    {/* Current Action */}
                    <div className="flex items-center gap-2.5">
                      <div className="relative flex h-2.5 w-2.5 shrink-0">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent"></span>
                      </div>
                      <span className="text-xs font-medium text-accent break-words">{streamProgress.message}</span>
                    </div>

                    {/* Graph Analysis Card */}
                    {streamProgress.graphData && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                        <div className="flex items-center gap-2 mb-2 text-primary">
                          <Share2 className="h-3.5 w-3.5" />
                          <span className="text-[11px] font-semibold">Knowledge Graph Insight</span>
                        </div>
                        <div className="text-[11px] text-foreground/80 leading-relaxed">
                          {streamProgress.graphData.summary || "Analyzing network structure..."}
                        </div>
                        {streamProgress.graphData.clusters && streamProgress.graphData.clusters.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {streamProgress.graphData.clusters.slice(0, 3).map((cluster, i) => (
                              <span key={i} className="inline-flex items-center rounded-full bg-background/50 border border-primary/10 px-1.5 py-0.5 text-[9px] text-primary/80">
                                {cluster.slice(0, 3).join(", ")}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Thinking Log */}
                    {streamProgress.thinkingSteps.length > 0 && (
                      <div className="rounded-lg bg-zinc-950/50 p-2.5 font-mono text-[10px]">
                        <div className="max-h-[120px] overflow-y-auto space-y-1 custom-scrollbar">
                          {streamProgress.thinkingSteps.map((step, i) => (
                            <div key={i} className="flex gap-2 text-zinc-400">
                              <span className="shrink-0 text-accent/40">{'>'}</span>
                              <span className="leading-tight">{step}</span>
                            </div>
                          ))}
                          <div className="h-2 w-1.5 animate-pulse bg-accent/50 rounded-sm" />
                        </div>
                      </div>
                    )}

                    {/* Streaming Response */}
                    {streamingText && (
                      <div className="mt-3 rounded-lg border border-border bg-card p-3">
                        <div className="text-xs text-muted-foreground mb-1.5">Generating Response...</div>
                        <div className="text-sm text-foreground whitespace-pre-wrap font-serif leading-relaxed">
                          {streamingText}
                          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent" />
                        </div>
                      </div>
                    )}

                    {/* Evidence Counter */}
                    {streamProgress.evidenceFound > 0 && (
                      <div className="flex items-center gap-2 text-[11px] text-muted-foreground pt-1.5 border-t border-border/50">
                        <Search className="h-3 w-3 text-primary" />
                        <span>Found <span className="font-medium text-foreground">{streamProgress.evidenceFound}</span> relevant sources</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Pending Hypotheses Display */}
          {chatMode === 'moe' && pendingHypotheses && pendingHypotheses.length > 0 && !isLoading && (
            <div className="shrink-0 border-t border-border bg-card/50 p-4">
              <div className="mx-auto max-w-3xl space-y-3">
                <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Network className="h-4 w-4 text-primary" />
                  Select a research path:
                </h4>
                <div className="grid gap-2 sm:grid-cols-1 md:grid-cols-2">
                  {pendingHypotheses.map((hypothesis, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSubmit(hypothesis.text)}
                      className="flex flex-col text-left gap-1 rounded-lg border border-border bg-card p-3 hover:border-primary/50 hover:bg-surface transition-all group"
                    >
                      <div className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                        {hypothesis.text}
                      </div>
                      {hypothesis.confidence !== undefined && (
                        <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                          <ShieldCheck className="h-3 w-3 text-success/80" />
                          Confidence: {(hypothesis.confidence * 100).toFixed(0)}%
                        </div>
                      )}
                      {hypothesis.reasoning && (
                        <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {hypothesis.reasoning}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
                <div className="text-xs flex justify-end">
                  <button
                    onClick={() => setPendingHypotheses(null)}
                    className="text-muted-foreground hover:text-foreground underline transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Input */}
          <div className="shrink-0 border-t border-border bg-card p-3">
            <div className="relative mx-auto max-w-3xl">
              <textarea
                ref={inputRef}
                value={currentInput}
                onChange={(e) => setCurrentInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  chatMode === 'librarian'
                    ? 'Ask a question about the documents...'
                    : chatMode === 'cortex'
                      ? 'Ask a complex research question...'
                      : 'Ask the MoE team to research and synthesize...'
                }
                className="w-full resize-none border-0 bg-transparent py-4 pl-4 pr-12 text-sm text-foreground outline-none placeholder:text-muted-foreground"
                rows={1}
                disabled={isLoading || !projectId}
              />
              <button
                onClick={() => handleSubmit()}
                disabled={isLoading || !currentInput.trim()}
                className={`absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 transition-all ${!currentInput.trim()
                  ? 'text-muted-foreground opacity-40'
                  : 'bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:opacity-90 shadow-sm'
                  }`}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            {isLoading && (
              <div className="mx-auto mt-2 max-w-3xl flex items-center justify-center gap-2">
                <button
                  onClick={() => {
                    const partialText = streamingText;
                    abortRef.current?.();
                    setIsLoading(false);
                    setStreamProgress(null);
                    setStreamingText('');
                    if (partialText.trim()) {
                      addMessage({
                        role: 'assistant',
                        content: partialText + '\n\n*(Generation stopped by user)*',
                      });
                    }
                  }}
                  className="text-[11px] text-muted-foreground hover:text-destructive transition-colors"
                >
                  Stop
                </button>
              </div>
            )}
          </div>
        </div>
        {chatMode === 'moe' && (
          <div className="w-[450px] shrink-0 border-l border-border bg-card/50">
            <AgentWorkbench
              streamProgress={streamProgress as any}
              streamingText={streamingText}
              isLoading={isLoading}
            />
          </div>
        )}
      </div>
    </div>
  );
}
