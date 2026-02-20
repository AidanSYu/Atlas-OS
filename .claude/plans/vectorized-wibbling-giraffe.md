# Atlas Phase 6: Spatial Research OS - Implementation Plan

## Context

Atlas has completed Phases 0-5: backend services (swarm agents, context engine, import/export), basic frontend (3-pane workspace, chat, graph, PDF viewer, editor). **Phase 6 transforms the frontend into a professional-grade "Spatial Research OS" ready for Duke University pilot deployment.**

### The Problem
- **Critical data gaps**: Backend sends confidence scores, grounding verification, contradictions, reasoning chains, and token streams—frontend discards all of it
- **Missing pilot-critical features**: Import/Export UI completely absent despite full backend implementation
- **Streaming bugs**: SSE partial-chunk buffer issue silently drops events; Librarian has no streaming at all
- **Poor feedback**: Users see static "loading..." states with no progress visibility
- **No keyboard efficiency**: Mouse-only navigation
- **Limited research workflow**: No spatial organization, comparison views, or AI-generated structured outputs

### The Vision (Antigravity + Pilot Reality)
The Antigravity plan proposes a full "infinite canvas OS" replacement. **This plan integrates that vision pragmatically**: keep the familiar 3-pane layout as the primary workspace, add canvas as a powerful integrated view mode, and prioritize data completeness + professional polish for pilot readiness.

---

## Implementation Strategy

### Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Layout paradigm** | Keep 3-pane, add canvas as 5th tab | Familiar UX, lower risk for pilot, researchers expect panel layouts |
| **React Flow version** | Upgrade to `@xyflow/react` v12 | Modern API, better performance, what Antigravity spec requires (v11 installed but unused) |
| **Motion library** | Install `framer-motion` v11 | Industry standard, physics-based springs, layout animations |
| **State complexity** | Pure Zustand (no XState) | Simpler, already working well, XState overkill for current needs |
| **AI streaming** | Keep manual SSE, fix buffer bug | Vercel AI SDK `streamUI` requires backend rewrite; manual SSE works once fixed |
| **Command palette** | `cmdk` library | De facto standard (used by Linear, Raycast, Vercel) |
| **Generative UI** | Manual React components | Custom control, no framework lock-in, incremental adoption |

---

## Phase 6A: Data Completeness & Streaming Fixes
**Priority**: CRITICAL (Pilot Blocker)
**Estimated effort**: 2-3 days

### 6A.1 - Fix SSE Partial-Chunk Buffer Bug

**Problem**: `streamSwarm` in `api.ts` splits each `read()` chunk independently. SSE events spanning two chunks are silently lost.

**File**: `src/frontend/lib/api.ts`

**Changes**:
```typescript
// Line 558-617: Replace streamSwarm implementation
let buffer = ''; // Add persistent buffer outside the while loop

while (!done) {
  const { value, done: streamDone } = await reader.read();
  done = streamDone;
  if (value) {
    const chunk = new TextDecoder().decode(value);
    buffer += chunk; // Append to buffer

    const events = buffer.split('\n\n'); // Split on complete boundaries
    buffer = events.pop() || ''; // Keep incomplete event in buffer

    for (const event of events) {
      // ... existing parsing logic
    }
  }
}
```

### 6A.2 - Wire Grounding Events to UI

**Problem**: `grounding` SSE events are caught but immediately discarded with `break;`. ClaimBadge component exists but is never fed data.

**Files**:
- `src/frontend/lib/api.ts` (lines 143-149) - Extend `SwarmResponse` type
- `src/frontend/components/DualAgentChat.tsx` (lines 187-237, 339-345)

**Changes**:

1. **Extend types** (`api.ts`):
```typescript
export interface GroundingEvent {
  claim: string;
  status: 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED';
  confidence: number;
  source?: string;
  page?: number;
}

export interface SwarmEvidence {
  source: string;
  page: number;
  excerpt: string;
  relevance: number;
  grounding_status?: 'GROUNDED' | 'SUPPORTED' | 'UNVERIFIED' | 'INFERRED'; // Add this
}

export interface SwarmResponse {
  brain_used: 'navigator' | 'cortex' | 'librarian';
  hypothesis: string;
  evidence: SwarmEvidence[];
  reasoning_trace: string[];
  status: string;
  confidence_score?: number;      // ADD
  iterations?: number;            // ADD
  contradictions?: Array<{        // ADD
    claim_a: string;
    claim_b: string;
    severity: 'HIGH' | 'LOW';
    resolution?: string;
  }>;
}
```

2. **Add grounding state** (`DualAgentChat.tsx`):
```typescript
// After line 185 (other state declarations)
const [groundingMap, setGroundingMap] = useState<Map<string, GroundingEvent>>(new Map());
```

3. **Handle grounding events** (line 219 - replace empty `break`):
```typescript
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
```

4. **Pass grounding status to CitationCard** (line 339-345):
```typescript
const groundingKey = `${citation.source}:${citation.page}`;
const groundingStatus = groundingMap.get(groundingKey)?.status;

<CitationCard
  key={i}
  source={citation.source}
  page={citation.page}
  excerpt={excerpt}
  relevance={citation.relevance}
  groundingStatus={groundingStatus}  // ADD THIS
  onClick={() => handleCitationClick(citation)}
/>
```

### 6A.3 - Surface Confidence, Iterations, Contradictions

**File**: `src/frontend/components/DualAgentChat.tsx`

**Changes**:

1. **Store additional fields** (line 246-260 - extend message creation):
```typescript
const message: ChatMessage = {
  id: Date.now().toString(),
  role: 'assistant',
  content: result.hypothesis,
  citations: evidenceWithText,
  brainActivity: {
    brain: result.brain_used,
    trace: result.reasoning_trace,
    evidence: result.evidence,
    confidenceScore: result.confidence_score,      // ADD
    iterations: result.iterations,                 // ADD
    contradictions: result.contradictions,         // ADD
  },
  timestamp: new Date(),
};
```

2. **Update ChatMessage interface** (`src/frontend/stores/chatStore.ts`):
```typescript
export interface BrainActivity {
  brain: string;
  trace: string[];
  evidence?: SwarmEvidence[];
  confidenceScore?: number;      // ADD
  iterations?: number;            // ADD
  contradictions?: Array<{        // ADD
    claim_a: string;
    claim_b: string;
    severity: 'HIGH' | 'LOW';
    resolution?: string;
  }>;
}
```

3. **Render confidence/iterations** (`DualAgentChat.tsx` - after brain activity toggle button ~line 471):
```tsx
{msg.brainActivity && (
  <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
    {msg.brainActivity.confidenceScore !== undefined && (
      <div className="flex items-center gap-1.5">
        <ShieldCheck className="h-3.5 w-3.5 text-success" />
        <span>Confidence: {(msg.brainActivity.confidenceScore * 100).toFixed(0)}%</span>
      </div>
    )}
    {msg.brainActivity.iterations !== undefined && (
      <div className="flex items-center gap-1.5">
        <RotateCw className="h-3.5 w-3.5 text-accent" />
        <span>{msg.brainActivity.iterations} reflection{msg.brainActivity.iterations !== 1 ? 's' : ''}</span>
      </div>
    )}
  </div>
)}
```

4. **Render contradictions** (inside brain activity expanded section ~line 490):
```tsx
{msg.brainActivity.contradictions && msg.brainActivity.contradictions.length > 0 && (
  <div className="mt-3 border-t border-border pt-3">
    <div className="mb-2 text-xs font-medium text-warning">
      Contradictions Identified ({msg.brainActivity.contradictions.length})
    </div>
    {msg.brainActivity.contradictions.map((contradiction, i) => (
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
```

### 6A.4 - Surface Librarian Reasoning & Relationships

**File**: `src/frontend/components/DualAgentChat.tsx`

**Changes** (line 294-299 - Librarian message creation):
```typescript
const message: ChatMessage = {
  id: Date.now().toString(),
  role: 'assistant',
  content: response.answer,
  citations: response.citations,
  librarianMetadata: {              // ADD NEW FIELD
    reasoning: response.reasoning,
    relationships: response.relationships,
    contextSources: response.context_sources,
  },
  timestamp: new Date(),
};
```

**Update store** (`src/frontend/stores/chatStore.ts`):
```typescript
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  brainActivity?: BrainActivity;
  librarianMetadata?: {           // ADD
    reasoning?: string;
    relationships?: Array<{
      source: string;
      type: string;
      target: string;
      context?: string;
    }>;
    contextSources?: any;
  };
  timestamp: Date;
}
```

**Render** (after citations section in message render):
```tsx
{msg.librarianMetadata?.reasoning && (
  <div className="mt-3 rounded-lg bg-muted/30 p-3 text-xs">
    <div className="mb-1.5 font-medium text-foreground">Reasoning</div>
    <div className="text-muted-foreground">{msg.librarianMetadata.reasoning}</div>
  </div>
)}

{msg.librarianMetadata?.relationships && msg.librarianMetadata.relationships.length > 0 && (
  <div className="mt-2 space-y-1">
    <div className="text-xs font-medium text-muted-foreground">Graph Relationships</div>
    {msg.librarianMetadata.relationships.map((rel, i) => (
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
```

### 6A.5 - Add Token Streaming (Handle `chunk` Events)

**File**: `src/frontend/components/DualAgentChat.tsx`

**Changes**:

1. **Add streaming text state** (after line 185):
```typescript
const [streamingText, setStreamingText] = useState<string>('');
```

2. **Handle chunk events** (line ~210 in handleEvent switch):
```typescript
case 'chunk':
  setStreamingText(prev => prev + data.content);
  break;
```

3. **Clear streaming text on complete** (line ~225):
```typescript
case 'complete':
  setStreamingText(''); // Clear before setting final message
  // ... existing complete logic
  break;
```

4. **Render streaming text** (in progress panel, after thinking log ~line 593):
```tsx
{streamingText && (
  <div className="mt-3 rounded-lg border border-border bg-card p-3">
    <div className="text-xs text-muted-foreground mb-1.5">Generating Response...</div>
    <div className="text-sm text-foreground whitespace-pre-wrap font-serif leading-relaxed">
      {streamingText}
      <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent" />
    </div>
  </div>
)}
```

### 6A.6 - Add Session Memory (session_id)

**Files**:
- `src/frontend/lib/api.ts`
- `src/frontend/components/DualAgentChat.tsx`
- `src/frontend/stores/chatStore.ts`

**Changes**:

1. **Generate session ID** (add to `chatStore.ts`):
```typescript
interface ChatStore {
  // ... existing fields
  cortexSessionId: string;
  librarianSessionId: string;
  // ... rest
}

const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      // ... existing state
      cortexSessionId: crypto.randomUUID(),
      librarianSessionId: crypto.randomUUID(),
      // ... rest
    }),
    { name: 'atlas-chat-storage' }
  )
);
```

2. **Pass session_id** (`DualAgentChat.tsx` line ~198):
```typescript
const result = await streamSwarm(
  query,
  projectId,
  handleEvent,
  mode === 'cortex' ? cortexSessionId : librarianSessionId  // ADD THIS
);
```

3. **Update API signature** (`api.ts` line ~558):
```typescript
export async function streamSwarm(
  query: string,
  projectId: string,
  onEvent: (type: string, data: any) => void,
  sessionId?: string  // ADD
): Promise<SwarmResponse> {
  // ... existing code
  const response = await fetch(`${API_BASE_URL}/api/swarm/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      query,
      session_id: sessionId  // ADD
    }),
  });
  // ... rest
}
```

---

## Phase 6B: Professional Polish & Motion System
**Priority**: HIGH (Pilot UX)
**Estimated effort**: 2 days

### 6B.1 - Install Dependencies

```bash
cd src/frontend
npm install framer-motion@11 cmdk@1.0
npm install --save-dev @types/node
```

### 6B.2 - Typography Density Adjustment

**File**: `src/frontend/app/globals.css`

**Changes** (line ~45):
```css
html {
  font-size: 13px; /* Change from default 16px */
}

@media (max-width: 768px) {
  html {
    font-size: 14px; /* Slightly larger on mobile */
  }
}
```

### 6B.3 - Motion Design System

**Create**: `src/frontend/lib/design-system/motion.ts`

```typescript
export const spring = {
  type: "spring",
  stiffness: 400,
  damping: 30,
} as const;

export const transitions = {
  fast: { duration: 0.15, ease: [0.4, 0, 0.2, 1] },
  base: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
  slow: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
} as const;

export const animations = {
  fadeIn: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideUp: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
  },
  scaleIn: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
} as const;
```

### 6B.4 - Add Layout Animations to Chat Messages

**File**: `src/frontend/components/DualAgentChat.tsx`

**Changes**:

1. **Import** (top of file):
```typescript
import { motion, AnimatePresence } from 'framer-motion';
import { spring, animations } from '@/lib/design-system/motion';
```

2. **Wrap messages** (line ~360 - message list rendering):
```tsx
<AnimatePresence mode="popLayout">
  {messages.map((msg, idx) => (
    <motion.div
      key={msg.id}
      layout
      layoutId={msg.id}
      {...animations.slideUp}
      transition={spring}
    >
      {/* existing message JSX */}
    </motion.div>
  ))}
</AnimatePresence>
```

### 6B.5 - Status Bar with Real Metrics

**File**: `src/frontend/app/project/workspace-page.tsx`

**Changes** (header section, add after model selector ~line 180):
```tsx
<div className="flex items-center gap-3 text-xs text-muted-foreground">
  <div className="flex items-center gap-1.5">
    <Activity className="h-3.5 w-3.5" />
    <span>{graphStore.nodes.length} nodes</span>
  </div>
  <div className="flex items-center gap-1.5">
    <FileText className="h-3.5 w-3.5" />
    <span>{files.filter(f => f.status === 'completed').length} docs</span>
  </div>
  {modelStatus?.device && (
    <div className="flex items-center gap-1.5">
      <Zap className="h-3.5 w-3.5 text-accent" />
      <span>{modelStatus.device.toUpperCase()}</span>
    </div>
  )}
</div>
```

**Import icons**: Add `Activity`, `FileText`, `Zap` to lucide-react imports

### 6B.6 - Elapsed Time Counter for Streaming

**File**: `src/frontend/components/DualAgentChat.tsx`

**Add state** (after line 185):
```typescript
const [startTime, setStartTime] = useState<number | null>(null);
const [elapsedSeconds, setElapsedSeconds] = useState(0);
```

**Add effect** (after other useEffects):
```typescript
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
```

**Set start time** (in handleSubmit, before try block):
```typescript
setStartTime(Date.now());
```

**Render** (in progress panel header ~line 525):
```tsx
<div className="flex items-center justify-between mb-2">
  <div className="text-xs font-medium text-foreground">Processing Query</div>
  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
    <Clock className="h-3 w-3" />
    <span>{elapsedSeconds}s</span>
  </div>
</div>
```

---

## Phase 6C: OmniBar / Command Palette
**Priority**: HIGH (Keyboard Efficiency)
**Estimated effort**: 1-2 days

### 6C.1 - Create OmniBar Component

**Create**: `src/frontend/components/OmniBar.tsx`

```typescript
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
  Settings,
  Home,
  Trash2,
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

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Global Command Menu"
      className="fixed left-1/2 top-[20vh] z-[200] w-full max-w-2xl -translate-x-1/2 rounded-xl border border-border bg-card/95 backdrop-blur-xl shadow-2xl shadow-primary/10"
    >
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Command.Input
          placeholder="Type a command or search..."
          className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
      </div>

      <Command.List className="max-h-96 overflow-y-auto p-2">
        <Command.Empty className="px-4 py-8 text-center text-sm text-muted-foreground">
          No results found.
        </Command.Empty>

        {projectId && (
          <>
            <Command.Group heading="Views" className="mb-2">
              <CommandItem icon={FileText} onSelect={() => { onSwitchView?.('document'); close(); }}>
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
              <CommandItem icon={Network} onSelect={() => { onSwitchView?.('canvas'); close(); }}>
                Research Canvas
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

      <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
        <kbd className="rounded bg-muted px-1.5 py-0.5 font-mono">Cmd/Ctrl K</kbd> to toggle
      </div>
    </Command.Dialog>
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
```

### 6C.2 - Integrate OmniBar into Workspace

**File**: `src/frontend/app/project/workspace-page.tsx`

**Import** (top):
```typescript
import { OmniBar } from '@/components/OmniBar';
```

**Add handlers** (after state declarations ~line 100):
```typescript
const handleUploadClick = () => {
  // Trigger file input in LibrarySidebar
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  input?.click();
};

const handleExport = async (type: 'bibtex' | 'markdown' | 'chat') => {
  // To be wired in Phase 6D
  console.log('Export:', type);
};

const handleViewSwitch = (view: MainView) => {
  setActiveView(view);
};
```

**Render** (at end of return, after </main> ~line 450):
```tsx
<OmniBar
  projectId={projectId}
  onUpload={handleUploadClick}
  onExport={handleExport}
  onSwitchView={handleViewSwitch}
/>
```

### 6C.3 - Add CMD-K Styling to globals.css

**File**: `src/frontend/app/globals.css`

**Add** (at end):
```css
/* Command Palette (cmdk) Overrides */
[cmdk-root] {
  z-index: 200;
}

[cmdk-overlay] {
  position: fixed;
  inset: 0;
  background-color: hsl(var(--background) / 0.5);
  backdrop-filter: blur(4px);
  z-index: 199;
}

[cmdk-group-heading] {
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

kbd {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  border-radius: 0.25rem;
  background-color: hsl(var(--muted));
  color: hsl(var(--foreground));
  border: 1px solid hsl(var(--border));
}
```

---

## Phase 6D: Import/Export UI
**Priority**: HIGH (Pilot Feature)
**Estimated effort**: 1 day

### 6D.1 - Add Import Button to LibrarySidebar

**File**: `src/frontend/components/LibrarySidebar.tsx`

**Add import state** (after line ~30):
```typescript
const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
```

**Add import handler** (after uploadFile function ~line 70):
```typescript
const handleImport = async (file: File) => {
  try {
    toast('Importing bibliography...', 'info');
    const result = await api.importBibtex(file, projectId);
    toast(`Imported ${result.total_imported} of ${result.total_entries} entries`, 'success');
    if (result.skipped.length > 0) {
      console.warn('Skipped entries:', result.skipped);
    }
    refreshFiles();
  } catch (error: any) {
    toastError(`Import failed: ${error.message}`);
  }
};
```

**Add button** (after Upload button ~line 120):
```tsx
<label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border bg-surface px-3 py-2 text-xs text-muted-foreground transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent">
  <FileDown className="h-4 w-4" />
  Import BibTeX/RIS
  <input
    type="file"
    accept=".bib,.ris"
    className="hidden"
    onChange={(e) => {
      const file = e.target.files?.[0];
      if (file) handleImport(file);
      e.target.value = '';
    }}
  />
</label>
```

**Import icons**: Add `FileDown` to lucide-react imports

### 6D.2 - Add Export Menu to Workspace Header

**File**: `src/frontend/app/project/workspace-page.tsx`

**Add export state** (after line ~60):
```typescript
const [exportMenuOpen, setExportMenuOpen] = useState(false);
```

**Add export handlers** (replace console.log from 6C.2):
```typescript
const handleExport = async (type: 'bibtex' | 'markdown' | 'chat') => {
  try {
    toast(`Exporting ${type}...`, 'info');

    if (type === 'bibtex') {
      await api.exportProjectBibtex(projectId);
      toast('BibTeX export complete', 'success');
    } else if (type === 'markdown') {
      // Get editor content from localStorage
      const editorContent = localStorage.getItem(`atlas-editor-${projectId}`);
      if (!editorContent) {
        toastError('No editor content to export');
        return;
      }

      const result = await api.exportMarkdown({
        content: editorContent,
        citations: [],
        project_id: projectId,
        title: project?.name || 'Untitled',
        author: 'Atlas User',
        style: 'apa',
      });

      // Download the markdown file
      const blob = new Blob([result.markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename;
      a.click();
      URL.revokeObjectURL(url);

      toast('Markdown export complete', 'success');
    } else if (type === 'chat') {
      const messages = useChatStore.getState().cortexMessages.concat(
        useChatStore.getState().librarianMessages
      );
      const result = await api.exportChatHistory(messages, project?.name);

      const blob = new Blob([result.markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${project?.name || 'chat'}-history.md`;
      a.click();
      URL.revokeObjectURL(url);

      toast('Chat history exported', 'success');
    }
  } catch (error: any) {
    toastError(`Export failed: ${error.message}`);
  }
};
```

**Add export dropdown** (in header, after model selector ~line 200):
```tsx
<div className="relative">
  <button
    onClick={() => setExportMenuOpen(!exportMenuOpen)}
    className="flex h-8 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-xs text-foreground hover:bg-surface/80"
  >
    <Download className="h-3.5 w-3.5" />
    Export
    <ChevronDown className="h-3 w-3" />
  </button>

  {exportMenuOpen && (
    <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-border bg-card shadow-xl z-50">
      <div className="p-1">
        <button
          onClick={() => { handleExport('bibtex'); setExportMenuOpen(false); }}
          className="w-full flex items-center gap-2 rounded px-3 py-2 text-xs text-foreground hover:bg-primary/10"
        >
          <FileCode className="h-4 w-4" />
          BibTeX (.bib)
        </button>
        <button
          onClick={() => { handleExport('markdown'); setExportMenuOpen(false); }}
          className="w-full flex items-center gap-2 rounded px-3 py-2 text-xs text-foreground hover:bg-primary/10"
        >
          <FileText className="h-4 w-4" />
          Markdown (.md)
        </button>
        <button
          onClick={() => { handleExport('chat'); setExportMenuOpen(false); }}
          className="w-full flex items-center gap-2 rounded px-3 py-2 text-xs text-foreground hover:bg-primary/10"
        >
          <MessageSquare className="h-4 w-4" />
          Chat History
        </button>
      </div>
    </div>
  )}
</div>
```

**Import icons**: Add `Download`, `ChevronDown`, `FileCode` to lucide-react imports

**Close menu on outside click** (add effect):
```typescript
useEffect(() => {
  if (!exportMenuOpen) return;
  const handleClick = () => setExportMenuOpen(false);
  document.addEventListener('click', handleClick);
  return () => document.removeEventListener('click', handleClick);
}, [exportMenuOpen]);
```

---

## Phase 6E: Research Canvas Integration
**Priority**: MEDIUM (Spatial Organization)
**Estimated effort**: 3-4 days

### 6E.1 - Upgrade to @xyflow/react v12

```bash
cd src/frontend
npm uninstall @reactflow/core @reactflow/background @reactflow/controls @reactflow/minimap
npm install @xyflow/react@12
```

### 6E.2 - Create Canvas Store

**Create**: `src/frontend/stores/canvasStore.ts`

```typescript
import { create } from 'zustand';
import { Node, Edge } from '@xyflow/react';

interface CanvasStore {
  nodes: Node[];
  edges: Edge[];
  addNode: (node: Node) => void;
  updateNode: (id: string, updates: Partial<Node>) => void;
  removeNode: (id: string) => void;
  addEdge: (edge: Edge) => void;
  removeEdge: (id: string) => void;
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  clearCanvas: () => void;
}

export const useCanvasStore = create<CanvasStore>((set) => ({
  nodes: [],
  edges: [],

  addNode: (node) => set((state) => ({
    nodes: [...state.nodes, node],
  })),

  updateNode: (id, updates) => set((state) => ({
    nodes: state.nodes.map((n) => n.id === id ? { ...n, ...updates } : n),
  })),

  removeNode: (id) => set((state) => ({
    nodes: state.nodes.filter((n) => n.id !== id),
    edges: state.edges.filter((e) => e.source !== id && e.target !== id),
  })),

  addEdge: (edge) => set((state) => ({
    edges: [...state.edges, edge],
  })),

  removeEdge: (id) => set((state) => ({
    edges: state.edges.filter((e) => e.id !== id),
  })),

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  clearCanvas: () => set({ nodes: [], edges: [] }),
}));
```

### 6E.3 - Create Custom Node Components

**Create**: `src/frontend/components/canvas/DocumentNode.tsx`

```typescript
'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { FileText, Trash2 } from 'lucide-react';

interface DocumentNodeData {
  filename: string;
  pageCount?: number;
  status?: string;
  onOpen?: () => void;
  onDelete?: () => void;
}

export const DocumentNode = memo(({ data }: NodeProps<DocumentNodeData>) => {
  return (
    <div className="group w-64 rounded-xl border border-border bg-card p-4 shadow-lg hover:border-primary/40 hover:shadow-xl transition-all">
      <Handle type="target" position={Position.Top} className="!bg-accent" />

      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          <FileText className="h-5 w-5 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-foreground line-clamp-2 mb-1">
            {data.filename}
          </div>
          {data.pageCount && (
            <div className="text-xs text-muted-foreground">
              {data.pageCount} pages
            </div>
          )}
        </div>

        <button
          onClick={data.onDelete}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-destructive/10 rounded"
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </button>
      </div>

      {data.status && (
        <div className="mt-2 text-xs text-muted-foreground">
          Status: {data.status}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-accent" />
    </div>
  );
});

DocumentNode.displayName = 'DocumentNode';
```

**Create**: `src/frontend/components/canvas/InsightNode.tsx`

```typescript
'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Sparkles } from 'lucide-react';

interface InsightNodeData {
  content: string;
  brain?: string;
  timestamp?: Date;
}

export const InsightNode = memo(({ data }: NodeProps<InsightNodeData>) => {
  return (
    <div className="w-80 rounded-xl border border-accent/40 bg-card p-4 shadow-lg">
      <Handle type="target" position={Position.Top} className="!bg-accent" />

      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="h-4 w-4 text-accent" />
        <span className="text-xs font-medium text-accent uppercase tracking-wide">
          {data.brain || 'Insight'}
        </span>
      </div>

      <div className="text-sm text-foreground leading-relaxed">
        {data.content}
      </div>

      {data.timestamp && (
        <div className="mt-2 text-xs text-muted-foreground">
          {new Date(data.timestamp).toLocaleString()}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-accent" />
    </div>
  );
});

InsightNode.displayName = 'InsightNode';
```

### 6E.4 - Create Research Canvas Component

**Create**: `src/frontend/components/ResearchCanvas.tsx`

```typescript
'use client';

import { useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  BackgroundVariant,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { DocumentNode } from './canvas/DocumentNode';
import { InsightNode } from './canvas/InsightNode';
import { useCanvasStore } from '@/stores/canvasStore';
import { ZoomIn, ZoomOut, Maximize2, Trash2 } from 'lucide-react';

const nodeTypes = {
  document: DocumentNode,
  insight: InsightNode,
};

interface ResearchCanvasProps {
  projectId: string;
}

export function ResearchCanvas({ projectId }: ResearchCanvasProps) {
  const canvasStore = useCanvasStore();
  const [nodes, setNodes, onNodesChange] = useNodesState(canvasStore.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(canvasStore.edges);

  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge = addEdge(params, edges);
      setEdges(newEdge);
      canvasStore.setEdges(newEdge);
    },
    [edges, setEdges, canvasStore]
  );

  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChange(changes);
      // Sync to store after a delay (debounce)
      setTimeout(() => canvasStore.setNodes(nodes), 300);
    },
    [onNodesChange, nodes, canvasStore]
  );

  return (
    <div className="h-full w-full bg-background relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: true,
          style: { stroke: 'hsl(var(--accent))' },
        }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={16}
          size={1}
          color="hsl(var(--border))"
        />

        <Controls
          className="!border-border !bg-card/95 !backdrop-blur-sm"
          showInteractive={false}
        />

        <MiniMap
          className="!border-border !bg-card/95 !backdrop-blur-sm"
          nodeColor="hsl(var(--primary))"
          maskColor="hsl(var(--background) / 0.8)"
        />

        <Panel position="top-left" className="flex gap-2">
          <button className="flex items-center gap-2 rounded-lg border border-border bg-card/95 backdrop-blur-sm px-3 py-2 text-xs text-foreground hover:bg-primary/10">
            <Trash2 className="h-3.5 w-3.5" />
            Clear Canvas
          </button>
        </Panel>

        <Panel position="top-right" className="text-xs text-muted-foreground bg-card/95 backdrop-blur-sm rounded-lg border border-border px-3 py-2">
          {nodes.length} nodes · {edges.length} connections
        </Panel>
      </ReactFlow>
    </div>
  );
}
```

### 6E.5 - Add Canvas Tab to Workspace

**File**: `src/frontend/app/project/workspace-page.tsx`

**Update type** (line ~50):
```typescript
type MainView = 'document' | 'editor' | 'graph' | 'chat' | 'canvas';
```

**Add tab** (in VIEW_TABS array ~line 54):
```typescript
{ id: 'canvas', icon: Layers, label: 'Canvas' },
```

**Import** (top):
```typescript
import { ResearchCanvas } from '@/components/ResearchCanvas';
import { Layers } from 'lucide-react';
```

**Add render case** (in content area ~line 380):
```typescript
{activeView === 'canvas' && <ResearchCanvas projectId={projectId} />}
```

### 6E.6 - Canvas Drag-and-Drop from Library

**File**: `src/frontend/components/LibrarySidebar.tsx`

**Add drag handler** (in file item rendering ~line 150):
```tsx
<div
  draggable
  onDragStart={(e) => {
    e.dataTransfer.setData('application/atlas-document', JSON.stringify({
      id: file.id,
      filename: file.filename,
      status: file.status,
    }));
  }}
  className="cursor-move"  // Add to existing classes
>
  {/* existing file item JSX */}
</div>
```

**File**: `src/frontend/components/ResearchCanvas.tsx`

**Add drop handler** (in ReactFlow component):
```typescript
const onDrop = useCallback(
  (event: React.DragEvent) => {
    event.preventDefault();
    const data = event.dataTransfer.getData('application/atlas-document');
    if (!data) return;

    const doc = JSON.parse(data);
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = {
      x: event.clientX - bounds.left - 128, // Half node width
      y: event.clientY - bounds.top - 50,
    };

    const newNode = {
      id: `doc-${doc.id}`,
      type: 'document',
      position,
      data: {
        filename: doc.filename,
        status: doc.status,
        onOpen: () => console.log('Open doc:', doc.id),
        onDelete: () => canvasStore.removeNode(`doc-${doc.id}`),
      },
    };

    canvasStore.addNode(newNode);
    setNodes([...nodes, newNode]);
  },
  [nodes, setNodes, canvasStore]
);

const onDragOver = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
}, []);
```

**Add to ReactFlow**:
```tsx
<ReactFlow
  onDrop={onDrop}
  onDragOver={onDragOver}
  // ... other props
>
```

---

## Phase 6F: Generative UI Components
**Priority**: MEDIUM (Enhanced Chat)
**Estimated effort**: 2-3 days

### 6F.1 - Create ComparisonTable Component

**Create**: `src/frontend/components/generative/ComparisonTable.tsx`

```typescript
'use client';

import { ArrowUpDown, Check, X, Minus } from 'lucide-react';
import { useState } from 'react';

interface ComparisonRow {
  feature: string;
  values: (string | boolean | null)[];
}

interface ComparisonTableProps {
  headers: string[]; // Column headers (e.g., document names)
  rows: ComparisonRow[];
}

export function ComparisonTable({ headers, rows }: ComparisonTableProps) {
  const [sortBy, setSortBy] = useState<number | null>(null);

  const renderCell = (value: string | boolean | null) => {
    if (typeof value === 'boolean') {
      return value ? (
        <Check className="h-4 w-4 text-success" />
      ) : (
        <X className="h-4 w-4 text-destructive" />
      );
    }
    if (value === null) {
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    }
    return <span className="text-sm">{value}</span>;
  };

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-border bg-muted/30">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Feature
              </th>
              {headers.map((header, i) => (
                <th
                  key={i}
                  className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground"
                  onClick={() => setSortBy(i)}
                >
                  <div className="flex items-center gap-1.5">
                    {header}
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-surface/50 transition-colors">
                <td className="px-4 py-3 text-sm font-medium text-foreground whitespace-nowrap">
                  {row.feature}
                </td>
                {row.values.map((value, j) => (
                  <td key={j} className="px-4 py-3">
                    {renderCell(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### 6F.2 - Create MetricCard Component

**Create**: `src/frontend/components/generative/MetricCard.tsx`

```typescript
'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: number | string;
  change?: number; // Percentage change
  unit?: string;
  color?: 'primary' | 'accent' | 'success' | 'warning' | 'destructive';
}

export function MetricCard({ label, value, change, unit, color = 'primary' }: MetricCardProps) {
  const colorClasses = {
    primary: 'from-primary/20 to-primary/5 border-primary/20',
    accent: 'from-accent/20 to-accent/5 border-accent/20',
    success: 'from-success/20 to-success/5 border-success/20',
    warning: 'from-warning/20 to-warning/5 border-warning/20',
    destructive: 'from-destructive/20 to-destructive/5 border-destructive/20',
  };

  const valueColorClasses = {
    primary: 'text-primary',
    accent: 'text-accent',
    success: 'text-success',
    warning: 'text-warning',
    destructive: 'text-destructive',
  };

  return (
    <div className={`inline-flex flex-col gap-2 rounded-xl border bg-gradient-to-br p-4 min-w-[140px] ${colorClasses[color]}`}>
      <div className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className={`text-2xl font-semibold ${valueColorClasses[color]}`}>
        {value}
        {unit && <span className="ml-1 text-sm text-muted-foreground">{unit}</span>}
      </div>
      {change !== undefined && (
        <div className="flex items-center gap-1 text-xs">
          {change > 0 ? (
            <TrendingUp className="h-3 w-3 text-success" />
          ) : change < 0 ? (
            <TrendingDown className="h-3 w-3 text-destructive" />
          ) : (
            <Minus className="h-3 w-3 text-muted-foreground" />
          )}
          <span className={change > 0 ? 'text-success' : change < 0 ? 'text-destructive' : 'text-muted-foreground'}>
            {Math.abs(change)}%
          </span>
        </div>
      )}
    </div>
  );
}
```

### 6F.3 - Detect and Render Generative UI in Chat

**File**: `src/frontend/components/DualAgentChat.tsx`

**Add detection function** (after imports):
```typescript
const detectGenerativeContent = (content: string) => {
  // Detect comparison tables (markdown tables with specific patterns)
  const tableRegex = /\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n)+)/g;
  // Detect metric patterns like "Accuracy: 95%" or "Count: 42 documents"
  const metricRegex = /\*\*([^:]+):\*\*\s*(\d+\.?\d*)(%|\s*\w+)?/g;

  return {
    hasTable: tableRegex.test(content),
    hasMetrics: metricRegex.test(content),
  };
};
```

**Modify message rendering** (in MarkdownContent or message bubble):
```typescript
// Before rendering markdown, check for generative content
const generative = detectGenerativeContent(msg.content);

// If table detected, parse and render ComparisonTable
// If metrics detected, parse and render MetricCard grid
// Otherwise, render standard markdown
```

**Note**: Full implementation of markdown-to-component parsing is complex. For pilot, manually trigger generative components via specific AI response formatting or use a simple keyword trigger system.

---

## Phase 6G: Onboarding & Empty States
**Priority**: LOW (UX Polish)
**Estimated effort**: 1-2 days

### 6G.1 - Create Welcome Tour Component

**Create**: `src/frontend/components/WelcomeTour.tsx`

```typescript
'use client';

import { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface TourStep {
  target: string; // CSS selector
  title: string;
  description: string;
  placement: 'top' | 'bottom' | 'left' | 'right';
}

const TOUR_STEPS: TourStep[] = [
  {
    target: '.library-sidebar',
    title: 'Document Library',
    description: 'Upload PDFs, search your documents, and see ingestion status here.',
    placement: 'right',
  },
  {
    target: '.view-tabs',
    title: 'Research Views',
    description: 'Switch between Documents, Editor, Knowledge Graph, Deep Chat, and Canvas.',
    placement: 'bottom',
  },
  {
    target: '.context-engine',
    title: 'Context Engine',
    description: 'See related concepts, citations, and graph insights automatically.',
    placement: 'left',
  },
];

export function WelcomeTour() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('atlas-tour-seen');
    if (!hasSeenTour) {
      setTimeout(() => setIsOpen(true), 1000);
    }
  }, []);

  const handleComplete = () => {
    localStorage.setItem('atlas-tour-seen', 'true');
    setIsOpen(false);
  };

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[300] pointer-events-none">
        {/* Overlay */}
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm pointer-events-auto" />

        {/* Spotlight on target */}
        <div className="absolute inset-0 pointer-events-none" style={{ /* Calculate spotlight position */ }} />

        {/* Tooltip */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className="absolute pointer-events-auto max-w-sm rounded-xl border border-primary/40 bg-card p-6 shadow-2xl"
          style={{ /* Position based on step.target and step.placement */ }}
        >
          <button
            onClick={handleComplete}
            className="absolute right-2 top-2 p-1 hover:bg-surface rounded"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="text-sm font-semibold text-foreground mb-2">
            {step.title}
          </div>
          <div className="text-sm text-muted-foreground mb-4">
            {step.description}
          </div>

          <div className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              {currentStep + 1} of {TOUR_STEPS.length}
            </div>
            <div className="flex gap-2">
              {currentStep > 0 && (
                <button
                  onClick={() => setCurrentStep(currentStep - 1)}
                  className="flex items-center gap-1 rounded-lg bg-surface px-3 py-1.5 text-xs hover:bg-surface/80"
                >
                  <ChevronLeft className="h-3 w-3" />
                  Back
                </button>
              )}
              <button
                onClick={() => {
                  if (currentStep < TOUR_STEPS.length - 1) {
                    setCurrentStep(currentStep + 1);
                  } else {
                    handleComplete();
                  }
                }}
                className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
              >
                {currentStep < TOUR_STEPS.length - 1 ? 'Next' : 'Finish'}
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
```

### 6G.2 - Enhanced Empty States

**File**: `src/frontend/components/LibrarySidebar.tsx`

**Replace empty state** (~line 200):
```tsx
{files.length === 0 && !loading && (
  <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
    <div className="mb-4 rounded-full bg-primary/10 p-4">
      <Upload className="h-8 w-8 text-primary" />
    </div>
    <div className="mb-2 text-sm font-medium text-foreground">
      No documents yet
    </div>
    <div className="mb-4 text-xs text-muted-foreground">
      Upload PDFs to build your research library
    </div>
    <div className="text-xs text-muted-foreground space-y-1">
      <div>• Drag & drop files</div>
      <div>• Import from BibTeX</div>
      <div>• Auto-extract entities</div>
    </div>
  </div>
)}
```

**File**: `src/frontend/components/DualAgentChat.tsx`

**Enhance suggestion chips** (~line 360):
```tsx
{messages.length === 0 && !isLoading && (
  <div className="flex h-full flex-col items-center justify-center px-6 text-center">
    <div className="mb-6 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 p-6">
      <Brain className="h-12 w-12 text-primary" />
    </div>
    <div className="mb-2 text-lg font-serif font-semibold text-foreground">
      Deep Research Assistant
    </div>
    <div className="mb-6 max-w-md text-sm text-muted-foreground">
      Ask complex questions and get answers backed by your documents with full citations and reasoning traces.
    </div>
    <div className="grid gap-2 sm:grid-cols-2">
      {[
        'Compare methodologies across papers',
        'Identify contradictions in findings',
        'Summarize key contributions',
        'Find evidence for a claim',
      ].map((suggestion) => (
        <button
          key={suggestion}
          onClick={() => {/* Pre-fill suggestion */}}
          className="rounded-lg border border-border bg-surface px-4 py-3 text-left text-xs hover:border-primary/40 hover:bg-primary/5"
        >
          {suggestion}
        </button>
      ))}
    </div>
  </div>
)}
```

---

## Verification & Testing

### End-to-End Test Scenarios

1. **Data Completeness**
   - Upload a document
   - Ask a Deep Discovery question in Cortex mode
   - Verify: confidence score displayed, grounding badges on citations, contradictions panel if any
   - Ask a Librarian question
   - Verify: reasoning section displayed, relationships shown

2. **Streaming**
   - Ask a complex Cortex question
   - Verify: elapsed timer visible, thinking log updates live, token streaming visible in progress panel
   - Verify: no SSE events lost (check browser DevTools Network tab for complete event stream)

3. **Import/Export**
   - Import a .bib file via LibrarySidebar
   - Verify: documents imported, toast shown with count
   - Export project as BibTeX via header menu
   - Verify: .bib file downloaded
   - Write content in Editor
   - Export as Markdown
   - Verify: .md file with Pandoc-compatible frontmatter

4. **OmniBar**
   - Press Cmd/Ctrl+K
   - Verify: command palette opens with all views, actions, navigation
   - Select "Upload Documents"
   - Verify: file dialog opens
   - Select "Research Canvas"
   - Verify: switches to Canvas tab

5. **Research Canvas**
   - Switch to Canvas tab
   - Drag a document from library onto canvas
   - Verify: Document node appears at drop position
   - Drag another document
   - Shift-drag connection between them
   - Verify: edge appears with animation
   - Click node delete button
   - Verify: node and connected edges removed

6. **Motion & Polish**
   - Open chat, send message
   - Verify: message slides up with spring physics
   - Switch between tabs
   - Verify: transitions smooth, no layout shift
   - Check typography density (should feel information-dense, professional)

7. **Onboarding**
   - Clear `localStorage.getItem('atlas-tour-seen')`
   - Reload workspace
   - Verify: Welcome tour appears after 1s delay
   - Step through tour
   - Verify: tooltips position correctly, spotlight highlights targets

---

## Dependencies Summary

### New packages to install
```bash
npm install framer-motion@11 cmdk@1.0 @xyflow/react@12
npm uninstall @reactflow/core @reactflow/background @reactflow/controls @reactflow/minimap
```

### Critical Files Created
- `src/frontend/lib/design-system/motion.ts`
- `src/frontend/components/OmniBar.tsx`
- `src/frontend/stores/canvasStore.ts`
- `src/frontend/components/canvas/DocumentNode.tsx`
- `src/frontend/components/canvas/InsightNode.tsx`
- `src/frontend/components/ResearchCanvas.tsx`
- `src/frontend/components/generative/ComparisonTable.tsx`
- `src/frontend/components/generative/MetricCard.tsx`
- `src/frontend/components/WelcomeTour.tsx`

### Critical Files Modified
- `src/frontend/lib/api.ts` (SSE buffer fix, type extensions)
- `src/frontend/components/DualAgentChat.tsx` (grounding, confidence, streaming, Librarian metadata)
- `src/frontend/stores/chatStore.ts` (session IDs, extended message types)
- `src/frontend/app/project/workspace-page.tsx` (Canvas tab, OmniBar, export menu, status bar)
- `src/frontend/components/LibrarySidebar.tsx` (import button, drag handlers, empty state)
- `src/frontend/app/globals.css` (13px base font, cmdk styles)

---

## Implementation Order (Recommended)

1. **Phase 6A** (2-3 days) - Data gaps are pilot blockers; fix first
2. **Phase 6D** (1 day) - Import/Export UI is high-value, low-complexity
3. **Phase 6B** (2 days) - Polish makes everything else feel better
4. **Phase 6C** (1-2 days) - OmniBar is high-impact UX win
5. **Phase 6E** (3-4 days) - Canvas is complex; do after foundations solid
6. **Phase 6F** (2-3 days) - Generative UI is incremental enhancement
7. **Phase 6G** (1-2 days) - Onboarding polish last

**Total estimated effort**: 12-17 days (2.5-3.5 weeks)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| SSE buffer fix breaks existing streaming | Test thoroughly with slow network simulation; add unit tests |
| @xyflow/react v12 API differences from v11 | Review migration guide; v12 has simpler API, should be straightforward |
| Canvas performance with many nodes | Implement virtualization if >100 nodes; use `nodesDraggable={false}` for read-only mode |
| Framer Motion bundle size impact | Tree-shake carefully; only import needed functions; consider lazy-loading |
| Grounding data structure mismatch | Validate backend SSE event shape matches frontend types; add type guards |

---

## Success Criteria (Pilot-Ready)

- [ ] All backend data (confidence, grounding, contradictions, reasoning, relationships) visible in UI
- [ ] No SSE events dropped; streaming robust
- [ ] Import/Export fully functional (BibTeX, Markdown, Chat)
- [ ] Keyboard-first workflow via OmniBar
- [ ] Canvas enables spatial document organization
- [ ] Professional aesthetic (no gradients, high density, smooth motion)
- [ ] Active feedback during all operations (no blank loading states)
- [ ] Onboarding experience for new users
- [ ] RTX 3050 performance validated (60fps UI, <2s response latency)
