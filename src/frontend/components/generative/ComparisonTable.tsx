'use client';

import { ArrowUpDown, Check, X, Minus } from 'lucide-react';
import { useState } from 'react';

interface ComparisonRow {
  feature: string;
  values: (string | boolean | null)[];
}

interface ComparisonTableProps {
  headers: string[]; // Column headers (e.g., document names)
  rows: ComparisonRow[];
  title?: string;
}

export function ComparisonTable({ headers, rows, title }: ComparisonTableProps) {
  const [sortBy, setSortBy] = useState<number | null>(null);

  const renderCell = (value: string | boolean | null) => {
    if (typeof value === 'boolean') {
      return value ? (
        <Check className="h-4 w-4 text-success" />
      ) : (
        <X className="h-4 w-4 text-destructive" />
      );
    }
    if (value === null) {
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    }
    return <span className="text-sm">{value}</span>;
  };

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {title && (
        <div className="border-b border-border bg-muted/30 px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-border bg-muted/30">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Feature
              </th>
              {headers.map((header, i) => (
                <th
                  key={i}
                  className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground transition-colors"
                  onClick={() => setSortBy(i)}
                >
                  <div className="flex items-center gap-1.5">
                    {header}
                    <ArrowUpDown className="h-3 w-3 opacity-50" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-surface/50 transition-colors">
                <td className="px-4 py-3 text-sm font-medium text-foreground whitespace-nowrap">
                  {row.feature}
                </td>
                {row.values.map((value, j) => (
                  <td key={j} className="px-4 py-3">
                    {renderCell(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
