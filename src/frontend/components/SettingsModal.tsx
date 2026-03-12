'use client';

import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, CheckCircle2, AlertCircle, Loader2, Key } from 'lucide-react';
import { api, ConfigKeysUpdate } from '@/lib/api';
import { toastError, toastSuccess } from '@/stores/toastStore';

interface SettingsModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onKeysUpdated?: () => void;
}

export default function SettingsModal({ open, onOpenChange, onKeysUpdated }: SettingsModalProps) {
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState({
        openai: false,
        anthropic: false,
        deepseek: false,
        minimax: false,
    });
    const [verified, setVerified] = useState({
        openai: false,
        anthropic: false,
        deepseek: false,
        minimax: false,
    });

    const [keys, setKeys] = useState({
        openai: '',
        anthropic: '',
        deepseek: '',
        minimax: '',
    });

    // Load status and verify keys when modal opens
    useEffect(() => {
        if (!open) return;
        const loadStatus = async () => {
            setLoading(true);
            try {
                const [res, verifyRes] = await Promise.all([
                    api.getApiKeysStatus(),
                    api.verifyApiKeys(),
                ]);
                setStatus({
                    openai: res.has_openai,
                    anthropic: res.has_anthropic,
                    deepseek: res.has_deepseek,
                    minimax: res.has_minimax,
                });
                setVerified({
                    openai: verifyRes.openai,
                    anthropic: verifyRes.anthropic,
                    deepseek: verifyRes.deepseek,
                    minimax: verifyRes.minimax,
                });
            } catch (err) {
                console.error('Failed to load API key status', err);
            } finally {
                setLoading(false);
            }
        };
        loadStatus();
    }, [open]);

    const handleSave = async () => {
        if (!keys.openai && !keys.anthropic && !keys.deepseek && !keys.minimax) {
            onOpenChange(false);
            return;
        }

        setSaving(true);
        try {
            const update: ConfigKeysUpdate = {};
            if (keys.openai) update.OPENAI_API_KEY = keys.openai;
            if (keys.anthropic) update.ANTHROPIC_API_KEY = keys.anthropic;
            if (keys.deepseek) update.DEEPSEEK_API_KEY = keys.deepseek;
            if (keys.minimax) update.MINIMAX_API_KEY = keys.minimax;

            await api.updateApiKeys(update);
            toastSuccess('API keys saved successfully!');

            // Verify keys and update status so "Verified" only shows when key works
            setKeys({ openai: '', anthropic: '', deepseek: '', minimax: '' });
            const [res, verifyRes] = await Promise.all([
                api.getApiKeysStatus(),
                api.verifyApiKeys(),
            ]);
            setStatus({
                openai: res.has_openai,
                anthropic: res.has_anthropic,
                deepseek: res.has_deepseek,
                minimax: res.has_minimax,
            });
            setVerified({
                openai: verifyRes.openai,
                anthropic: verifyRes.anthropic,
                deepseek: verifyRes.deepseek,
                minimax: verifyRes.minimax,
            });
            const anyFailed = (res.has_openai && !verifyRes.openai) || (res.has_anthropic && !verifyRes.anthropic)
                || (res.has_deepseek && !verifyRes.deepseek) || (res.has_minimax && !verifyRes.minimax);
            if (anyFailed) {
                toastError(
                    'Keys saved. Verification failed for some keys (network, timeout, or provider limits can cause this). You can still try using the model.'
                );
            }

            onOpenChange(false);
            onKeysUpdated?.();
        } catch (err) {
            toastError('Failed to save API keys');
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm px-4">
            {/* Click outside to close */}
            <div className="absolute inset-0" onClick={() => onOpenChange(false)} />

            <div className="relative w-full max-w-md rounded-xl border border-border bg-card shadow-2xl animate-in zoom-in-95 duration-200">
                <div className="p-6">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <SettingsIcon className="h-5 w-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold tracking-tight text-foreground">Settings</h2>
                            <p className="text-sm text-muted-foreground">Configure your AI providers</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <ApiKeyInput
                            label="OpenAI API Key"
                            provider="openai"
                            value={keys.openai}
                            isConfigured={status.openai}
                            isVerified={verified.openai}
                            onChange={(v) => setKeys(prev => ({ ...prev, openai: v }))}
                            placeholder="sk-..."
                        />
                        <ApiKeyInput
                            label="Anthropic API Key"
                            provider="anthropic"
                            value={keys.anthropic}
                            isConfigured={status.anthropic}
                            isVerified={verified.anthropic}
                            onChange={(v) => setKeys(prev => ({ ...prev, anthropic: v }))}
                            placeholder="sk-ant-..."
                        />
                        <ApiKeyInput
                            label="DeepSeek API Key"
                            provider="deepseek"
                            value={keys.deepseek}
                            isConfigured={status.deepseek}
                            isVerified={verified.deepseek}
                            onChange={(v) => setKeys(prev => ({ ...prev, deepseek: v }))}
                            placeholder="sk-..."
                        />
                        <ApiKeyInput
                            label="MiniMax API Key"
                            provider="minimax"
                            value={keys.minimax}
                            isConfigured={status.minimax}
                            isVerified={verified.minimax}
                            onChange={(v) => setKeys(prev => ({ ...prev, minimax: v }))}
                            placeholder="..."
                        />
                    </div>

                    <div className="mt-8 flex justify-end gap-3">
                        <button
                            onClick={() => onOpenChange(false)}
                            className="rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-surface hover:text-foreground transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-50 transition-colors"
                        >
                            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save Changes'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ApiKeyInput({
    label,
    value,
    isConfigured,
    isVerified,
    onChange,
    placeholder
}: {
    label: string;
    provider: string;
    value: string;
    isConfigured: boolean;
    isVerified: boolean;
    onChange: (v: string) => void;
    placeholder: string;
}) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">{label}</label>
                {isVerified ? (
                    <span className="flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider text-emerald-500">
                        <CheckCircle2 className="h-3 w-3" /> Verified
                    </span>
                ) : isConfigured ? (
                    <span className="flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3" /> Saved
                    </span>
                ) : (
                    <span className="flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
                        <AlertCircle className="h-3 w-3" /> Not Configured
                    </span>
                )}
            </div>
            <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground">
                    <Key className="h-4 w-4" />
                </div>
                <input
                    type="password"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={isConfigured ? "Enter new key to replace existing" : placeholder}
                    className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 pl-10 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
            </div>
        </div>
    );
}
