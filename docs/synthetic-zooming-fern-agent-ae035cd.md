# Zero-Prompt Framework Research for Atlas 2.0

## Research Report: Zero-Prompt UX Patterns for AI-Powered Research Tools

---

## Table of Contents
1. [The Problem Statement](#1-the-problem-statement)
2. [Competitive Landscape Analysis](#2-competitive-landscape-analysis)
3. [Catalog of Zero-Prompt UX Patterns](#3-catalog-of-zero-prompt-ux-patterns)
4. [Design Principles](#4-design-principles)
5. [What Atlas Already Has](#5-what-atlas-already-has)
6. [Implementation Strategy for Atlas](#6-implementation-strategy-for-atlas)
7. [Concrete Feature Blueprints](#7-concrete-feature-blueprints)

---

## 1. The Problem Statement

The blank text box is the single biggest failure mode in AI-powered tools. When a researcher opens a chatbot-style interface, they face three compounding problems:

1. **The Prompt Engineering Tax**: Users must know *how* to ask, not just *what* to ask. The quality of output is directly coupled to prompt sophistication.
2. **The Cold Start Problem**: A blank input field provides zero affordance. The user has no idea what the system can do, what it knows, or what would be a productive next step.
3. **The Context Collapse**: Chat interfaces flatten rich, multi-dimensional research workflows into a single linear text stream. Research is not a conversation -- it is exploration, comparison, synthesis, and annotation happening in parallel.

**The zero-prompt philosophy**: The best AI interface is one where the user never has to write a prompt at all. The system should *always know what to suggest next* based on the user's context, and the user's job is to accept, modify, or redirect -- never to start from scratch.

---

## 2. Competitive Landscape Analysis

### 2.1 Elicit (elicit.com) -- "Structured Research Workflows"

**Key Zero-Prompt Patterns:**
- **Structured Question Decomposition**: Instead of a blank text box, Elicit asks "What is your research question?" and then *automatically decomposes it* into sub-questions. The user does not need to know how to prompt -- they just state their question in natural language and Elicit structures the workflow.
- **Column-Based Extraction**: After finding papers, Elicit presents a spreadsheet-like interface where users can add columns (e.g., "Sample Size", "Methodology", "Key Finding"). The AI auto-fills these columns for each paper. The user never writes extraction prompts -- they just pick columns.
- **Paper Discovery Flow**: Upload a seed paper or type a question -> Elicit finds relevant papers -> presents them in a structured table -> lets you drill into any paper -> auto-generates summaries. Each step *suggests* the next step.
- **Follow-Up Suggestions**: After generating a summary, Elicit suggests follow-up questions based on the content. The user clicks instead of typing.

**What Atlas Can Steal:**
- The column-based extraction interface for document comparison
- Auto-generated follow-up questions after every AI response
- Structured workflows that replace "chat with your documents"

### 2.2 Consensus (consensus.app) -- "Evidence-First Search"

**Key Zero-Prompt Patterns:**
- **Search Bar as Intent Detector**: Consensus's search bar looks like Google, but it routes to an evidence synthesis engine. Users type natural language questions and get synthesized answers with "Consensus Meter" showing agreement levels across papers.
- **Claim-Level Extraction**: Instead of showing full papers, Consensus extracts *specific claims* from papers and presents them as cards. Each card shows the claim, the paper it came from, and whether the evidence supports or contradicts the query.
- **Filter Rails**: After search, users can filter by study type, sample size, journal, year -- all without typing. These filters *are* the prompt refinement.
- **Copilot Synthesis**: The AI synthesizes across all found papers and presents a structured summary with inline citations. No prompt needed -- the search query IS the prompt.

**What Atlas Can Steal:**
- Evidence synthesis cards that show claims with support/contradiction indicators
- The Consensus Meter concept applied to knowledge graph connections (agreement/disagreement across documents)
- Filter-based prompt refinement instead of text-based

### 2.3 SciSpace (scispace.com) -- "Inline Document Intelligence"

**Key Zero-Prompt Patterns:**
- **PDF Copilot**: When reading a PDF, an AI sidebar automatically generates explanations for highlighted text. The user does not prompt -- they highlight, and the AI explains.
- **"Explain Like I'm 5"**: A single button click that re-explains complex content in simple language. No prompt engineering.
- **Related Papers Panel**: While reading any paper, a sidebar shows related papers automatically. No search query needed -- the context IS the query.
- **Table/Figure Extraction**: The AI automatically identifies tables and figures and offers to explain or extract data from them.
- **Citation Explorer**: Click any citation in a paper to see its abstract, key findings, and how it relates to the current paper.

**What Atlas Can Steal:**
- Highlight-to-explain (text selection triggers AI without any prompt)
- Auto-detection and extraction of tables/figures from PDFs
- Citation explorer within the PDF viewer

### 2.4 Semantic Scholar -- "Feed-Based Ambient Intelligence"

**Key Zero-Prompt Patterns:**
- **Research Feeds**: Like a social media feed but for papers. The system learns your interests and pushes relevant new papers to you. Zero prompting -- the system proactively delivers.
- **TLDR Auto-Summaries**: Every paper has an AI-generated TLDR. You never ask for a summary -- it is already there.
- **Citation Graph Navigation**: Click any paper to see its citation graph -- what it cites, what cites it, and the most influential connections. Each click IS the next query.
- **Research Alerts**: Set up alerts for topics and get notified when relevant papers are published. The initial setup is the only "prompt."
- **Highly Influential Citations**: The system automatically identifies which citations are most important, not just which exist.

**What Atlas Can Steal:**
- Auto-generated TLDRs for every ingested document
- A "Research Feed" view that shows recent discoveries, new connections, and suggested explorations
- Citation influence analysis (which connections in the knowledge graph are most significant)

### 2.5 Cursor (cursor.com) -- "Ghost Text & Ambient Completion"

**Key Zero-Prompt Patterns:**
- **Tab Completion (Ghost Text)**: The most powerful zero-prompt pattern in all of AI UX. Cursor predicts what you are about to type and shows it as gray text. You press Tab to accept. No prompt ever written.
- **Inline Diff**: When Cursor suggests a change, it shows a diff preview inline. You accept or reject. The AI proposes, the user disposes.
- **Cmd+K Contextual Editing**: Select code, press Cmd+K, and the AI understands what you want to do based on context. The prompt is minimal because the context does the work.
- **Codebase-Aware Context**: Cursor indexes your entire codebase and uses it as implicit context. You never have to explain your project -- it already knows.
- **@-Mentions for Context**: Instead of writing long prompts, you @-mention files, functions, or docs. The system assembles the context for you.

**What Atlas Can Steal:**
- Ghost text suggestions in the Editor pane (predict what the researcher will write next)
- @-mention system in the OmniBar/chat to reference specific documents, entities, or graph nodes
- Contextual action suggestions based on what the user is currently looking at
- "Accept/Reject" interaction model instead of "write a prompt"

### 2.6 Devin / Replit Agent -- "Plan-First Autonomous Execution"

**Key Zero-Prompt Patterns:**
- **Plan Generation**: User describes a goal in plain language. The system generates a multi-step plan. User reviews and approves the plan. System executes autonomously, step by step.
- **Progress Visibility**: During execution, the user sees exactly what the agent is doing, what it has completed, and what is next. They can intervene at any step.
- **Guardrailed Autonomy**: The system asks for approval at critical decision points but handles routine steps automatically.
- **Task Decomposition**: Complex goals are automatically broken into sub-tasks with clear success criteria.

**What Atlas Can Steal:**
- Research plan generation: "I want to understand X" -> system generates a research plan with steps (find papers, extract key findings, compare methodologies, synthesize, identify gaps)
- The user reviews the plan and clicks "Execute" -- the system runs through each step
- Progress visibility in the AgentWorkbench (already partially implemented!)

### 2.7 Manus AI -- "Full Autonomy with Browser-Visible Execution"

**Key Zero-Prompt Patterns:**
- **Natural Language Task Input**: User describes what they want in one sentence. Manus decomposes, plans, and executes entirely.
- **Virtual Computer View**: The user can watch the AI work in real-time (browsing, coding, writing). This builds trust and allows intervention.
- **Deliverable-Oriented**: The output is not a chat message -- it is a deliverable (a report, a spreadsheet, a website). The AI produces artifacts, not text.
- **Zero Configuration**: No API keys, no model selection, no prompt templates. You describe what you want, it does it.

**What Atlas Can Steal:**
- Deliverable-oriented outputs (produce a literature review document, not a chat message)
- The concept of "watching the AI work" (the AgentWorkbench already does this!)
- Artifact generation as the primary output format

---

## 3. Catalog of Zero-Prompt UX Patterns

Based on the competitive analysis, here are the named patterns:

### Pattern 1: "Context IS the Prompt"
**Definition**: The system infers user intent from what they are currently doing, not from what they type.
**Examples**: SciSpace highlight-to-explain, Cursor ghost text, Semantic Scholar related papers
**Implementation**: Track user focus (which document, which page, which graph node, which editor paragraph) and generate suggestions in real-time.

### Pattern 2: "Structured Rails Replace Free Text"
**Definition**: Instead of a blank text box, provide structured inputs with predefined options.
**Examples**: Elicit column extraction, Consensus filter rails, Manus task templates
**Implementation**: Workflow templates with dropdown/checkbox/card-based inputs instead of text prompts.

### Pattern 3: "Suggest, Don't Ask"
**Definition**: The system proactively presents options the user can accept, modify, or dismiss. The user's job is curation, not creation.
**Examples**: Cursor ghost text, Elicit follow-up suggestions, Semantic Scholar feeds
**Implementation**: After every AI action, generate 2-4 suggested next actions as clickable cards.

### Pattern 4: "Progressive Disclosure Workflows"
**Definition**: Guide the user through a multi-step process where each step reveals the next. The user never faces a blank page.
**Examples**: Elicit research question decomposition, Devin plan-first execution
**Implementation**: Multi-step research wizards (e.g., "Literature Review Workflow" with 5 guided stages).

### Pattern 5: "Ambient Intelligence Sidebar"
**Definition**: A persistent sidebar that continuously updates with relevant information based on user context, without any user action.
**Examples**: SciSpace related papers panel, Atlas's existing Context Engine
**Implementation**: The Context Engine sidebar becomes the primary zero-prompt surface.

### Pattern 6: "Click-to-Explore Graph Navigation"
**Definition**: Every piece of information is a hyperlink to deeper exploration. Clicking IS querying.
**Examples**: Semantic Scholar citation graph, Wikipedia link navigation
**Implementation**: Every entity, citation, concept, and connection in the UI is clickable and opens a contextual exploration panel.

### Pattern 7: "Accept/Reject Instead of Write"
**Definition**: The AI proposes actions/text/analysis, and the user accepts, modifies, or rejects. Binary decisions replace open-ended prompting.
**Examples**: Cursor inline diff, GitHub Copilot, Smart Compose
**Implementation**: In the Editor pane, suggest paragraph continuations, citation insertions, and section structure.

### Pattern 8: "Deliverable-First, Not Chat-First"
**Definition**: The primary output is a structured artifact (report, table, graph), not a chat message.
**Examples**: Manus deliverables, Elicit extraction tables, Notion AI
**Implementation**: Research outputs go to the Editor pane or Canvas as structured documents, not chat bubbles.

### Pattern 9: "The Research Feed"
**Definition**: A push-based discovery surface that shows the user what they should look at next.
**Examples**: Semantic Scholar feeds, Twitter/X algorithmic timeline
**Implementation**: A "Discovery Feed" showing new connections, gaps, contradictions, and suggested explorations.

### Pattern 10: "One-Click Workflows"
**Definition**: Common multi-step research tasks condensed into single-click actions.
**Examples**: SciSpace "Explain Like I'm 5", Consensus "Synthesize", Elicit "Find Papers"
**Implementation**: Action buttons like "Synthesize Selected", "Find Gaps", "Compare These Papers", "Generate Hypothesis".

---

## 4. Design Principles

### Principle 1: "The Knowledge Graph IS the Interface"
Atlas has a unique advantage over every competitor: it has a **knowledge graph**. This graph is not just a visualization -- it IS the zero-prompt engine. The graph tells the system:
- What the user knows (ingested documents)
- What connections exist (edges)
- What gaps exist (disconnected clusters, low-degree nodes)
- What contradictions exist (conflicting claims across documents)
- What to explore next (high-betweenness nodes, bridge entities)

**The graph should drive every suggestion, every workflow, and every proactive action.**

### Principle 2: "No Blank Pages, Ever"
Every view in Atlas should have a meaningful default state when there is no user action:
- **Document View (no doc selected)**: Show "Suggested papers to read" based on knowledge graph gaps
- **Editor (empty)**: Show "Start with a template" with options like Literature Review, Research Summary, Hypothesis Document
- **Graph (first load)**: Show auto-detected clusters with labels like "These 5 papers form a theme around X"
- **Chat (no messages)**: Show suggested questions based on the corpus: "Based on your 12 papers, you might want to ask..."
- **Canvas (empty)**: Show a template layout with pre-placed document nodes based on clusters

### Principle 3: "The AI is Invisible"
The best AI interface is one where you forget AI is involved. The system should feel like a very smart document workspace, not like a chatbot. This means:
- AI actions happen in response to user gestures (clicks, selections, navigation), not prompts
- AI outputs appear inline (margin notes, highlighted connections, auto-filled columns), not in chat bubbles
- The word "AI" should appear nowhere in the interface except possibly in settings

### Principle 4: "Every Action Suggests the Next Action"
After every user action, the system should suggest 2-4 relevant next steps:
- After uploading a paper: "View extracted entities" / "Find related papers" / "Compare with existing corpus"
- After reading a section: "Deep dive into [concept]" / "Find contradicting evidence" / "Add to synthesis"
- After exploring a graph node: "Trace this to source documents" / "Find bridging concepts" / "Generate research question about this"
- After generating a synthesis: "Export as LaTeX" / "Identify gaps" / "Extend with more sources"

### Principle 5: "Reduce Decisions, Not Options"
The system should have many capabilities but should surface only the most relevant ones at any moment. This is not about simplification -- it is about intelligent prioritization. The OmniBar's auto-routing already does this for chat modes. Extend this to ALL actions.

---

## 5. What Atlas Already Has (Zero-Prompt Features Already Implemented)

Atlas is further along than it might seem. Here is what already exists that maps to zero-prompt patterns:

| Existing Feature | Zero-Prompt Pattern | File |
|---|---|---|
| Context Engine sidebar | Ambient Intelligence Sidebar | `ContextEngine.tsx` |
| Related passages from other docs | Context IS the Prompt | `useContextEngine.ts` |
| Connected concepts display | Click-to-Explore | `ContextEngine.tsx` |
| OmniBar auto-routing | Intelligent Mode Selection | `OmniBar.tsx` |
| Agent Workbench telemetry | Progress Visibility | `AgentWorkbench.tsx` |
| Discovery OS tool execution trace | Autonomous Execution | `DiscoveryWorkbench.tsx` |
| Suggestion buttons in Context Engine | Suggest, Don't Ask | `ContextEngine.tsx` (lines 481-512) |
| Welcome Tour | Progressive Disclosure | `WelcomeTour.tsx` |
| Document structure analysis | Auto-Summary | `ContextEngine.tsx` (key findings) |
| Graph stats display | Ambient Intelligence | `ContextEngine.tsx` (graph stats) |

**Key Gap**: These features exist but they are *passive and siloed*. The Context Engine shows suggestions, but they do not trigger actions. The OmniBar auto-routes, but only after the user types. The Agent Workbench shows progress, but does not suggest next steps after completion.

---

## 6. Implementation Strategy for Atlas

### Phase 1: "Activate What You Have" (Low Effort, High Impact)

**Goal**: Make existing zero-prompt features *actionable* instead of passive.

#### 1a. Clickable Suggestion Cards (Context Engine)
**Current state**: The Context Engine shows suggestion buttons like "Ask: What are the key findings in [file]?" but they do nothing interactive.
**Change**: Make each suggestion button actually trigger the query. When clicked, it should:
1. Switch to chat view
2. Auto-fill the query
3. Auto-select the appropriate mode
4. Auto-submit

**Files to modify**: `ContextEngine.tsx` (add onClick handlers that call `setPendingQuestion` and switch view)

#### 1b. Post-Response Follow-Up Suggestions
**Current state**: After an AI response, the chat shows the message and stops.
**Change**: After every AI response, generate 2-3 follow-up question suggestions as clickable pills below the message. These should be generated by the AI as part of the response.

**Files to modify**: `ConversationView.tsx`, backend `routes.py` (add `suggested_followups` to response schema)

#### 1c. Empty State Intelligence
**Current state**: Empty states say things like "No document selected" or "Agent Workbench Idle."
**Change**: Replace every empty state with intelligent suggestions:
- Document view empty: Show top 3 suggested documents to review based on recency and graph connectivity
- Chat empty: Show 3-5 generated questions based on corpus content
- Graph empty: Show "Upload documents to build your knowledge graph" with a one-click upload
- Editor empty: Show template options

**Files to modify**: Each view component's empty state rendering

### Phase 2: "The Research Workflow Engine" (Medium Effort, Very High Impact)

**Goal**: Introduce structured, multi-step research workflows that replace chat-based interaction.

#### 2a. Workflow Templates
Create a new component: `WorkflowLauncher.tsx` accessible from the OmniBar, Canvas, and a new "Workflows" tab.

**Templates to implement:**
1. **Literature Review**: Define question -> Find papers -> Extract key findings -> Compare methods -> Synthesize -> Identify gaps -> Generate report
2. **Hypothesis Generation**: Select entities from graph -> Find connections -> Identify contradictions -> Propose hypotheses -> Rank by evidence
3. **Gap Analysis**: Analyze graph topology -> Find disconnected clusters -> Identify low-evidence nodes -> Suggest searches
4. **Paper Deep Dive**: Select paper -> Auto-extract structure -> Generate summary -> Find related work -> Add to graph -> Suggest follow-ups
5. **Comparative Analysis**: Select 2+ documents -> Extract comparable attributes -> Generate comparison table -> Identify agreements/disagreements

Each workflow is a deterministic multi-step pipeline that uses the existing backend services (retrieval, graph, swarm) but wraps them in a structured UX instead of chat.

#### 2b. Research Plan Auto-Generation
When a user types a complex question in the OmniBar, instead of immediately routing to a chat mode:
1. Detect that the question requires multiple steps
2. Generate a research plan (3-7 steps)
3. Show the plan as a checklist
4. Let the user approve/modify the plan
5. Execute each step sequentially, showing progress in the AgentWorkbench
6. Deliver the final result as an artifact in the Editor pane

#### 2c. OmniBar as Workflow Hub
Extend the OmniBar with a "Workflows" command group:
- `/review [topic]` - Start literature review workflow
- `/compare [doc A] vs [doc B]` - Start comparative analysis
- `/gaps` - Run gap analysis on current corpus
- `/hypothesis [entity]` - Generate hypotheses about an entity
- `/deep-dive [document]` - Run paper deep dive workflow

### Phase 3: "The Invisible AI" (Higher Effort, Transformative Impact)

**Goal**: Embed AI so deeply into the workspace that it becomes invisible.

#### 3a. Ghost Text in Editor
When the user is writing in the Editor pane, predict the next sentence/paragraph based on:
- The existing text
- The knowledge graph
- The ingested documents
- Recent chat history

Show the prediction as gray ghost text. Press Tab to accept.

**Implementation**: Use the existing LLM service with a `continue_writing` endpoint that takes the editor content + project context.

#### 3b. Highlight-to-Explore in PDF Viewer
When the user selects text in the PDF viewer:
1. Show a floating toolbar with: "Explain" / "Find Related" / "Add to Graph" / "Ask About This"
2. "Explain" generates an inline explanation without navigating to chat
3. "Find Related" shows related passages in a popover
4. "Add to Graph" creates a new entity from the selection
5. "Ask About This" opens the OmniBar pre-filled

**Implementation**: Add a `SelectionToolbar` component to the PDF viewer that appears on text selection.

#### 3c. Entity Hotspots in Documents
When viewing a document, automatically highlight entities that the system recognizes from the knowledge graph. Show inline badges or underlines. Hovering shows the entity card with connections.

**Implementation**: Use the existing entity extraction data from `nodes` table. Overlay highlights on the PDF text layer or text viewer.

#### 3d. Research Feed / Insights Dashboard
Add a new view or dashboard tab that shows:
- **New Connections Discovered**: "Entity A and Entity B appear in 3 shared contexts"
- **Knowledge Gaps**: "Your corpus covers X but has no information about Y (which is commonly associated)"
- **Contradictions**: "Paper 1 claims X, but Paper 3 claims Y"
- **Growth Metrics**: "12 new entities added this week, 34 new connections"
- **Suggested Next Steps**: "To strengthen your understanding of [topic], consider reading [suggested paper type]"

This is computed periodically in the background using the graph service.

#### 3e. Smart Document Ordering
When the user opens the Library Sidebar, instead of (or in addition to) chronological ordering, offer:
- **"Read Next"**: Based on graph gaps and what the user has already explored
- **"Most Connected"**: Documents with the most knowledge graph connections
- **"Least Explored"**: Documents the user has not deeply engaged with

---

## 7. Concrete Feature Blueprints

### Blueprint A: "Next Step Cards" (Phase 1 - implement first)

```
+------------------------------------------+
|  [icon] What would you like to do next?  |
+------------------------------------------+
|                                          |
|  [card] Explore connections to "CRISPR"  |
|         Found in 4 documents             |
|         -> Click to deep dive            |
|                                          |
|  [card] Compare Paper A vs Paper B       |
|         Both discuss "gene editing"      |
|         -> Click to compare              |
|                                          |
|  [card] Fill gap: "delivery mechanisms"  |
|         Mentioned 2x but no deep coverage|
|         -> Click to search for papers    |
|                                          |
+------------------------------------------+
```

This appears: (a) in the Context Engine sidebar, (b) after every AI response, (c) in empty states, (d) on the Canvas.

### Blueprint B: "Workflow Runner" (Phase 2)

```
+--------------------------------------------------+
|  Literature Review Workflow              [3/5]   |
+--------------------------------------------------+
|                                                  |
|  [x] 1. Define research question                 |
|      "How does CRISPR-Cas9 affect gene therapy?" |
|                                                  |
|  [x] 2. Find relevant papers (12 found)          |
|      [View papers table]                         |
|                                                  |
|  [x] 3. Extract key findings                     |
|      [View extraction table]                     |
|                                                  |
|  [ ] 4. Compare methodologies    [Running...]    |
|      Progress: analyzing paper 7/12              |
|                                                  |
|  [ ] 5. Generate synthesis report                |
|      Waiting for step 4...                       |
|                                                  |
+--------------------------------------------------+
|  [Pause]  [Skip Step]  [Add Step]  [Cancel]      |
+--------------------------------------------------+
```

This replaces the "Deep Chat" view for complex research tasks.

### Blueprint C: "Smart Editor" (Phase 3)

```
+--------------------------------------------------+
| Research Synthesis: CRISPR Gene Therapy           |
+--------------------------------------------------+
|                                                  |
| ## Introduction                                   |
|                                                  |
| Gene therapy has emerged as a promising           |
| approach to treating genetic disorders.           |
| The development of CRISPR-Cas9 has               |
| [dramatically accelerated progress in this       |  <- gray ghost text
|  field, particularly in the treatment of          |     (press Tab to accept)
|  monogenic diseases (Chen et al., 2023).]         |
|                                                  |
| ## Key Findings                                   |
|                                                  |
| [i] 3 papers support this claim  [!] 1 contradicts|  <- inline evidence badges
|                                                  |
+--------------------------------------------------+
| Suggestions: [Add citation] [Expand section]      |
|              [Find counter-evidence] [Rephrase]   |
+--------------------------------------------------+
```

---

## Summary: Priority Order for Implementation

| Priority | Feature | Pattern | Effort | Impact |
|---|---|---|---|---|
| P0 | Clickable suggestion cards | Suggest, Don't Ask | Low | High |
| P0 | Post-response follow-up suggestions | Suggest, Don't Ask | Low | High |
| P0 | Intelligent empty states | No Blank Pages | Low | Medium |
| P1 | OmniBar workflow commands | Structured Rails | Medium | High |
| P1 | Research plan auto-generation | Progressive Disclosure | Medium | Very High |
| P1 | Highlight-to-explore in PDF | Context IS the Prompt | Medium | High |
| P2 | Workflow templates engine | Progressive Disclosure | High | Very High |
| P2 | Ghost text in Editor | Accept/Reject | High | High |
| P2 | Entity hotspots in documents | Ambient Intelligence | Medium | High |
| P3 | Research Feed dashboard | Research Feed | High | Very High |
| P3 | Smart document ordering | Ambient Intelligence | Medium | Medium |
| P3 | Contradiction detection | Ambient Intelligence | High | High |

---

## The North Star

The ideal Atlas workspace feels like this:

> You open your project. The knowledge graph loads and immediately highlights a cluster you have not explored yet -- a bridge entity connects two groups of papers you uploaded separately. The sidebar shows "3 new connections found since your last session." You click one. It opens the relevant passage in Paper 7, with the connected passage from Paper 3 shown as a split view. A floating card says "These papers disagree on the mechanism of X -- generate hypothesis about why?" You click it. The system produces a structured hypothesis document in the Editor, complete with citations. At the bottom, three next-step cards appear: "Search for papers that test this hypothesis," "Find additional evidence for Claim A," "Map the timeline of this debate."

> At no point did you type a prompt. At no point did you face a blank page. The system guided you through your research by understanding your corpus, your context, and your trajectory.

That is the zero-prompt research workspace.
