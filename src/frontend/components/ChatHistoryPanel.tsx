'use client';

import React, { useState, useMemo } from 'react';
import { MessageSquare, Plus, Search, Trash2, X, Clock } from 'lucide-react';
import { useChatStore, type ChatThread } from '@/stores/chatStore';
import type { ChatMode } from '@/hooks/useRunManager';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODE_LABELS: Record<ChatMode, string> = {
  librarian: 'Librarian',
  cortex: 'Cortex',
  moe: 'MoE',
};

const MODE_COLORS: Record<ChatMode, string> = {
  librarian: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  cortex: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  moe: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function getLastUserMessage(thread: ChatThread): string | null {
  const userMsgs = thread.messages.filter((m) => m.role === 'user');
  return userMsgs[userMsgs.length - 1]?.content ?? null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatHistoryPanelProps {
  projectId: string;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatHistoryPanel({
  projectId,
  onSelectThread,
  onNewChat,
  onClose,
}: ChatHistoryPanelProps) {
  const [search, setSearch] = useState('');

  // Select stable reference: store.threads (same ref until store updates). Derive project
  // threads in the component so Zustand never sees a new array reference each render.
  const storeThreads = useChatStore((s) => s.threads);
  const threads = useMemo(
    () => storeThreads.filter((t) => t.projectId === projectId),
    [storeThreads, projectId]
  );
  const activeThreadId = useChatStore((s) => s.activeThreadId);
  const deleteThread = useChatStore((s) => s.deleteThread);

  const filtered = useMemo(() => {
    if (!search.trim()) return threads;
    const q = search.toLowerCase();
    return threads.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.messages.some((m) => m.content.toLowerCase().includes(q))
    );
  }, [threads, search]);

  return (
    <div className="flex h-full flex-col">

      {/* ---- Header ---- */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Chat
          </span>
        </div>
        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          title="Close chat"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* ---- New Chat ---- */}
      <div className="shrink-0 p-3 pb-2">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/20 active:scale-[0.98]"
        >
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </button>
      </div>

      {/* ---- Search ---- */}
      <div className="shrink-0 px-3 pb-3">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface/60 px-2.5 py-1.5 transition-colors focus-within:border-primary/40 focus-within:bg-surface">
          <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
          <input
            type="text"
            placeholder="Search chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground/40 outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="shrink-0 text-muted-foreground/50 hover:text-foreground transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* ---- Section label ---- */}
      {threads.length > 0 && (
        <div className="shrink-0 px-3 pb-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
            {search ? `${filtered.length} result${filtered.length !== 1 ? 's' : ''}` : `${threads.length} conversation${threads.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      )}

      {/* ---- Thread list ---- */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center px-4">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/5 border border-primary/10">
              <MessageSquare className="h-5 w-5 text-muted-foreground/30" />
            </div>
            <p className="text-xs font-medium text-muted-foreground/60">
              {search ? 'No chats match your search' : 'No chats yet'}
            </p>
            {!search && (
              <p className="mt-1 text-[11px] text-muted-foreground/40">
                Start a new chat to begin
              </p>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {filtered.map((thread) => {
              const isActive = thread.id === activeThreadId;
              const preview = getLastUserMessage(thread);
              const msgCount = thread.messages.filter((m) => m.role === 'user').length;

              return (
                <div key={thread.id} className="group flex items-start gap-1">
                  <button
                    type="button"
                    onClick={() => onSelectThread(thread.id)}
                    className={`min-w-0 flex-1 rounded-lg px-2.5 py-2.5 text-left transition-all ${
                      isActive
                        ? 'bg-primary/12 ring-1 ring-inset ring-primary/20'
                        : 'hover:bg-surface/60'
                    }`}
                  >
                    {/* Top row: mode badge + time */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${MODE_COLORS[thread.chatMode]}`}
                      >
                        {MODE_LABELS[thread.chatMode]}
                      </span>
                      <div className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground/40">
                        <Clock className="h-2.5 w-2.5" />
                        <span>{timeAgo(thread.updatedAt)}</span>
                      </div>
                    </div>

                    {/* Title */}
                    <p
                      className={`truncate text-xs font-medium leading-snug ${
                        isActive ? 'text-foreground' : 'text-foreground/75'
                      }`}
                    >
                      {thread.title}
                    </p>

                    {/* Last user message preview */}
                    {preview && (
                      <p className="mt-0.5 truncate text-[11px] leading-relaxed text-muted-foreground/45">
                        {preview}
                      </p>
                    )}

                    {/* Message count */}
                    <p className="mt-1 text-[10px] text-muted-foreground/30">
                      {msgCount} message{msgCount !== 1 ? 's' : ''}
                    </p>
                  </button>

                  {/* Delete button — visible on group hover */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteThread(thread.id);
                    }}
                    className="mt-2 flex h-6 w-6 shrink-0 items-center justify-center rounded text-transparent transition-all group-hover:text-muted-foreground/35 hover:!text-destructive hover:bg-destructive/10"
                    title="Delete chat"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
