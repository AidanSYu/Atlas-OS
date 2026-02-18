'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { useChatStore, ChatMessage } from '@/stores/chatStore';
import { api, Citation, SwarmResponse } from '@/lib/api';
import {
  Send,
  Bot,
  User,
  FileText,
  Brain,
  BookOpen,
  Network,
  Zap,
  Loader2,
  Trash2,
  AlertCircle
} from 'lucide-react';

interface DualAgentChatProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex';
  onChatModeChange: (mode: 'librarian' | 'cortex') => void;
}

export default function DualAgentChat({
  onCitationClick,
  projectId,
  chatMode,
  onChatModeChange,
}: DualAgentChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    librarianMessages,
    librarianInput,
    cortexMessages,
    cortexInput,
    addLibrarianMessage,
    addCortexMessage,
    setLibrarianInput,
    setCortexInput,
    clearLibrarianChat,
    clearCortexChat,
    setActiveProject,
  } = useChatStore();

  // Track project changes
  useEffect(() => {
    setActiveProject(projectId || null);
  }, [projectId, setActiveProject]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [librarianMessages, cortexMessages, chatMode]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  }, [chatMode === 'librarian' ? librarianInput : cortexInput]);

  // Loading state
  const [isLoading, setIsLoading] = React.useState(false);
  const [brainStatus, setBrainStatus] = React.useState<string | null>(null);

  const currentMessages = chatMode === 'librarian' ? librarianMessages : cortexMessages;
  const currentInput = chatMode === 'librarian' ? librarianInput : cortexInput;
  const setCurrentInput = chatMode === 'librarian' ? setLibrarianInput : setCortexInput;
  const addMessage = chatMode === 'librarian' ? addLibrarianMessage : addCortexMessage;
  const clearChat = chatMode === 'librarian' ? clearLibrarianChat : clearCortexChat;

  const handleSubmit = useCallback(async () => {
    if (!currentInput.trim() || isLoading || !projectId) return;

    const userContent = currentInput.trim();
    setCurrentInput('');
    setIsLoading(true);
    setBrainStatus(null);

    // Add user message immediately
    addMessage({ role: 'user', content: userContent });

    try {
      if (chatMode === 'cortex') {
        setBrainStatus('Initializing swarm intelligence...');
        const result: SwarmResponse = await api.runSwarm(userContent, projectId);

        addMessage({
          role: 'assistant',
          content: result.hypothesis || 'No analysis generated.',
          citations: result.evidence?.map((e) => ({
            source: e.source,
            page: e.page,
            relevance: e.relevance,
            text: e.excerpt,
          })),
          brainActivity: {
            brain: result.brain_used,
            trace: result.reasoning_trace || [],
            evidence: result.evidence || [],
          },
        });
      } else {
        // Librarian mode
        setBrainStatus('Searching document knowledge base...');
        const response = await api.chat(userContent, projectId);

        addMessage({
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      addMessage({
        role: 'assistant',
        content: 'I apologize, but I encountered an error processing your request. Please try again or check your connection.',
      });
    } finally {
      setIsLoading(false);
      setBrainStatus(null);
    }
  }, [currentInput, isLoading, projectId, chatMode, addMessage, setCurrentInput]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const renderCitation = (citation: Citation, index: number) => (
    <button
      key={index}
      onClick={() => onCitationClick(citation.source, citation.page, citation.doc_id)}
      className="group inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] bg-accent/50 hover:bg-accent border border-border rounded-md transition-all text-muted-foreground hover:text-foreground"
      title={`Open ${citation.source} at page ${citation.page}`}
    >
      <FileText className="h-3 w-3 opacity-70" />
      <span className="truncate max-w-[100px]">{citation.source}</span>
      <span className="opacity-50">p.{citation.page}</span>
    </button>
  );

  const getAgentConfig = (mode: 'librarian' | 'cortex') => {
    if (mode === 'librarian') {
      return {
        name: 'Librarian',
        title: 'Document Analysis',
        subtitle: 'RAG-powered document Q&A',
        icon: BookOpen,
      };
    }
    return {
      name: 'Cortex',
      title: 'Research Intelligence',
      subtitle: 'Multi-agent swarm analysis',
      icon: Brain,
    };
  };

  const currentConfig = getAgentConfig(chatMode);

  if (!projectId) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-muted-foreground text-center">
        <AlertCircle className="w-8 h-8 mb-2 opacity-20" />
        <p className="text-sm">No Project Selected</p>
      </div>
    );
  }

  return (
    <div className="flex h-full max-h-full w-full flex-col overflow-hidden border border-border bg-card">
      {/* Header */}
      <div className="border-b border-border bg-card px-4 py-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Simple Toggle - "Material Switch" style */}
            <div className="flex bg-muted/50 p-1 rounded-lg">
              <button
                onClick={() => onChatModeChange('librarian')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${chatMode === 'librarian'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                Librarian
              </button>
              <button
                onClick={() => onChatModeChange('cortex')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${chatMode === 'cortex'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                  }`}
              >
                <Brain className="w-3.5 h-3.5" />
                Cortex
              </button>
            </div>
          </div>

          <button
            onClick={clearChat}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors"
            title="Clear"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-6">
        {currentMessages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full opacity-30 text-center px-8">
            {chatMode === 'librarian' ? <BookOpen className="w-12 h-12 mb-4" /> : <Brain className="w-12 h-12 mb-4" />}
            <p className="text-sm">{chatMode === 'librarian' ? "Ask questions about your documents." : "Deep analysis and hypothesis generation."}</p>
          </div>
        )}

        {currentMessages.map((message, index) => (
          <div
            key={message.id}
            className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start max-w-[85%]'}`}
          >
            {message.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0 border border-border">
                {message.brainActivity ? (
                  <Brain className="w-4 h-4 text-foreground opacity-70" />
                ) : (
                  <Bot className="w-4 h-4 text-foreground opacity-70" />
                )}
              </div>
            )}

            <div
              className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${message.role === 'user'
                  ? 'bg-primary text-primary-foreground rounded-br-none'
                  : 'bg-muted/30 border border-border text-foreground rounded-bl-none'
                }`}
            >
              <div className="whitespace-pre-wrap break-words">
                {message.content}
              </div>

              {message.citations && message.citations.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border/50">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
                    Sources
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {message.citations.map((citation, idx) => renderCitation(citation, idx))}
                  </div>
                </div>
              )}
            </div>

            {message.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center shrink-0 border border-border">
                <User className="w-4 h-4 text-foreground opacity-70" />
              </div>
            )}
          </div>
        ))}

        {/* Loading State */}
        {isLoading && (
          <div className="flex gap-4 max-w-[85%]">
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0 border border-border">
              <Loader2 className="w-4 h-4 animate-spin text-foreground opacity-50" />
            </div>
            <div className="bg-muted/30 border border-border rounded-2xl rounded-bl-none px-4 py-3">
              <div className="flex items-center gap-3">
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  {brainStatus || "Thinking..."}
                  <span className="flex gap-1 ml-1">
                    <span className="w-1 h-1 bg-foreground opacity-50 rounded-full animate-bounce" />
                    <span className="w-1 h-1 bg-foreground opacity-50 rounded-full animate-bounce delay-100" />
                    <span className="w-1 h-1 bg-foreground opacity-50 rounded-full animate-bounce delay-200" />
                  </span>
                </p>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border bg-background p-4 flex-shrink-0">
        <div className="relative max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              chatMode === 'cortex'
                ? 'Ask for deep analysis...'
                : 'Ask about the document...'
            }
            disabled={isLoading}
            rows={1}
            className="w-full pl-4 pr-12 py-3 bg-muted/30 border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-border focus:bg-muted/50 transition-all text-sm resize-none scrollbar-hide shadow-inner"
          />
          <button
            onClick={handleSubmit}
            disabled={isLoading || !currentInput.trim()}
            className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-all ${!currentInput.trim() ? 'text-muted-foreground opacity-50' : 'bg-foreground text-background hover:opacity-90'
              }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
