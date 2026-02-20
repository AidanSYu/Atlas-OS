'use client';

import { useEffect, useState, useCallback } from 'react';
import { Command } from 'cmdk';
import { useRouter } from 'next/navigation';
import {
  Search,
  Upload,
  MessageSquare,
  FileText,
  Network,
  PenTool,
  Download,
  Home,
  BookOpen,
} from 'lucide-react';

interface OmniBarProps {
  projectId?: string;
  onUpload?: () => void;
  onExport?: (type: 'bibtex' | 'markdown' | 'chat') => void;
  onSwitchView?: (view: 'document' | 'editor' | 'graph' | 'chat' | 'canvas') => void;
}

export function OmniBar({ projectId, onUpload, onExport, onSwitchView }: OmniBarProps) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const close = useCallback(() => setOpen(false), []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[20vh]">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-background/50 backdrop-blur-sm"
        onClick={close}
      />

      {/* Command Palette */}
      <div className="relative z-[201] w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-card/95 backdrop-blur-xl shadow-2xl shadow-primary/10">
        <Command
          label="Global Command Menu"
          className="flex w-full flex-col bg-transparent"
        >
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Command.Input
              placeholder="Type a command or search..."
              className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>

          <Command.List className="max-h-[60vh] overflow-y-auto p-2">
            <Command.Empty className="px-4 py-8 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            {projectId && (
              <>
                <Command.Group heading="Views" className="mb-2">
                  <CommandItem icon={BookOpen} onSelect={() => { onSwitchView?.('document'); close(); }}>
                    Documents View
                  </CommandItem>
                  <CommandItem icon={PenTool} onSelect={() => { onSwitchView?.('editor'); close(); }}>
                    Editor View
                  </CommandItem>
                  <CommandItem icon={Network} onSelect={() => { onSwitchView?.('graph'); close(); }}>
                    Knowledge Graph
                  </CommandItem>
                  <CommandItem icon={MessageSquare} onSelect={() => { onSwitchView?.('chat'); close(); }}>
                    Deep Chat
                  </CommandItem>
                </Command.Group>

                <Command.Group heading="Actions" className="mb-2">
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
                </Command.Group>
              </>
            )}

            <Command.Group heading="Navigation">
              <CommandItem icon={Home} onSelect={() => { router.push('/'); close(); }}>
                Back to Dashboard
              </CommandItem>
            </Command.Group>
          </Command.List>

          <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground bg-surface/50">
            <kbd className="rounded bg-muted px-1.5 py-0.5 font-mono">Cmd/Ctrl K</kbd> to close
          </div>
        </Command>
      </div>
    </div>
  );
}

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
      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-foreground hover:bg-primary/10 aria-selected:bg-primary/10"
    >
      <Icon className="h-4 w-4 text-muted-foreground" />
      {children}
    </Command.Item>
  );
}
