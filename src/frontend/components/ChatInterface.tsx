'use client';

import React from 'react';
import DualAgentChat from '@/components/DualAgentChat';

interface ChatInterfaceProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex' | 'moe' | 'discovery';
  onChatModeChange: (mode: 'librarian' | 'cortex' | 'moe' | 'discovery') => void;
}

export default function ChatInterface({
  onCitationClick,
  projectId,
  chatMode,
  onChatModeChange,
}: ChatInterfaceProps) {
  return (
    <DualAgentChat
      onCitationClick={onCitationClick}
      projectId={projectId}
      chatMode={chatMode}
      onChatModeChange={onChatModeChange}
    />
  );
}
