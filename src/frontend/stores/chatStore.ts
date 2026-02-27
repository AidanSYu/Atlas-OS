/**
 * Persistent Multi-Agent Chat Store
 *
 * Manages separate chat histories and input states for Librarian (green),
 * Cortex (purple), MoE (blue), and Discovery (orange) agents.
 * History is cleared when a new project is started.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{
    source: string;
    page: number;
    doc_id?: string;
    relevance?: number;
    text?: string;
  }>;
  brainActivity?: {
    brain: string;
    trace: string[];
    evidence: Array<{
      source: string;
      page: number;
      excerpt: string;
      relevance: number;
    }>;
    confidenceScore?: number;
    iterations?: number;
    contradictions?: Array<{
      claim_a: string;
      claim_b: string;
      severity: 'HIGH' | 'LOW';
      resolution?: string;
    }>;
    candidates?: Array<{
      smiles: string;
      properties?: Record<string, any>;
      toxicity?: Record<string, any>;
    }>;
  };
  librarianMetadata?: {
    reasoning?: string;
    relationships?: Array<{
      source: string;
      type: string;
      target: string;
      context?: string;
    }>;
    contextSources?: any;
  };
  timestamp: number;
}

interface ChatState {
  // Librarian (green) chat state
  librarianMessages: ChatMessage[];
  librarianInput: string;
  librarianSessionId: string;

  // Cortex (purple) chat state
  cortexMessages: ChatMessage[];
  cortexInput: string;
  cortexSessionId: string;

  // MoE (blue) chat state
  moeMessages: ChatMessage[];
  moeInput: string;
  moeSessionId: string;

  // Discovery (orange) chat state
  discoveryMessages: ChatMessage[];
  discoveryInput: string;
  discoverySessionId: string;

  // Current active project (for clearing on project change)
  activeProjectId: string | null;

  // Pending question (pre-filled from other views, e.g. "Ask about this page")
  pendingQuestion: string | null;

  // Phase 4: Pending hypotheses for MoE user-in-the-loop interaction
  pendingHypotheses: any[] | null;

  // Actions
  addLibrarianMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  addCortexMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  addMoeMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  addDiscoveryMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  setLibrarianInput: (input: string) => void;
  setCortexInput: (input: string) => void;
  setMoeInput: (input: string) => void;
  setDiscoveryInput: (input: string) => void;
  clearLibrarianChat: () => void;
  clearCortexChat: () => void;
  clearMoeChat: () => void;
  clearDiscoveryChat: () => void;
  clearAllChats: () => void;
  setActiveProject: (projectId: string | null) => void;
  setPendingQuestion: (question: string | null) => void;
  setPendingHypotheses: (hypotheses: any[] | null) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

// Welcome messages for each agent
const LIBRARIAN_WELCOME: ChatMessage = {
  id: 'librarian-welcome',
  role: 'assistant',
  content: "I'm your **Librarian**. I specialize in document analysis and can answer questions about your uploaded research papers. Ask me anything about the content of your documents.",
  timestamp: Date.now(),
};

const CORTEX_WELCOME: ChatMessage = {
  id: 'cortex-welcome',
  role: 'assistant',
  content: "I'm **Cortex**, your research analysis agent. I can cross-reference documents, identify patterns across your research, and help you discover connections that might not be immediately obvious.",
  timestamp: Date.now(),
};

const MOE_WELCOME: ChatMessage = {
  id: 'moe-welcome',
  role: 'assistant',
  content: "I'm the **Mixture of Experts (MoE) Supervisor**. I manage a team of specialized agents (Hypothesis, Retrieval, Writer, Critic). Ask a complex research question, and I'll orchestrate the team to synthesize a highly grounded answer.",
  timestamp: Date.now(),
};

const DISCOVERY_WELCOME: ChatMessage = {
  id: 'discovery-welcome',
  role: 'assistant',
  content: "I'm the **Discovery OS**. I use deterministic chemistry tools to predict molecular properties, check toxicity, and search your literature. Ask me about any molecule or scientific computation -- I'll call the right tools and show you verifiable results.",
  timestamp: Date.now(),
};

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // Initial state
      librarianMessages: [LIBRARIAN_WELCOME],
      librarianInput: '',
      librarianSessionId: crypto.randomUUID(),
      cortexMessages: [CORTEX_WELCOME],
      cortexInput: '',
      cortexSessionId: crypto.randomUUID(),
      moeMessages: [MOE_WELCOME],
      moeInput: '',
      moeSessionId: crypto.randomUUID(),
      discoveryMessages: [DISCOVERY_WELCOME],
      discoveryInput: '',
      discoverySessionId: crypto.randomUUID(),
      activeProjectId: null,
      pendingQuestion: null,
      pendingHypotheses: null,

      addLibrarianMessage: (message) =>
        set((state) => ({
          librarianMessages: [
            ...state.librarianMessages,
            { ...message, id: generateId(), timestamp: Date.now() },
          ],
        })),

      addCortexMessage: (message) =>
        set((state) => ({
          cortexMessages: [
            ...state.cortexMessages,
            { ...message, id: generateId(), timestamp: Date.now() },
          ],
        })),

      addMoeMessage: (message) =>
        set((state) => ({
          moeMessages: [
            ...state.moeMessages,
            { ...message, id: generateId(), timestamp: Date.now() },
          ],
        })),

      addDiscoveryMessage: (message) =>
        set((state) => ({
          discoveryMessages: [
            ...state.discoveryMessages,
            { ...message, id: generateId(), timestamp: Date.now() },
          ],
        })),

      setLibrarianInput: (input) => set({ librarianInput: input }),
      setCortexInput: (input) => set({ cortexInput: input }),
      setMoeInput: (input) => set({ moeInput: input }),
      setDiscoveryInput: (input) => set({ discoveryInput: input }),

      clearLibrarianChat: () =>
        set({ librarianMessages: [LIBRARIAN_WELCOME], librarianInput: '' }),

      clearCortexChat: () =>
        set({ cortexMessages: [CORTEX_WELCOME], cortexInput: '' }),

      clearMoeChat: () =>
        set({ moeMessages: [MOE_WELCOME], moeInput: '' }),

      clearDiscoveryChat: () =>
        set({ discoveryMessages: [DISCOVERY_WELCOME], discoveryInput: '' }),

      clearAllChats: () =>
        set({
          librarianMessages: [LIBRARIAN_WELCOME],
          librarianInput: '',
          cortexMessages: [CORTEX_WELCOME],
          cortexInput: '',
          moeMessages: [MOE_WELCOME],
          moeInput: '',
          discoveryMessages: [DISCOVERY_WELCOME],
          discoveryInput: '',
        }),

      setActiveProject: (projectId) => {
        const currentProjectId = get().activeProjectId;
        // Only clear if project actually changed
        if (projectId !== currentProjectId) {
          set({
            activeProjectId: projectId,
            librarianMessages: [LIBRARIAN_WELCOME],
            librarianInput: '',
            cortexMessages: [CORTEX_WELCOME],
            cortexInput: '',
            moeMessages: [MOE_WELCOME],
            moeInput: '',
            discoveryMessages: [DISCOVERY_WELCOME],
            discoveryInput: '',
            pendingQuestion: null,
          });
        }
      },

      setPendingQuestion: (question) => set({ pendingQuestion: question }),

      setPendingHypotheses: (hypotheses) =>
        set({ pendingHypotheses: hypotheses }),
    }),
    {
      name: 'atlas-chat-storage',
      version: 3,
      storage: createJSONStorage(() => localStorage),
      // Only persist messages and inputs, not the project ID (we check that on load)
      partialize: (state) => ({
        librarianMessages: state.librarianMessages,
        librarianInput: state.librarianInput,
        librarianSessionId: state.librarianSessionId,
        cortexMessages: state.cortexMessages,
        cortexInput: state.cortexInput,
        cortexSessionId: state.cortexSessionId,
        moeMessages: state.moeMessages,
        moeInput: state.moeInput,
        moeSessionId: state.moeSessionId,
        discoveryMessages: state.discoveryMessages,
        discoveryInput: state.discoveryInput,
        discoverySessionId: state.discoverySessionId,
        activeProjectId: state.activeProjectId,
      }),
    }
  )
);
