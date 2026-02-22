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
