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
  type Connection,
  BackgroundVariant,
  Panel,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { DocumentNode } from './canvas/DocumentNode';
import { InsightNode } from './canvas/InsightNode';
import { useCanvasStore } from '@/stores/canvasStore';
import { Trash2 } from 'lucide-react';

const nodeTypes: any = {
  document: DocumentNode,
  insight: InsightNode,
};

interface ResearchCanvasProps {
  projectId: string;
}

export function ResearchCanvasPropsInner({ projectId }: ResearchCanvasProps) {
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

  const handleClearCanvas = useCallback(() => {
    if (confirm('Clear all nodes and connections from the canvas?')) {
      canvasStore.clearCanvas();
      setNodes([]);
      setEdges([]);
    }
  }, [canvasStore, setNodes, setEdges]);

  const { screenToFlowPosition } = useReactFlow();

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const data = event.dataTransfer.getData('application/atlas-document');
      if (!data) return;

      const doc = JSON.parse(data);
      const position = screenToFlowPosition({
        x: event.clientX - 128, // Offset by roughly half node width
        y: event.clientY - 50,  // Offset by roughly half node height
      });

      const newNode = {
        id: `doc-${doc.id}`,
        type: 'document',
        position,
        data: {
          filename: doc.filename,
          pageCount: doc.pageCount,
          status: doc.status,
          onOpen: () => console.log('Open doc:', doc.id),
          onDelete: () => {
            canvasStore.removeNode(`doc-${doc.id}`);
            setNodes((nds) => nds.filter((n) => n.id !== `doc-${doc.id}`));
          },
        },
      };

      canvasStore.addNode(newNode);
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes, canvasStore, screenToFlowPosition]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <div className="h-full w-full bg-background relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
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
          <button
            onClick={handleClearCanvas}
            className="flex items-center gap-2 rounded border border-border/50 bg-card/90 backdrop-blur-md px-3 py-2 text-xs text-foreground hover:bg-surface transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear Canvas
          </button>
        </Panel>

        <Panel position="top-right" className="text-xs text-muted-foreground bg-card/90 backdrop-blur-md rounded border border-border/50 px-3 py-2">
          {nodes.length} nodes · {edges.length} connections
        </Panel>
      </ReactFlow>
    </div>
  );
}

export function ResearchCanvas({ projectId }: ResearchCanvasProps) {
  return (
    <ReactFlowProvider>
      <ResearchCanvasPropsInner projectId={projectId} />
    </ReactFlowProvider>
  );
}
