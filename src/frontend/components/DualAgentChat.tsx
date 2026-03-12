/**
 * Thin re-export shim.
 *
 * The monolith that used to live here has been decomposed into:
 *   - chat/ChatShell.tsx      (container + orchestration)
 *   - chat/ConversationView.tsx (message rendering)
 *   - chat/RunProgressDisplay.tsx (streaming progress)
 *   - chat/CommandSurface.tsx  (input area)
 *
 * This file exists so every existing `import DualAgentChat from
 * '@/components/DualAgentChat'` keeps working without a find-replace.
 */

export { default } from './chat/ChatShell';
