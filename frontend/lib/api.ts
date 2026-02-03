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
 * In Tauri, always use the local sidecar server.
 * In development, use the environment variable or localhost.
 */
function getApiBaseUrl(): string {
  // In Tauri desktop app, always use local sidecar
  if (typeof window !== 'undefined' && window.__TAURI__) {
    return 'http://127.0.0.1:8000';
  }
  // Development or web deployment
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

const API_BASE_URL = getApiBaseUrl();

// Timeouts
const API_TIMEOUT = 30000; // 30 seconds
const CHAT_TIMEOUT = 180000; // 180 seconds for LLM responses (bundled LLM may be slower)

// Helper function to handle API errors consistently
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    const errorMessage = errorData.detail || response.statusText;
    throw new Error(`API Error (${response.status}): ${errorMessage}`);
  }
  return response.json();
}

// Helper to add timeout to fetch calls
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = API_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
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
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface Citation {
  source: string; // filename
  page: number;
  doc_id?: string; // for opening PDF in viewer
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

export const api = {
  // File Management
  async uploadFile(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetchWithTimeout(`${API_BASE_URL}/ingest`, {
      method: 'POST',
      body: formData,
    });
    
    return handleResponse(response);
  },

  async listFiles(): Promise<FileInfo[]> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/files`);
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

  // Chat
  async chat(query: string): Promise<ChatResponse> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    }, CHAT_TIMEOUT);
    
    return handleResponse(response);
  },

  // Entities & Relationships
  async listEntities(params?: { entity_type?: string; document_id?: string; limit?: number }): Promise<EntityInfo[]> {
    const q = new URLSearchParams();
    if (params?.entity_type) q.append('entity_type', params.entity_type);
    if (params?.document_id) q.append('document_id', params.document_id);
    q.append('limit', String(params?.limit ?? 50));
    const response = await fetchWithTimeout(`${API_BASE_URL}/entities?${q.toString()}`);
    return handleResponse(response);
  },

  async getEntityRelationships(entityId: string, direction: 'outgoing' | 'incoming' | 'both' = 'both'): Promise<RelationshipInfo[]> {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/entities/${encodeURIComponent(entityId)}/relationships?direction=${direction}`
    );
    return handleResponse(response);
  },

  async getEntityTypes(): Promise<Array<{ type: string; count: number }>> {
    const response = await fetchWithTimeout(`${API_BASE_URL}/graph/types`);
    const data = await handleResponse<{ entity_types: Array<{ type: string; count: number }> }>(response);
    return data.entity_types;
  },

  async getFullGraph(documentId?: string): Promise<{ nodes: EntityInfo[]; edges: RelationshipInfo[] }> {
    const url = documentId 
      ? `${API_BASE_URL}/graph/full?document_id=${encodeURIComponent(documentId)}`
      : `${API_BASE_URL}/graph/full`;
    const response = await fetchWithTimeout(url);
    return handleResponse(response);
  },
};
