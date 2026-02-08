'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, Brain, BookOpen, Network, Zap } from 'lucide-react';
import { api, ChatMessage, Citation, SwarmResponse, SwarmEvidence } from '@/lib/api';

interface ChatInterfaceProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex';
  onChatModeChange: (mode: 'librarian' | 'cortex') => void;
}

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  brainActivity?: {
    brain: string;
    trace: string[];
    evidence: SwarmEvidence[];
  };
}

export default function ChatInterface({
  onCitationClick,
  projectId,
  chatMode,
  onChatModeChange,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      role: 'assistant',
      content:
        'Hello! I\'m your research assistant. Use "Librarian" mode for document Q&A with citations, or "Cortex" mode to activate the Two-Brain Swarm for deep discovery and broad research.',
      citations: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [brainStatus, setBrainStatus] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, brainStatus]);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: DisplayMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      if (chatMode === 'cortex' && projectId) {
        // Swarm mode
        setBrainStatus('Routing query to swarm...');
        const result: SwarmResponse = await api.runSwarm(input, projectId);

        const brainLabel = result.brain_used === 'navigator' ? 'Navigator' : 'Cortex';
        const assistantMessage: DisplayMessage = {
          role: 'assistant',
          content: result.hypothesis || 'No hypothesis generated.',
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
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        // Librarian mode (standard RAG)
        setBrainStatus(null);
        const response = await api.chat(input, projectId);
        const assistantMessage: DisplayMessage = {
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error processing your request. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
      setBrainStatus(null);
    }
  };

  const renderCitation = (citation: Citation, index: number) => (
    <button
      key={index}
      onClick={() => onCitationClick(citation.source, citation.page, citation.doc_id)}
      className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-blue-900/40 hover:bg-blue-800/50 text-blue-300 rounded-md transition-colors mr-1 mb-1"
      title={`Open ${citation.source} at page ${citation.page}`}
    >
      <FileText className="h-3 w-3" />
      <span>{citation.source}</span>
      <span className="text-blue-500">p.{citation.page}</span>
    </button>
  );

  const renderBrainActivity = (activity: DisplayMessage['brainActivity']) => {
    if (!activity) return null;
    const isNavigator = activity.brain === 'navigator';
    return (
      <div className="mt-3 pt-3 border-t border-gray-700">
        <div className="flex items-center gap-2 mb-2">
          {isNavigator ? (
            <Network className="h-3.5 w-3.5 text-purple-400" />
          ) : (
            <Zap className="h-3.5 w-3.5 text-blue-400" />
          )}
          <p className="text-xs font-semibold text-gray-400">
            {isNavigator ? 'Navigator Brain' : 'Cortex Brain'} - Reasoning Trace
          </p>
        </div>
        <div className="space-y-1 max-h-32 overflow-y-auto">
          {activity.trace.map((step, i) => (
            <p key={i} className="text-xs text-gray-500 font-mono pl-2 border-l border-gray-700">
              {step}
            </p>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {chatMode === 'cortex' ? (
              <Brain className="h-5 w-5 text-purple-400" />
            ) : (
              <BookOpen className="h-5 w-5 text-emerald-400" />
            )}
            <h2 className="text-lg font-semibold text-gray-100">
              {chatMode === 'cortex' ? 'Cortex Swarm' : 'Librarian AI'}
            </h2>
          </div>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-1 bg-gray-800 rounded-lg p-0.5">
          <button
            onClick={() => onChatModeChange('librarian')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              chatMode === 'librarian'
                ? 'bg-emerald-600 text-white'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <BookOpen className="h-3 w-3" />
            Librarian
          </button>
          <button
            onClick={() => onChatModeChange('cortex')}
            disabled={!projectId}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              chatMode === 'cortex'
                ? 'bg-purple-600 text-white'
                : projectId
                ? 'text-gray-500 hover:text-gray-300'
                : 'text-gray-700 cursor-not-allowed'
            }`}
          >
            <Brain className="h-3 w-3" />
            Cortex
          </button>
        </div>

        <p className="text-xs text-gray-500 mt-2">
          {chatMode === 'cortex'
            ? 'Agentic RAG: Two-Brain Swarm for deep discovery & broad research'
            : 'Standard RAG: Document Q&A with automatic citations'}
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    message.brainActivity
                      ? 'bg-purple-900/50'
                      : 'bg-emerald-900/50'
                  }`}
                >
                  {message.brainActivity ? (
                    <Brain className="h-4 w-4 text-purple-400" />
                  ) : (
                    <Bot className="h-4 w-4 text-emerald-400" />
                  )}
                </div>
              </div>
            )}

            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-200'
              }`}
            >
              <div className="whitespace-pre-wrap break-words text-sm">{message.content}</div>

              {message.citations && message.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-xs font-semibold text-gray-400 mb-2">Sources:</p>
                  <div className="flex flex-wrap gap-1">
                    {message.citations.map((citation, idx) => renderCitation(citation, idx))}
                  </div>
                </div>
              )}

              {renderBrainActivity(message.brainActivity)}
            </div>

            {message.role === 'user' && (
              <div className="flex-shrink-0">
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
                  <User className="h-4 w-4 text-gray-400" />
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Loading / Brain Activity indicator */}
        {loading && (
          <div className="flex gap-3">
            <div className="flex-shrink-0">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  chatMode === 'cortex' ? 'bg-purple-900/50' : 'bg-emerald-900/50'
                }`}
              >
                {chatMode === 'cortex' ? (
                  <Brain className="h-4 w-4 text-purple-400 animate-pulse" />
                ) : (
                  <Bot className="h-4 w-4 text-emerald-400 animate-pulse" />
                )}
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg px-4 py-3">
              {brainStatus ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {chatMode === 'cortex' && (
                      <div className="flex gap-0.5">
                        <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-ping" />
                        <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-ping delay-100" />
                      </div>
                    )}
                    <p className="text-xs text-gray-400 font-medium">{brainStatus}</p>
                  </div>
                </div>
              ) : (
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100" />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200" />
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800 bg-gray-900">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              chatMode === 'cortex'
                ? 'Ask a research question (Swarm will auto-route)...'
                : 'Ask about your documents...'
            }
            disabled={loading}
            className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-800/50 disabled:cursor-not-allowed text-sm"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className={`px-4 py-2 text-white rounded-lg disabled:bg-gray-700 disabled:cursor-not-allowed transition-colors flex items-center gap-2 text-sm ${
              chatMode === 'cortex'
                ? 'bg-purple-600 hover:bg-purple-700'
                : 'bg-emerald-600 hover:bg-emerald-700'
            }`}
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
