'use client';

import React from 'react';
import DualAgentChat from '@/components/DualAgentChat';

interface ChatInterfaceProps {
  onCitationClick: (filename: string, page: number, docId?: string) => void;
  projectId?: string;
}

export default function ChatInterface({
  onCitationClick,
  projectId,
}: ChatInterfaceProps) {
  return (
    <DualAgentChat
      onCitationClick={onCitationClick}
      projectId={projectId}
    />
  );
}
