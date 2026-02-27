import { useState, useEffect, useCallback } from 'react';

interface ContextPayload {
    project_id: string;
    selected_text?: string;
    current_doc_id?: string;
    current_page?: number;
}

export interface ContextSuggestionsResponse {
    related_passages: any[];
    connected_concepts: any[];
    suggestions: any[];
}

/**
 * Hook to proactively send user reading context to the Atlas backend.
 * Features:
 *  - Debounces by 500ms to prevent spamming the backend when scrolling/highlighting.
 *  - Silently handles 429/503 errors (which happen when the local LLM is busy generating text).
 */
export function useContextEngine(projectId: string | null) {
    const [suggestions, setSuggestions] = useState<ContextSuggestionsResponse | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [lastPayload, setLastPayload] = useState<ContextPayload | null>(null);

    // Debounced API call to the backend Context Engine
    const fetchContext = useCallback(async (payload: ContextPayload) => {
        if (!payload.project_id) return;

        setIsProcessing(true);
        try {
            const response = await fetch('http://127.0.0.1:8000/api/context', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: payload.project_id,
                    selected_text: payload.selected_text || null,
                    current_doc_id: payload.current_doc_id || null,
                    current_page: payload.current_page || null,
                }),
            });

            // If backend is busy (e.g. LLM constraint), ignore gracefully.
            if (!response.ok) {
                if (response.status === 429 || response.status === 503 || response.status === 404) {
                    console.debug('Context Engine busy/unavailable, skipping background embeddings.');
                    return;
                }
                throw new Error(`Context Engine error: ${response.status}`);
            }

            const data = await response.json();
            if (data.status === 'success') {
                setSuggestions(data.suggestions || null);
            }
        } catch (error) {
            console.debug('Context Engine fetch failed silently:', error);
        } finally {
            setIsProcessing(false);
        }
    }, []);

    // Effect to manage debouncing the context
    useEffect(() => {
        if (!lastPayload || !lastPayload.project_id) return;

        // Only hit the backend if there's actual context to parse
        if (!lastPayload.selected_text && !lastPayload.current_doc_id) {
            setSuggestions(null);
            return;
        }

        const timer = setTimeout(() => {
            fetchContext(lastPayload);
        }, 500);

        return () => clearTimeout(timer);
    }, [lastPayload, fetchContext]);

    const updateContext = useCallback((
        selectedText?: string,
        docId?: string,
        page?: number
    ) => {
        if (!projectId) return;

        setLastPayload((prev) => {
            if (prev && prev.current_doc_id !== docId) {
                setSuggestions(null); // Clear previous doc's suggestions immediately
            }
            return {
                project_id: projectId,
                selected_text: selectedText,
                current_doc_id: docId,
                current_page: page,
            };
        });
    }, [projectId]);

    return {
        suggestions,
        isProcessing,
        updateContext,
    };
}
