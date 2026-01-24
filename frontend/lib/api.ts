const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface FileInfo {
  filename: string;
  doc_id: string;
  status: string;
  size_bytes?: number;
  uploaded_at?: string;
  processed_at?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface Citation {
  source: string; // filename
  page: number;
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
    
    const response = await fetch(`${API_BASE_URL}/ingest`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    
    return response.json();
  },

  async listFiles(): Promise<FileInfo[]> {
    const response = await fetch(`${API_BASE_URL}/files`);
    
    if (!response.ok) {
      throw new Error(`Failed to list files: ${response.statusText}`);
    }
    
    return response.json();
  },

  async deleteFile(docId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/files/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
    });
    
    if (!response.ok) {
      throw new Error(`Delete failed: ${response.statusText}`);
    }
    
    return response.json();
  },

  getFileUrl(docId: string): string {
    return `${API_BASE_URL}/files/${encodeURIComponent(docId)}`;
  },

  // Chat
  async chat(query: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });
    
    if (!response.ok) {
      throw new Error(`Chat failed: ${response.statusText}`);
    }
    
    return response.json();
  },

  // Entities & Relationships
  async listEntities(params?: { entity_type?: string; document_id?: string; limit?: number }): Promise<EntityInfo[]> {
    const q = new URLSearchParams();
    if (params?.entity_type) q.append('entity_type', params.entity_type);
    if (params?.document_id) q.append('document_id', params.document_id);
    q.append('limit', String(params?.limit ?? 50));
    const response = await fetch(`${API_BASE_URL}/entities?${q.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to list entities: ${response.statusText}`);
    }
    return response.json();
  },

  async getEntityRelationships(entityId: string, direction: 'outgoing' | 'incoming' | 'both' = 'both'): Promise<RelationshipInfo[]> {
    const response = await fetch(`${API_BASE_URL}/entities/${encodeURIComponent(entityId)}/relationships?direction=${direction}`);
    if (!response.ok) {
      throw new Error(`Failed to get relationships: ${response.statusText}`);
    }
    return response.json();
  },

  async getEntityTypes(): Promise<Array<{ type: string; count: number }>> {
    const response = await fetch(`${API_BASE_URL}/graph/types`);
    if (!response.ok) {
      throw new Error(`Failed to get entity types: ${response.statusText}`);
    }
    const data = await response.json();
    return data.entity_types;
  },
};
