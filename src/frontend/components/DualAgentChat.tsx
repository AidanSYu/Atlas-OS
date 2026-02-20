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
} from 'lucide-react';
import CitationCard from './generative/CitationCard';
import ClaimBadge, { GroundingStatus } from './generative/ClaimBadge';
import { spring, animations } from '@/lib/design-system/motion';

interface DualAgentChatProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex';
  onChatModeChange: (mode: 'librarian' | 'cortex') => void;
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
    addLibrarianMessage,
    addCortexMessage,
    setLibrarianInput,
    setCortexInput,
    clearLibrarianChat,
    clearCortexChat,
    setActiveProject,
    pendingQuestion,
    setPendingQuestion,
  } = useChatStore();

  useEffect(() => {
    setActiveProject(projectId || null);
  }, [projectId, setActiveProject]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [librarianMessages, cortexMessages, chatMode]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  }, [chatMode === 'librarian' ? librarianInput : cortexInput]);

  const [isLoading, setIsLoading] = useState(false);
  const [streamProgress, setStreamProgress] = useState<StreamProgress | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
  const [groundingMap, setGroundingMap] = useState<Map<string, GroundingEvent>>(new Map());
  const [streamingText, setStreamingText] = useState<string>('');
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const currentMessages = chatMode === 'librarian' ? librarianMessages : cortexMessages;
  const currentInput = chatMode === 'librarian' ? librarianInput : cortexInput;
  const setCurrentInput = chatMode === 'librarian' ? setLibrarianInput : setCortexInput;
  const addMessage = chatMode === 'librarian' ? addLibrarianMessage : addCortexMessage;
  const clearChat = chatMode === 'librarian' ? clearLibrarianChat : clearCortexChat;

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

  const handleSubmit = useCallback(async () => {
    if (!currentInput.trim() || isLoading || !projectId) return;

    const userContent = currentInput.trim();
    setCurrentInput('');
    setIsLoading(true);
    setStreamProgress(null);
    setStartTime(Date.now());

    addMessage({ role: 'user', content: userContent });

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
        } catch {
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
      } else {
        setStreamProgress({
          currentNode: 'librarian',
          message: 'Searching document library...',
          thinkingSteps: [],
          evidenceFound: 0,
        });

        const response = await api.chat(userContent, projectId);
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
    } catch (error) {
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
  }, [currentInput, isLoading, projectId, chatMode, addMessage, setCurrentInput]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
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

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {currentMessages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-8">
            <div className={`rounded-2xl p-5 mb-5 ${chatMode === 'librarian' ? 'bg-gradient-to-br from-primary/10 to-primary/5' : 'bg-gradient-to-br from-accent/10 to-accent/5'}`}>
              {chatMode === 'librarian' ? (
                <BookOpen className="h-10 w-10 text-primary" />
              ) : (
                <Brain className="h-10 w-10 text-accent" />
              )}
            </div>
            <h3 className="font-serif text-xl text-foreground mb-2">
              {chatMode === 'librarian' ? 'Document Librarian' : 'Research Cortex'}
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
              {chatMode === 'librarian'
                ? 'Ask questions about your documents. Fast, focused answers with source citations.'
                : 'Deep multi-agent analysis. Finds connections, generates hypotheses, cross-checks findings.'}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {(chatMode === 'librarian'
                ? ['What are the key findings?', 'Summarize this paper', 'What methods were used?']
                : ['Find connections between papers', 'Generate hypothesis about X', 'Compare approaches across studies']
              ).map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => { setCurrentInput(suggestion); inputRef.current?.focus(); }}
                  className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-xs text-muted-foreground transition-all hover:border-primary/30 hover:text-foreground hover:bg-primary/5"
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
                  ? 'bg-gradient-to-br from-accent/20 to-accent/10 border border-accent/20'
                  : 'bg-gradient-to-br from-primary/20 to-primary/10 border border-primary/20'
                  }`}>
                  {message.brainActivity ? (
                    <Brain className="h-4 w-4 text-accent" />
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
                    <MarkdownContent content={message.content} />
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
        {isLoading && streamProgress && (
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
                      ) : (
                        <BookOpen className="h-3.5 w-3.5 text-primary" />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-foreground">
                        {streamProgress.routing.brain === 'navigator' ? 'Deep Discovery' :
                          streamProgress.routing.brain === 'cortex' ? 'Research Cortex' : 'Librarian'}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {streamProgress.routing.intent.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                )}

                {/* Processing Header with Elapsed Time */}
                <div className="flex items-center justify-between pb-2 border-b border-border/30">
                  <div className="text-xs font-medium text-foreground">Processing Query</div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>{elapsedSeconds}s</span>
                  </div>
                </div>

                {/* Current Action */}
                <div className="flex items-center gap-2.5">
                  <div className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent"></span>
                  </div>
                  <span className="text-xs font-medium text-accent">{streamProgress.message}</span>
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

      {/* Input */}
      <div className="shrink-0 border-t border-border bg-card p-3">
        <div className="relative mx-auto max-w-3xl">
          <textarea
            ref={inputRef}
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              chatMode === 'cortex'
                ? 'Ask for deep analysis, hypothesis generation...'
                : 'Ask about your documents...'
            }
            disabled={isLoading}
            rows={1}
            className="w-full rounded-xl border border-border bg-background py-3 pl-4 pr-12 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all resize-none"
          />
          <button
            onClick={handleSubmit}
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
                abortRef.current?.();
                setIsLoading(false);
                setStreamProgress(null);
              }}
              className="text-[11px] text-muted-foreground hover:text-destructive transition-colors"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
