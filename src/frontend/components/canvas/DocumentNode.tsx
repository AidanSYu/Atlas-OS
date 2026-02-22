'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps, type Node } from '@xyflow/react';
import { FileText, Trash2 } from 'lucide-react';

interface DocumentNodeData extends Record<string, unknown> {
  filename: string;
  pageCount?: number;
  status?: string;
  onOpen?: () => void;
  onDelete?: () => void;
}

type CustomDocNode = Node<DocumentNodeData>;

export const DocumentNode = memo(({ data }: NodeProps<CustomDocNode>) => {
  return (
    <div className="group w-64 rounded-md border border-border/60 bg-card/95 backdrop-blur-sm p-4 shadow-sm hover:border-primary/40 hover:shadow-md transition-all">
      <Handle type="target" position={Position.Top} className="!bg-accent" />

      <div className="flex items-start gap-3">
        <div className="rounded border border-primary/10 bg-primary/5 p-2">
          <FileText className="h-4 w-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-foreground line-clamp-2 mb-1">
            {data.filename}
          </div>
          {data.pageCount && (
            <div className="text-xs text-muted-foreground">
              {data.pageCount} pages
            </div>
          )}
        </div>

        <button
          onClick={data.onDelete}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-destructive/10 rounded"
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </button>
      </div>

      {data.status && (
        <div className="mt-2 text-xs text-muted-foreground">
          Status: {data.status}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-accent" />
    </div>
  );
});

DocumentNode.displayName = 'DocumentNode';
