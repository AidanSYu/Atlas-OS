'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Maximize2 } from 'lucide-react';
import { GraphLink, GraphNode, useGraphStore } from '@/stores/graphStore';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

interface KnowledgeGraphProps {
  height: number;
  width: number;
  projectId?: string;
  documentId?: string;
}

type RenderNode = GraphNode & {
  isCluster?: boolean;
  memberCount?: number;
  degree?: number;
  tetherX?: number;
  tetherY?: number;
};

type RenderLink = GraphLink & {
  weight?: number;
};

const TYPE_COLORS: Record<string, string> = {
  Person: '#7FA7FF',
  Organization: '#6CC9B5',
  Location: '#C59DFF',
  Date: '#D8BC7F',
  Event: '#E69A9A',
  Concept: '#87B5D6',
  Document: '#A6B0BE',
  Entity: '#8E9AA8',
  Cluster: '#9AA7B5',
};

function colorForType(type: string) {
  return TYPE_COLORS[type] || TYPE_COLORS.Entity;
}

function toNodeId(value: string | GraphNode): string {
  return typeof value === 'string' ? value : value.id;
}

function normalizeTypeLabel(type: string) {
  return type || 'Entity';
}

export default function KnowledgeGraph({ height, width, projectId, documentId }: KnowledgeGraphProps) {
  const fgRef = useRef<any>(null);
  const [isStabilizing, setIsStabilizing] = useState(true);
  const [warmupElapsed, setWarmupElapsed] = useState(false);

  const {
    nodes,
    links,
    loading,
    error,
    focusedNodeId,
    loadGraph,
    setSelectedNode,
    setFocusedNode,
    clearFocus,
  } = useGraphStore();

  useEffect(() => {
    setIsStabilizing(true);
    setWarmupElapsed(false);

    const timer = window.setTimeout(() => setWarmupElapsed(true), 650);
    return () => window.clearTimeout(timer);
  }, [documentId]);

  useEffect(() => {
    if (!projectId) return;
    loadGraph(projectId, documentId);
  }, [loadGraph, projectId, documentId]);

  const graphData = useMemo<{ nodes: RenderNode[]; links: RenderLink[]; isClustered: boolean }>(() => {
    const safeNodes: RenderNode[] = nodes.map((node) => ({
      ...node,
      color: colorForType(normalizeTypeLabel(node.type)),
    }));

    const safeLinks: RenderLink[] = links.map((link) => ({ ...link }));

    if (safeNodes.length === 0) {
      return { nodes: safeNodes, links: safeLinks, isClustered: false };
    }

    if (safeNodes.length > 50) {
      const byType = new Map<string, RenderNode[]>();
      safeNodes.forEach((node) => {
        const key = normalizeTypeLabel(node.type);
        if (!byType.has(key)) byType.set(key, []);
        byType.get(key)!.push(node);
      });

      const clusteredNodes: RenderNode[] = Array.from(byType.entries()).map(([type, members], idx) => ({
        id: `cluster:${type}`,
        name: type,
        type: 'Cluster',
        color: colorForType(type),
        val: Math.max(10, Math.min(26, 8 + members.length * 0.42)),
        memberCount: members.length,
        isCluster: true,
        tetherX: Math.cos((idx / Math.max(byType.size, 1)) * Math.PI * 2) * 240,
        tetherY: Math.sin((idx / Math.max(byType.size, 1)) * Math.PI * 2) * 160,
      }));

      const clusterLinksMap = new Map<string, number>();
      const nodeType = new Map(safeNodes.map((node) => [node.id, normalizeTypeLabel(node.type)]));

      safeLinks.forEach((link) => {
        const sourceType = nodeType.get(toNodeId(link.source));
        const targetType = nodeType.get(toNodeId(link.target));
        if (!sourceType || !targetType) return;

        const key = `${sourceType}=>${targetType}`;
        clusterLinksMap.set(key, (clusterLinksMap.get(key) || 0) + 1);
      });

      const clusteredLinks: RenderLink[] = Array.from(clusterLinksMap.entries()).map(([key, count]) => {
        const [sourceType, targetType] = key.split('=>');
        return {
          source: `cluster:${sourceType}`,
          target: `cluster:${targetType}`,
          label: count > 1 ? `${count} relations` : 'relation',
          weight: count,
        };
      });

      return { nodes: clusteredNodes, links: clusteredLinks, isClustered: true };
    }

    const degreeMap = new Map<string, number>();
    safeNodes.forEach((node) => degreeMap.set(node.id, 0));

    safeLinks.forEach((link) => {
      const source = toNodeId(link.source);
      const target = toNodeId(link.target);
      degreeMap.set(source, (degreeMap.get(source) || 0) + 1);
      degreeMap.set(target, (degreeMap.get(target) || 0) + 1);
    });

    let mainNodeId = safeNodes[0].id;
    let maxDegree = -1;
    degreeMap.forEach((degree, id) => {
      if (degree > maxDegree) {
        maxDegree = degree;
        mainNodeId = id;
      }
    });

    const sorted = safeNodes.filter((node) => node.id !== mainNodeId);
    const withTethers: RenderNode[] = safeNodes.map((node) => {
      if (node.id === mainNodeId) {
        return {
          ...node,
          val: Math.max(node.val + 4, 14),
          degree: degreeMap.get(node.id) || 0,
          tetherX: 0,
          tetherY: 0,
        };
      }

      const i = sorted.findIndex((item) => item.id === node.id);
      const angle = (i / Math.max(sorted.length, 1)) * Math.PI * 2;
      const radius = 170 + ((i % 4) * 26);

      return {
        ...node,
        degree: degreeMap.get(node.id) || 0,
        tetherX: Math.cos(angle) * radius,
        tetherY: Math.sin(angle) * radius,
      };
    });

    return { nodes: withTethers, links: safeLinks, isClustered: false };
  }, [nodes, links]);

  useEffect(() => {
    if (!fgRef.current || graphData.nodes.length === 0) return;

    const chargeForce = fgRef.current.d3Force('charge');
    if (chargeForce && typeof chargeForce.strength === 'function') {
      chargeForce.strength(-280);
    }

    const linkForce = fgRef.current.d3Force('link');
    if (linkForce) {
      if (typeof linkForce.distance === 'function') {
        linkForce.distance((link: RenderLink) => (link.weight && link.weight > 1 ? 90 : 120));
      }
      if (typeof linkForce.strength === 'function') {
        linkForce.strength((link: RenderLink) => (link.weight && link.weight > 1 ? 0.42 : 0.22));
      }
    }

    const centerStrength = graphData.isClustered ? 0.2 : 0.12;
    const forceX = fgRef.current.d3Force('x');
    if (forceX && typeof forceX.strength === 'function') {
      forceX.strength(centerStrength);
      if (typeof forceX.x === 'function') {
        forceX.x((node: RenderNode) => node.tetherX || 0);
      }
    }

    const forceY = fgRef.current.d3Force('y');
    if (forceY && typeof forceY.strength === 'function') {
      forceY.strength(centerStrength);
      if (typeof forceY.y === 'function') {
        forceY.y((node: RenderNode) => node.tetherY || 0);
      }
    }

    fgRef.current.d3ReheatSimulation();
  }, [graphData]);

  const handleNodeClick = useCallback(
    (rawNode: any) => {
      const node = rawNode as RenderNode;
      if (node.isCluster) return;

      const nodeId = node.id;
      if (focusedNodeId === nodeId) {
        clearFocus();
        setSelectedNode(null);
        return;
      }

      setFocusedNode(nodeId);
      setSelectedNode(nodeId);

      if (fgRef.current && node.x !== undefined && node.y !== undefined) {
        fgRef.current.centerAt(node.x, node.y, 320);
        fgRef.current.zoom(2.2, 320);
      }
    },
    [focusedNodeId, clearFocus, setSelectedNode, setFocusedNode]
  );

  const nodeCanvasObject = useCallback((rawNode: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const node = rawNode as RenderNode;
    const focused = !!node.isFocused;
    const neighbor = !!node.isNeighbor;
    const dimmed = !!node.isDimmed;

    const radius = Math.max(5, (node.val || 8) / 1.75);
    const opacity = dimmed ? 0.15 : focused ? 1 : neighbor ? 0.88 : 0.72;

    ctx.globalAlpha = opacity;
    ctx.beginPath();
    ctx.arc(node.x || 0, node.y || 0, radius, 0, Math.PI * 2);
    ctx.fillStyle = node.color || colorForType(node.type);
    ctx.fill();

    ctx.lineWidth = (focused ? 2 : 1) / globalScale;
    ctx.strokeStyle = focused ? '#FFFFFF' : '#2F2F2F';
    ctx.stroke();

    ctx.globalAlpha = 1;

    if (globalScale < 0.7 && !focused) return;

    const title = node.isCluster ? `${node.name} (${node.memberCount || 0})` : node.name;
    const fontSize = Math.max(8, 12 / Math.max(globalScale, 0.8));
    ctx.font = `500 ${fontSize}px Inter, sans-serif`;

    const textWidth = ctx.measureText(title).width;
    const textX = (node.x || 0) - textWidth / 2;
    const textY = (node.y || 0) + radius + fontSize + 2;

    ctx.fillStyle = '#1F1F1F';
    ctx.fillRect(textX - 4, textY - fontSize, textWidth + 8, fontSize + 4);
    ctx.fillStyle = '#E8E8E8';
    ctx.fillText(title, textX, textY);
  }, []);

  const linkCanvasObject = useCallback((rawLink: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const link = rawLink as RenderLink;
    if (link.isDimmed) return;

    const source = link.source as RenderNode;
    const target = link.target as RenderNode;
    if (!source || !target || source.x == null || source.y == null || target.x == null || target.y == null) {
      return;
    }

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;

    const targetRadius = Math.max(5, ((target.val || 8) / 1.75));
    const arrowBaseX = target.x - ux * (targetRadius + 4);
    const arrowBaseY = target.y - uy * (targetRadius + 4);

    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.lineTo(arrowBaseX, arrowBaseY);
    ctx.strokeStyle = '#5A5A5A';
    ctx.lineWidth = Math.max(0.7, (link.weight && link.weight > 1 ? 1.5 : 1.1) / Math.max(globalScale, 0.7));
    ctx.stroke();

    const arrowSize = Math.max(4, 7 / Math.max(globalScale, 0.8));
    ctx.beginPath();
    ctx.moveTo(arrowBaseX, arrowBaseY);
    ctx.lineTo(
      arrowBaseX - ux * arrowSize - uy * arrowSize * 0.45,
      arrowBaseY - uy * arrowSize + ux * arrowSize * 0.45
    );
    ctx.lineTo(
      arrowBaseX - ux * arrowSize + uy * arrowSize * 0.45,
      arrowBaseY - uy * arrowSize - ux * arrowSize * 0.45
    );
    ctx.closePath();
    ctx.fillStyle = '#8A8A8A';
    ctx.fill();

    if (globalScale < 1.15) return;

    const label = link.label || '';
    if (!label) return;

    const midX = source.x + dx * 0.5;
    const midY = source.y + dy * 0.5;
    const fontSize = Math.max(7, 9 / Math.max(globalScale, 0.95));
    ctx.font = `500 ${fontSize}px Inter, sans-serif`;

    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = '#1E1E1E';
    ctx.fillRect(midX - textWidth / 2 - 3, midY - fontSize, textWidth + 6, fontSize + 3);
    ctx.fillStyle = '#B7C2D0';
    ctx.fillText(label, midX - textWidth / 2, midY);
  }, []);

  if (!projectId) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background text-sm text-muted-foreground">
        No project selected.
      </div>
    );
  }

  if (!documentId) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background text-muted-foreground">
        <p className="text-sm">Select a document to render its Atlas Map.</p>
        <p className="mt-1 text-xs">Graph scope is limited to the active document.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background text-muted-foreground">
        <div className="flex flex-col items-center">
          <div className="mb-2 h-4 w-4 animate-pulse rounded-full bg-accent" />
          <span className="text-xs">Mapping document entities...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background p-4 text-center text-destructive">
        <span className="mb-2">Unable to render graph map.</span>
        <span className="text-xs opacity-80">{error}</span>
      </div>
    );
  }

  if (graphData.nodes.length === 0) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background text-muted-foreground">
        <p className="text-sm">No graph entities found in this document.</p>
        <p className="mt-1 text-xs">Try another file or re-process this document.</p>
      </div>
    );
  }

  const hideCanvas = isStabilizing || !warmupElapsed;

  return (
    <div className="relative h-full w-full bg-background">
      <div className={hideCanvas ? 'pointer-events-none opacity-0 transition-opacity' : 'opacity-100 transition-opacity'}>
        <ForceGraph2D
          ref={fgRef}
          width={width}
          height={height}
          graphData={{ nodes: graphData.nodes, links: graphData.links }}
          cooldownTicks={150}
          d3AlphaDecay={0.024}
          d3VelocityDecay={0.34}
          onEngineStop={() => setIsStabilizing(false)}
          nodeLabel={() => ''}
          nodeCanvasObject={nodeCanvasObject}
          linkCanvasObject={linkCanvasObject}
          onNodeClick={handleNodeClick}
          enableNodeDrag={false}
          backgroundColor="#1A1A1A"
        />
      </div>

      {hideCanvas && (
        <div className="absolute inset-0 flex items-center justify-center bg-background">
          <div className="flex flex-col items-center text-muted-foreground">
            <div className="mb-2 h-4 w-4 animate-pulse rounded-full bg-accent" />
            <span className="text-xs">Stabilizing Atlas Map...</span>
          </div>
        </div>
      )}

      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <button
          onClick={() => fgRef.current?.zoomToFit(420, 28)}
          className="rounded-md border border-border bg-card p-2 text-muted-foreground transition-colors hover:bg-accent/15 hover:text-foreground"
          title="Fit graph"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
