'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Maximize2, ZoomIn, ZoomOut, RotateCcw, Eye, EyeOff, Network } from 'lucide-react';
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

// Vibrant, accessible entity colors
const TYPE_COLORS: Record<string, string> = {
  Person: '#6B9EFF',      // bright blue
  Organization: '#4DD9AC', // mint green
  Location: '#B580FF',     // lavender
  Date: '#FFB84D',         // amber
  Event: '#FF7B7B',        // coral
  Concept: '#5CC8E6',      // cyan
  Document: '#7B8CFF',     // indigo
  Method: '#A78BFA',       // violet
  Chemical: '#2DD4BF',     // teal
  Result: '#A3E635',       // lime
  Entity: '#94A3B8',       // slate
  Cluster: '#818CF8',      // indigo cluster
};

function colorForType(type: string) {
  return TYPE_COLORS[type] || TYPE_COLORS.Entity;
}

function toNodeId(value: string | GraphNode): string {
  return typeof value === 'string' ? value : value.id;
}

export default function KnowledgeGraph({ height, width, projectId, documentId }: KnowledgeGraphProps) {
  const fgRef = useRef<any>(null);
  const [isStabilizing, setIsStabilizing] = useState(true);
  const [warmupElapsed, setWarmupElapsed] = useState(false);
  const [showLabels, setShowLabels] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<RenderNode | null>(null);

  const nodes = useGraphStore((s) => s.nodes);
  const links = useGraphStore((s) => s.links);
  const loading = useGraphStore((s) => s.loading);
  const error = useGraphStore((s) => s.error);
  const focusedNodeId = useGraphStore((s) => s.focusedNodeId);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const setSelectedNode = useGraphStore((s) => s.setSelectedNode);
  const setFocusedNode = useGraphStore((s) => s.setFocusedNode);
  const clearFocus = useGraphStore((s) => s.clearFocus);

  useEffect(() => {
    setIsStabilizing(true);
    setWarmupElapsed(false);
    const timer = window.setTimeout(() => setWarmupElapsed(true), 650);
    return () => window.clearTimeout(timer);
  }, [documentId, projectId]);

  useEffect(() => {
    if (!projectId) return;
    loadGraph(projectId, documentId);
  }, [loadGraph, projectId, documentId]);

  const graphData = useMemo<{ nodes: RenderNode[]; links: RenderLink[]; isClustered: boolean }>(() => {
    const safeNodes: RenderNode[] = nodes.map((node) => ({
      ...node,
      color: colorForType(node.type || 'Entity'),
    }));
    const safeLinks: RenderLink[] = links.map((link) => ({ ...link }));

    if (safeNodes.length === 0) {
      return { nodes: safeNodes, links: safeLinks, isClustered: false };
    }

    // Cluster when too many nodes
    if (safeNodes.length > 60) {
      const byType = new Map<string, RenderNode[]>();
      safeNodes.forEach((node) => {
        const key = node.type || 'Entity';
        if (!byType.has(key)) byType.set(key, []);
        byType.get(key)!.push(node);
      });

      const clusteredNodes: RenderNode[] = Array.from(byType.entries()).map(([type, members], idx) => ({
        id: `cluster:${type}`,
        name: type,
        type: 'Cluster',
        color: colorForType(type),
        val: Math.max(12, Math.min(28, 10 + members.length * 0.5)),
        memberCount: members.length,
        isCluster: true,
        tetherX: Math.cos((idx / Math.max(byType.size, 1)) * Math.PI * 2) * 250,
        tetherY: Math.sin((idx / Math.max(byType.size, 1)) * Math.PI * 2) * 170,
      }));

      const clusterLinksMap = new Map<string, number>();
      const nodeType = new Map(safeNodes.map((n) => [n.id, n.type || 'Entity']));

      safeLinks.forEach((link) => {
        const sourceType = nodeType.get(toNodeId(link.source));
        const targetType = nodeType.get(toNodeId(link.target));
        if (!sourceType || !targetType || sourceType === targetType) return;
        const key = [sourceType, targetType].sort().join('|');
        clusterLinksMap.set(key, (clusterLinksMap.get(key) || 0) + 1);
      });

      const clusteredLinks: RenderLink[] = Array.from(clusterLinksMap.entries()).map(([key, count]) => {
        const [a, b] = key.split('|');
        return {
          source: `cluster:${a}`,
          target: `cluster:${b}`,
          label: `${count}`,
          weight: count,
        };
      });

      return { nodes: clusteredNodes, links: clusteredLinks, isClustered: true };
    }

    // Degree calculation + tether layout for non-clustered
    const degreeMap = new Map<string, number>();
    safeNodes.forEach((n) => degreeMap.set(n.id, 0));
    safeLinks.forEach((link) => {
      const s = toNodeId(link.source);
      const t = toNodeId(link.target);
      degreeMap.set(s, (degreeMap.get(s) || 0) + 1);
      degreeMap.set(t, (degreeMap.get(t) || 0) + 1);
    });

    let mainNodeId = safeNodes[0]?.id;
    let maxDeg = -1;
    degreeMap.forEach((deg, id) => {
      if (deg > maxDeg) { maxDeg = deg; mainNodeId = id; }
    });

    const sorted = safeNodes.filter((n) => n.id !== mainNodeId);
    const withTethers: RenderNode[] = safeNodes.map((node) => {
      if (node.id === mainNodeId) {
        return { ...node, val: Math.max((node.val || 8) + 4, 14), degree: degreeMap.get(node.id) || 0, tetherX: 0, tetherY: 0 };
      }
      const i = sorted.findIndex((s) => s.id === node.id);
      const angle = (i / Math.max(sorted.length, 1)) * Math.PI * 2;
      const radius = 170 + (i % 4) * 28;
      return { ...node, degree: degreeMap.get(node.id) || 0, tetherX: Math.cos(angle) * radius, tetherY: Math.sin(angle) * radius };
    });

    return { nodes: withTethers, links: safeLinks, isClustered: false };
  }, [nodes, links]);

  // Type legend
  const typeLegend = useMemo(() => {
    const types = new Map<string, number>();
    graphData.nodes.forEach((n) => {
      if (n.isCluster) {
        types.set(n.name, n.memberCount || 0);
      } else {
        const t = n.type || 'Entity';
        types.set(t, (types.get(t) || 0) + 1);
      }
    });
    return Array.from(types.entries()).sort((a, b) => b[1] - a[1]);
  }, [graphData.nodes]);

  useEffect(() => {
    if (!fgRef.current || graphData.nodes.length === 0) return;

    const charge = fgRef.current.d3Force('charge');
    if (charge?.strength) {
      charge.strength(-800);
      charge.distanceMax(400);
    }

    const collision = fgRef.current.d3Force('collide');
    if (!collision && fgRef.current.d3Force) {
      // d3-force-3d doesn't expose d3 directly, so we rely on node val for spacing indirectly via charge
    }

    const linkForce = fgRef.current.d3Force('link');
    if (linkForce) {
      linkForce.distance?.((l: RenderLink) => (l.weight && l.weight > 1 ? 120 : 180));
      linkForce.strength?.((l: RenderLink) => (l.weight && l.weight > 1 ? 0.3 : 0.15));
    }

    const str = graphData.isClustered ? 0.2 : 0.1;
    const fx = fgRef.current.d3Force('x');
    if (fx) { fx.strength?.(str); fx.x?.((n: RenderNode) => n.tetherX || 0); }
    const fy = fgRef.current.d3Force('y');
    if (fy) { fy.strength?.(str); fy.y?.((n: RenderNode) => n.tetherY || 0); }

    fgRef.current.d3ReheatSimulation();
  }, [graphData]);

  const handleNodeClick = useCallback((rawNode: any) => {
    const node = rawNode as RenderNode;
    if (node.isCluster) return;

    if (focusedNodeId === node.id) {
      clearFocus();
      setSelectedNode(null);
    } else {
      setFocusedNode(node.id);
      setSelectedNode(node.id);
      if (fgRef.current && node.x != null && node.y != null) {
        fgRef.current.centerAt(node.x, node.y, 320);
        fgRef.current.zoom(2.2, 320);
      }
    }
  }, [focusedNodeId, clearFocus, setSelectedNode, setFocusedNode]);

  const nodeCanvasObject = useCallback((rawNode: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const node = rawNode as RenderNode;
    const focused = !!node.isFocused;
    const neighbor = !!node.isNeighbor;
    const dimmed = !!node.isDimmed;
    const hovered = hoveredNode?.id === node.id;

    const baseRadius = Math.max(5, (node.val || 8) / 1.6);
    const radius = (focused || hovered) ? baseRadius * 1.15 : baseRadius;
    const opacity = dimmed ? 0.12 : focused ? 1 : neighbor ? 0.9 : 0.75;

    const color = node.color || colorForType(node.type);

    // Outer glow for focused/hovered
    if (focused || hovered) {
      ctx.globalAlpha = 0.25;
      ctx.beginPath();
      ctx.arc(node.x || 0, node.y || 0, radius + 6, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }

    // Main circle
    ctx.globalAlpha = opacity;
    ctx.beginPath();
    ctx.arc(node.x || 0, node.y || 0, radius, 0, Math.PI * 2);

    // Gradient fill
    const gradient = ctx.createRadialGradient(
      (node.x || 0) - radius * 0.3, (node.y || 0) - radius * 0.3, 0,
      node.x || 0, node.y || 0, radius
    );
    gradient.addColorStop(0, color);
    gradient.addColorStop(1, adjustBrightness(color, -30));
    ctx.fillStyle = gradient;
    ctx.fill();

    // Ring
    if (focused) {
      ctx.lineWidth = 2.5 / globalScale;
      ctx.strokeStyle = '#FFFFFF';
      ctx.stroke();
    } else if (neighbor) {
      ctx.lineWidth = 1.5 / globalScale;
      ctx.strokeStyle = color;
      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Labels
    if (!showLabels && !focused && !hovered) return;
    if (globalScale < 0.55 && !focused && !hovered) return;

    const title = node.isCluster ? `${node.name} (${node.memberCount || 0})` : node.name;
    const fontSize = Math.max(8, (focused ? 13 : 11) / Math.max(globalScale, 0.8));
    ctx.font = `${focused ? '600' : '500'} ${fontSize}px Inter, sans-serif`;

    const textWidth = ctx.measureText(title).width;
    const textX = (node.x || 0) - textWidth / 2;
    const textY = (node.y || 0) + radius + fontSize + 3;

    // Label background
    const bgAlpha = dimmed ? 0.05 : 0.85;
    ctx.globalAlpha = bgAlpha;
    ctx.fillStyle = '#0D1117';
    const padding = 4;
    ctx.beginPath();
    roundRect(ctx, textX - padding, textY - fontSize - 1, textWidth + padding * 2, fontSize + 4, 3);
    ctx.fill();

    // Label text
    ctx.globalAlpha = dimmed ? 0.2 : (focused ? 1 : 0.85);
    ctx.fillStyle = focused ? '#FFFFFF' : '#D4D8E0';
    ctx.fillText(title, textX, textY);

    ctx.globalAlpha = 1;
  }, [showLabels, hoveredNode]);

  const linkCanvasObject = useCallback((rawLink: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const link = rawLink as RenderLink;
    if (link.isDimmed) return;

    const source = link.source as RenderNode;
    const target = link.target as RenderNode;
    if (!source || !target || source.x == null || target.x == null) return;

    const dx = target.x - source.x;
    const dy = (target.y || 0) - (source.y || 0);
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;

    const targetR = Math.max(5, ((target.val || 8) / 1.6));
    const endX = target.x - ux * (targetR + 5);
    const endY = (target.y || 0) - uy * (targetR + 5);

    const isHighlighted = !link.isDimmed && (
      (source as RenderNode).isFocused || (target as RenderNode).isFocused ||
      (source as RenderNode).isNeighbor || (target as RenderNode).isNeighbor
    );

    // Line
    ctx.beginPath();
    ctx.moveTo(source.x, source.y || 0);
    ctx.lineTo(endX, endY);
    ctx.strokeStyle = isHighlighted ? 'hsl(174, 62%, 47%)' : 'rgba(100, 116, 139, 0.35)';
    ctx.lineWidth = Math.max(0.5, (isHighlighted ? 2 : 1) / Math.max(globalScale, 0.6));
    ctx.stroke();

    // Arrow
    const arrowSize = Math.max(3.5, (isHighlighted ? 8 : 6) / Math.max(globalScale, 0.7));
    ctx.beginPath();
    ctx.moveTo(endX, endY);
    ctx.lineTo(endX - ux * arrowSize - uy * arrowSize * 0.4, endY - uy * arrowSize + ux * arrowSize * 0.4);
    ctx.lineTo(endX - ux * arrowSize + uy * arrowSize * 0.4, endY - uy * arrowSize - ux * arrowSize * 0.4);
    ctx.closePath();
    ctx.fillStyle = isHighlighted ? 'hsl(174, 62%, 47%)' : 'rgba(100, 116, 139, 0.5)';
    ctx.fill();

    // Label
    if (globalScale < 1.2 || !link.label) return;
    const midX = source.x + dx * 0.5;
    const midY = (source.y || 0) + dy * 0.5;
    const fontSize = Math.max(7, 9 / Math.max(globalScale, 0.95));
    ctx.font = `400 ${fontSize}px Inter, sans-serif`;
    const tw = ctx.measureText(link.label).width;

    ctx.globalAlpha = 0.85;
    ctx.fillStyle = '#0D1117';
    ctx.beginPath();
    roundRect(ctx, midX - tw / 2 - 3, midY - fontSize, tw + 6, fontSize + 3, 2);
    ctx.fill();

    ctx.globalAlpha = 0.7;
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(link.label, midX - tw / 2, midY);
    ctx.globalAlpha = 1;
  }, []);

  // Empty/loading/error states
  if (!projectId) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        No project selected.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div className="h-8 w-8 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
          </div>
          <span className="text-xs text-muted-foreground">Building knowledge graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-4 text-center">
        <span className="mb-2 text-destructive text-sm">Unable to render graph</span>
        <span className="text-xs text-muted-foreground">{error}</span>
      </div>
    );
  }

  if (graphData.nodes.length === 0) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center text-center">
        <Network className="h-10 w-10 text-muted-foreground/20 mb-3" />
        <p className="text-sm text-muted-foreground">
          {documentId ? 'No entities found in this document.' : 'Select a document to view its knowledge graph.'}
        </p>
        <p className="mt-1 text-xs text-muted-foreground/60">
          {documentId ? 'Try re-processing or uploading a different document.' : 'Or upload a document to get started.'}
        </p>
      </div>
    );
  }

  const hideCanvas = isStabilizing || !warmupElapsed;

  return (
    <div className="relative h-full w-full" style={{ background: '#0A0E17' }}>
      {/* Graph canvas */}
      <div className={hideCanvas ? 'pointer-events-none opacity-0 transition-opacity duration-300' : 'opacity-100 transition-opacity duration-500'}>
        <ForceGraph2D
          ref={fgRef}
          width={width}
          height={height}
          graphData={{ nodes: graphData.nodes, links: graphData.links }}
          cooldownTicks={160}
          d3AlphaDecay={0.022}
          d3VelocityDecay={0.33}
          onEngineStop={() => setIsStabilizing(false)}
          nodeLabel={() => ''}
          nodeCanvasObject={nodeCanvasObject}
          linkCanvasObject={linkCanvasObject}
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => setHoveredNode(node as RenderNode | null)}
          enableNodeDrag={true}
          backgroundColor="transparent"
        />
      </div>

      {/* Stabilizing overlay */}
      {hideCanvas && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: '#0A0E17' }}>
          <div className="flex flex-col items-center gap-3">
            <div className="relative">
              <div className="h-8 w-8 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
            </div>
            <span className="text-xs text-muted-foreground">Stabilizing graph layout...</span>
          </div>
        </div>
      )}

      {/* Legend */}
      {typeLegend.length > 0 && !hideCanvas && (
        <div className="absolute bottom-4 left-4 rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm px-3 py-2 max-w-[180px]">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Entity Types
          </p>
          <div className="space-y-1">
            {typeLegend.slice(0, 8).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2 text-[11px]">
                <div
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: colorForType(type) }}
                />
                <span className="text-foreground/80 truncate">{type}</span>
                <span className="ml-auto text-muted-foreground text-[10px]">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      {!hideCanvas && (
        <div className="absolute bottom-4 right-4 flex flex-col gap-1.5">
          <button
            onClick={() => fgRef.current?.zoomToFit(420, 30)}
            className="rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm p-2 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
            title="Fit to view"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
          <button
            onClick={() => fgRef.current?.zoom(fgRef.current?.zoom() * 1.3, 200)}
            className="rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm p-2 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={() => fgRef.current?.zoom(fgRef.current?.zoom() * 0.7, 200)}
            className="rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm p-2 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowLabels(!showLabels)}
            className={`rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm p-2 transition-colors ${showLabels ? 'text-accent' : 'text-muted-foreground'} hover:bg-surface`}
            title={showLabels ? 'Hide labels' : 'Show labels'}
          >
            {showLabels ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
          </button>
          {focusedNodeId && (
            <button
              onClick={() => clearFocus()}
              className="rounded-lg border border-border/50 bg-card/90 backdrop-blur-sm p-2 text-amber-400 transition-colors hover:bg-surface"
              title="Clear focus"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Hovered node tooltip */}
      {hoveredNode && !hoveredNode.isCluster && hoveredNode.x != null && (
        <div
          className="pointer-events-none absolute rounded-lg border border-border/50 bg-card/95 backdrop-blur-sm px-3 py-2 shadow-lg"
          style={{
            left: Math.min(width - 200, Math.max(10, (hoveredNode.x || 0) + width / 2 + 15)),
            top: Math.min(height - 60, Math.max(10, (hoveredNode.y || 0) + height / 2 - 20)),
          }}
        >
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: hoveredNode.color }} />
            <span className="text-xs font-medium text-foreground">{hoveredNode.name}</span>
            <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {hoveredNode.type}
            </span>
          </div>
          {hoveredNode.properties?.description && (
            <p className="mt-1 max-w-[200px] text-[10px] text-muted-foreground line-clamp-2">
              {hoveredNode.properties.description}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// Helper: rounded rectangle
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
}

// Helper: adjust hex color brightness
function adjustBrightness(hex: string, amount: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.max(0, Math.min(255, ((num >> 16) & 0xFF) + amount));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0xFF) + amount));
  const b = Math.max(0, Math.min(255, (num & 0xFF) + amount));
  return `#${(r << 16 | g << 8 | b).toString(16).padStart(6, '0')}`;
}

