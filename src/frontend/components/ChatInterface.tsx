'use client';

import React from 'react';
import DualAgentChat from '@/components/DualAgentChat';

interface ChatInterfaceProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
  chatMode: 'librarian' | 'cortex';
  onChatModeChange: (mode: 'librarian' | 'cortex') => void;
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
