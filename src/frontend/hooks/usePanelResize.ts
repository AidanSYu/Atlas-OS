import { useCallback, useEffect, useRef, useState } from 'react';

interface UsePanelResizeOptions {
    /** Starting size in pixels */
    initialSize: number;
    /** Minimum size in pixels */
    minSize?: number;
    /** Maximum size in pixels */
    maxSize?: number;
    /** Direction the handle resizes: 'horizontal' (left/right) or 'vertical' (up/down) */
    direction: 'horizontal' | 'vertical';
    /**
     * When true, the resize delta is negated.
     * Use this when the drag handle sits **above** or **to the right of** the panel it controls,
     * so that dragging toward the panel shrinks it rather than grows it.
     */
    invert?: boolean;
    /** localStorage key to persist the size across sessions */
    storageKey?: string;
}

interface UsePanelResizeReturn {
    size: number;
    /** Attach to the drag handle element */
    handleMouseDown: (e: React.MouseEvent) => void;
    /** true while the user is actively dragging */
    isDragging: boolean;
}

function getPersistedSize(storageKey: string | undefined, fallback: number, min: number, max: number): number {
    if (!storageKey || typeof window === 'undefined') return fallback;
    try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
            const parsed = Number(raw);
            if (!Number.isNaN(parsed) && parsed >= min && parsed <= max) return parsed;
        }
    } catch { /* ignore */ }
    return fallback;
}

/**
 * VS Code-style panel resize hook.
 * Supports horizontal (left↔right) and vertical (up↔down) resize.
 * Persists size to localStorage when a storageKey is provided.
 */
export function usePanelResize({
    initialSize,
    minSize = 120,
    maxSize = Infinity,
    direction,
    invert = false,
    storageKey,
}: UsePanelResizeOptions): UsePanelResizeReturn {
    const [size, setSize] = useState<number>(() =>
        getPersistedSize(storageKey, initialSize, minSize, maxSize)
    );
    const [isDragging, setIsDragging] = useState(false);

    // Use refs so event listeners always see current values without re-subscribing
    const sizeRef = useRef(size);
    const dragStartRef = useRef<{ pos: number; size: number } | null>(null);
    const draggingRef = useRef(false);

    // Keep sizeRef in sync
    useEffect(() => { sizeRef.current = size; }, [size]);

    const handleMouseDown = useCallback(
        (e: React.MouseEvent) => {
            e.preventDefault();
            dragStartRef.current = {
                pos: direction === 'horizontal' ? e.clientX : e.clientY,
                size: sizeRef.current,
            };
            draggingRef.current = true;
            setIsDragging(true);
        },
        [direction],
    );

    useEffect(() => {
        const onMouseMove = (e: MouseEvent) => {
            if (!draggingRef.current || !dragStartRef.current) return;
            const { pos, size: startSize } = dragStartRef.current;
            const rawDelta = (direction === 'horizontal' ? e.clientX : e.clientY) - pos;
            const delta = invert ? -rawDelta : rawDelta;
            const next = Math.min(maxSize, Math.max(minSize, startSize + delta));
            sizeRef.current = next;
            setSize(next);
        };

        const onMouseUp = () => {
            if (!draggingRef.current) return;
            draggingRef.current = false;
            dragStartRef.current = null;
            setIsDragging(false);
            // Persist final value
            if (storageKey) {
                try { localStorage.setItem(storageKey, String(sizeRef.current)); } catch { /* ignore */ }
            }
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);

        return () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };
        // Only attach/detach once — refs handle dynamic values
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Apply global cursor + select-none while dragging
    useEffect(() => {
        if (isDragging) {
            document.body.style.userSelect = 'none';
            document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
        }
    }, [isDragging, direction]);

    return { size, handleMouseDown, isDragging };
}
