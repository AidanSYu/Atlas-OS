/**
 * Truncation & Blob Protocol
 *
 * Prevents DOM crashes by ensuring the ExecutionPipeline never renders
 * massive JSON payloads into React. Arrays, strings, and deeply nested
 * objects are truncated to safe preview strings. The full payload is
 * downloadable as a Blob on demand.
 *
 * Source: docs/DiscoveryOS_GoldenPath_Plan.md v3.1 — "Truncation & Blob Protocol"
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const PIPELINE_RENDER_LIMITS = {
  maxArrayElements: 500,
  maxStringBytes: 65_536,
  maxNestingDepth: 3,
} as const;

const ARRAY_PREVIEW_COUNT = 5;
const STRING_PREVIEW_CHARS = 200;

const BASE64_RE = /^[A-Za-z0-9+/]{100,}={0,2}$/;

// ---------------------------------------------------------------------------
// Public Interface
// ---------------------------------------------------------------------------

export interface TruncatedPayload {
  preview: string;
  fullSizeBytes: number;
  elementCount?: number;
  blob: Blob | null;
  downloadFilename: string;
  isTruncated: boolean;
}

// ---------------------------------------------------------------------------
// Core
// ---------------------------------------------------------------------------

/**
 * Accepts any JSON-serializable value and returns a DOM-safe preview plus
 * a lazy-downloadable Blob for the full payload.
 */
export function truncatePayload(
  value: unknown,
  downloadFilename: string,
): TruncatedPayload {
  const fullJson = JSON.stringify(value);
  const fullSizeBytes = new Blob([fullJson]).size;

  if (typeof value === 'string' && BASE64_RE.test(value)) {
    return {
      preview: `[Binary blob — ${formatBytes(fullSizeBytes)} — Download]`,
      fullSizeBytes,
      blob: null,
      downloadFilename,
      isTruncated: true,
    };
  }

  if (Array.isArray(value) && value.length > PIPELINE_RENDER_LIMITS.maxArrayElements) {
    const slice = value.slice(0, ARRAY_PREVIEW_COUNT);
    const remaining = value.length - ARRAY_PREVIEW_COUNT;
    const previewInner = JSON.stringify(slice, null, 2);
    const preview =
      previewInner.slice(0, -1) +               // remove trailing ']'
      `,\n  "... ${remaining.toLocaleString()} more items — Download full array (${formatBytes(fullSizeBytes)})"\n]`;

    return {
      preview,
      fullSizeBytes,
      elementCount: value.length,
      blob: null,
      downloadFilename,
      isTruncated: true,
    };
  }

  if (typeof value === 'string' && fullSizeBytes > PIPELINE_RENDER_LIMITS.maxStringBytes) {
    const safeSlice = safeTruncateString(value, STRING_PREVIEW_CHARS);
    const preview = JSON.stringify(
      safeSlice + `... [Truncated — Download full payload (${formatBytes(fullSizeBytes)})]`,
    );
    return {
      preview,
      fullSizeBytes,
      blob: null,
      downloadFilename,
      isTruncated: true,
    };
  }

  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const depth = measureDepth(value);
    if (depth > PIPELINE_RENDER_LIMITS.maxNestingDepth) {
      const preview = truncateObjectDepth(
        value as Record<string, unknown>,
        PIPELINE_RENDER_LIMITS.maxNestingDepth,
      );
      return {
        preview,
        fullSizeBytes,
        blob: null,
        downloadFilename,
        isTruncated: true,
      };
    }
  }

  if (fullSizeBytes > PIPELINE_RENDER_LIMITS.maxStringBytes) {
    const preview = truncateObjectDepth(
      value as Record<string, unknown>,
      PIPELINE_RENDER_LIMITS.maxNestingDepth,
    );
    return {
      preview,
      fullSizeBytes,
      blob: null,
      downloadFilename,
      isTruncated: true,
    };
  }

  return {
    preview: JSON.stringify(value, null, 2),
    fullSizeBytes,
    blob: null,
    downloadFilename,
    isTruncated: false,
  };
}

/**
 * Materializes the Blob (if not yet created) and triggers a browser download.
 * Revokes the object URL after the download starts.
 */
export function downloadBlob(payload: TruncatedPayload, originalValue?: unknown): void {
  let blob = payload.blob;
  if (!blob) {
    const content = originalValue !== undefined
      ? JSON.stringify(originalValue, null, 2)
      : payload.preview;
    blob = new Blob([content], { type: 'application/json' });
    payload.blob = blob;
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = payload.downloadFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Truncates a string at a safe UTF-8 boundary (never splits a surrogate pair).
 */
function safeTruncateString(str: string, maxChars: number): string {
  if (str.length <= maxChars) return str;

  let end = maxChars;
  const code = str.charCodeAt(end - 1);
  if (code >= 0xd800 && code <= 0xdbff) {
    end--;
  }
  return str.slice(0, end);
}

/**
 * Measures the maximum nesting depth of a JSON-like value.
 */
function measureDepth(value: unknown, current: number = 0): number {
  if (typeof value !== 'object' || value === null) return current;
  if (current > PIPELINE_RENDER_LIMITS.maxNestingDepth + 2) return current;

  let max = current;
  const entries = Array.isArray(value) ? value : Object.values(value);
  for (const child of entries) {
    const childDepth = measureDepth(child, current + 1);
    if (childDepth > max) max = childDepth;
  }
  return max;
}

/**
 * Produces a valid-JSON preview of an object, collapsing anything deeper
 * than `maxDepth` into a placeholder string.
 */
function truncateObjectDepth(
  obj: Record<string, unknown>,
  maxDepth: number,
  currentDepth: number = 0,
): string {
  if (currentDepth >= maxDepth) {
    if (Array.isArray(obj)) {
      return `"[Array of ${obj.length} items — expand to view]"`;
    }
    const keys = Object.keys(obj);
    return `"[Object with ${keys.length} keys — expand to view]"`;
  }

  const entries: string[] = [];
  const indent = '  '.repeat(currentDepth + 1);
  const closingIndent = '  '.repeat(currentDepth);

  for (const [key, val] of Object.entries(obj)) {
    if (typeof val === 'object' && val !== null) {
      const nested = truncateObjectDepth(
        val as Record<string, unknown>,
        maxDepth,
        currentDepth + 1,
      );
      entries.push(`${indent}${JSON.stringify(key)}: ${nested}`);
    } else {
      entries.push(`${indent}${JSON.stringify(key)}: ${JSON.stringify(val)}`);
    }
  }

  return `{\n${entries.join(',\n')}\n${closingIndent}}`;
}
