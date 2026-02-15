// Detect if running in Tauri desktop app
declare global {
  interface Window {
    __TAURI__?: {
      tauri?: any;
      window?: any;
    };
  }
}

/**
 * Get the API base URL dynamically.
 */
function getApiBaseUrl(): string {
  if (typeof window !== 'undefined' && window.__TAURI__) {
    return 'http://127.0.0.1:8000';
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

const API_BASE_URL = getApiBaseUrl();

const API_TIMEOUT = 30000;
const CHAT_TIMEOUT = 180000;
const SWARM_TIMEOUT = 300000; // 5 minutes for swarm (multi-step)

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    const errorMessage = errorData.detail || response.statusText;
    throw new Error(`API Error (${response.status}): ${errorMessage}`);
  }
  return response.json();
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = API_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

// ============================================================
// TYPES
// ============================================================

export interface ProjectInfo {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface FileInfo {
  filename: string;
  doc_id: string;
  status: string;
  size_bytes?: number;
  uploaded_at?: string;
  processed_at?: string;
  total_chunks?: number;
  processed_chunks?: number;
  progress?: number;
  project_id?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface Citation {
  source: string;
  page: number;
  doc_id?: string;
  relevance?: number;
  text?: string;
}

export interface ChatResponse {
  answer: string;
  reasoning: string;
  citations: Citation[];
  relationships?: Array<{ source: string; type: string; target: string; context?: string }>;
  context_sources?: any;
}

export interface EntityInfo {
  id: string;
  name: string;
  type: string;
  description?: string;
  document_id: string;
}

export interface RelationshipInfo {
  id: string;
  source_id: string;
  source_name: string;
  target_id: string;
  target_name: string;
  type: string;
  context?: string;
}

export interface ModelInfo {
  name: string;
  path: string;
}

export interface ModelsResponse {
  models_dir: string;
  llm: ModelInfo[];
  embeddings: ModelInfo[];
  ner: ModelInfo[];
  other: ModelInfo[];
  message?: string;
}

export interface ModelStatusResponse {
  active_model: string | null;
  model_type: string;
  device: string;
  gpu_layers: number;
  fallback: boolean;
}

export interface SwarmEvidence {
  source: string;
  page: number;
  excerpt: string;
  relevance: number;
}

export interface SwarmResponse {
  brain_used: 'navigator' | 'cortex';
  hypothesis: string;
  evidence: SwarmEvidence[];
  reasoning_trace: string[];
  status: string;
}

// ============================================================
// API CLIENT
// ============================================================

export const api = {
  // ---- Projects ----

  async createProject(name: string, description?: string): Promise<ProjectInfo> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    });
    return handleResponse(response);
  },

  async listProjects(): Promise<ProjectInfo[]> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/projects`);
    return handleResponse(response);
  },

  async deleteProject(projectId: string): Promise<any> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}`, {
      method: 'DELETE',
    });
    return handleResponse(response);
  },

  // ---- File Management ----

  async uploadFile(file: File, projectId?: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const url = projectId
      ? `${API_BASE_URL}/ingest?project_id=${encodeURIComponent(projectId)}`
      : `${API_BASE_URL}/ingest`;
    const response = await fetchWithTimeout(url, { method: 'POST', body: formData });
    return handleResponse(response);
  },

  async listFiles(projectId?: string): Promise<FileInfo[]> {
    const params = new URLSearchParams();
    if (projectId) params.append('project_id', projectId);
    const url = params.toString()
      ? `${API_BASE_URL}/files?${params.toString()}`
      : `${API_BASE_URL}/files`;
    const response = await fetchWithTimeout(url);
    return handleResponse(response);
  },

  async deleteFile(docId: string): Promise<any> {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/files/${encodeURIComponent(docId)}`,
      { method: 'DELETE' }
    );
    return handleResponse(response);
  },

  getFileUrl(docId: string): string {
    return `${API_BASE_URL}/files/${encodeURIComponent(docId)}`;
  },

  // ---- Chat (Librarian RAG) ----

  async chat(query: string, projectId?: string): Promise<ChatResponse> {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/chat`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, project_id: projectId }),
      },
      CHAT_TIMEOUT
    );
    return handleResponse(response);
  },

  // ---- Swarm (Two-Brain Agentic RAG) ----

  async runSwarm(query: string, projectId: string): Promise<SwarmResponse> {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/api/swarm/run`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, project_id: projectId }),
      },
      SWARM_TIMEOUT
    );
    return handleResponse(response);
  },

  // ---- Entities & Graph ----

  async listEntities(params?: {
    entity_type?: string;
    document_id?: string;
    project_id?: string;
    limit?: number;
  }): Promise<EntityInfo[]> {
    const q = new URLSearchParams();
    if (params?.entity_type) q.append('entity_type', params.entity_type);
    if (params?.document_id) q.append('document_id', params.document_id);
    if (params?.project_id) q.append('project_id', params.project_id);
    q.append('limit', String(params?.limit ?? 50));
    const response = await fetchWithTimeout(`${API_BASE_URL}/entities?${q.toString()}`);
    return handleResponse(response);
  },

  async getEntityRelationships(
    entityId: string,
    direction: 'outgoing' | 'incoming' | 'both' = 'both'
  ): Promise<RelationshipInfo[]> {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/entities/${encodeURIComponent(entityId)}/relationships?direction=${direction}`
    );
    return handleResponse(response);
  },

  async getEntityTypes(projectId?: string): Promise<Array<{ type: string; count: number }>> {
    const params = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    const response = await fetchWithTimeout(`${API_BASE_URL}/graph/types${params}`);
    const data = await handleResponse<{ entity_types: Array<{ type: string; count: number }> }>(response);
    return data.entity_types;
  },

  async getFullGraph(
    documentId?: string,
    projectId?: string
  ): Promise<{ nodes: EntityInfo[]; edges: RelationshipInfo[] }> {
    const params = new URLSearchParams();
    if (documentId) params.append('document_id', documentId);
    if (projectId) params.append('project_id', projectId);
    const url = params.toString()
      ? `${API_BASE_URL}/graph/full?${params.toString()}`
      : `${API_BASE_URL}/graph/full`;
    const response = await fetchWithTimeout(url);
    return handleResponse(response);
  },

  async listModels(): Promise<ModelsResponse> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/models`);
    return handleResponse(response);
  },

  async getModelStatus(): Promise<ModelStatusResponse> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/models/status`);
    return handleResponse(response);
  },

  async loadModel(modelName: string): Promise<ModelStatusResponse> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/models/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_name: modelName }),
    });
    return handleResponse(response);
  },
};
