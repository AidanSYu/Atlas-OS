'use client';

import React from 'react';
import { Cpu, Database, Moon, Sun, Wifi, WifiOff, Zap, HardDrive } from 'lucide-react';

interface StatusBarProps {
  modelName?: string;
  device?: string;
  nodeCount: number;
  connected?: boolean;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export function StatusBar({
  modelName,
  device,
  nodeCount,
  connected = true,
  theme,
  onToggleTheme,
}: StatusBarProps) {
  return (
    <div className="flex h-6 shrink-0 items-center justify-between border-t border-border bg-card px-3 text-[11px] text-muted-foreground">
      {/* Left side */}
      <div className="flex items-center gap-3">
        {/* Connection */}
        <div className="flex items-center gap-1.5" title={connected ? 'Backend is connected' : 'Backend is offline'}>
          {connected ? (
            <Wifi className="h-3 w-3 text-accent" />
          ) : (
            <WifiOff className="h-3 w-3 text-destructive" />
          )}
          <span>{connected ? 'Connected' : 'Offline'}</span>
        </div>

        {/* Model */}
        {modelName && (
          <div className="flex items-center gap-1.5 border-l border-border pl-3" title={`Active model: ${modelName}`}>
            <Cpu className="h-3 w-3 text-accent/60" />
            <span className="max-w-[200px] truncate">{modelName}</span>
            {device && (
              <span className="rounded bg-accent/10 text-accent px-1 py-0.5 text-[9px] font-medium uppercase">
                {device}
              </span>
            )}
          </div>
        )}

        {/* Nodes */}
        <div className="flex items-center gap-1.5 border-l border-border pl-3" title={`${nodeCount} nodes in the knowledge graph`}>
          <Database className="h-3 w-3 text-accent/60" />
          <span>{nodeCount} nodes</span>
        </div>

        {/* Local indicator */}
        <div className="flex items-center gap-1.5 border-l border-border pl-3" title="All processing runs locally on your machine">
          <HardDrive className="h-3 w-3 text-muted-foreground/50" />
          <span className="text-muted-foreground/60">Local</span>
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider opacity-50">
          <Zap className="h-2.5 w-2.5 text-accent/50" />
          Atlas Framework
        </div>
        <button
          onClick={onToggleTheme}
          className="flex h-4 w-4 items-center justify-center rounded transition-colors hover:text-foreground"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />}
        </button>
      </div>
    </div>
  );
}
