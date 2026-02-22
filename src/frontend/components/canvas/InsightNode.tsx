'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps, type Node } from '@xyflow/react';
import { Lightbulb } from 'lucide-react';

interface InsightNodeData extends Record<string, unknown> {
  content: string;
  brain?: string;
  timestamp?: Date;
}

type CustomInsightNode = Node<InsightNodeData>;

export const InsightNode = memo(({ data }: NodeProps<CustomInsightNode>) => {
  return (
    <div className="w-80 rounded-md border border-accent/30 bg-card/95 backdrop-blur-sm p-4 shadow-sm">
      <Handle type="target" position={Position.Top} className="!bg-accent" />

      <div className="flex items-center gap-2 mb-2">
        <Lightbulb className="h-3.5 w-3.5 text-accent" />
        <span className="text-xs font-medium text-accent uppercase tracking-wide">
          {data.brain || 'Insight'}
        </span>
      </div>

      <div className="text-sm text-foreground leading-relaxed">
        {data.content}
      </div>

      {data.timestamp && (
        <div className="mt-2 text-xs text-muted-foreground">
          {new Date(data.timestamp).toLocaleString()}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-accent" />
    </div>
  );
});

InsightNode.displayName = 'InsightNode';
