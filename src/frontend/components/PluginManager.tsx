'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Cpu, Database, Trash2, RefreshCw, Zap, ChevronDown, ChevronRight } from 'lucide-react';

interface Plugin {
  name: string;
  description: string;
  loaded: boolean;
  type: 'deterministic' | 'semantic';
  input_schema: any;
  output_schema: any;
}

interface PluginManagerProps {
  projectId?: string;
}

export function PluginManager({ projectId }: PluginManagerProps) {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [orchestratorProvider, setOrchestratorProvider] = useState<string>('');
  const [orchestratorModel, setOrchestratorModel] = useState<string>('');
  const [toolProvider, setToolProvider] = useState<string>('');
  const [toolModel, setToolModel] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [expandedPlugin, setExpandedPlugin] = useState<string | null>(null);

  const loadPlugins = async () => {
    setIsLoading(true);
    try {
      const data = await api.getPlugins();
      setPlugins(data.plugins);
      setOrchestratorProvider(data.orchestrator_provider);
      setOrchestratorModel(data.orchestrator_model);
      setToolProvider(data.tool_provider);
      setToolModel(data.tool_model);
    } catch (err) {
      console.error('Failed to load plugins:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, []);

  const handleUnload = async (pluginName: string) => {
    try {
      await api.unloadPlugin(pluginName);
      await loadPlugins();
    } catch (err) {
      console.error('Failed to unload plugin:', err);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Plugin Registry</h3>
        </div>
        <button
          onClick={loadPlugins}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent/10 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* LLM Configuration */}
      <div className="grid grid-cols-2 gap-3 p-3 bg-accent/5 rounded border border-border/50">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Orchestrator</span>
          <div className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-orange-500" />
            <span className="text-xs font-medium text-foreground">
              {orchestratorProvider}/{orchestratorModel || 'local'}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Tool Caller</span>
          <div className="flex items-center gap-2">
            <Database className="h-3.5 w-3.5 text-blue-500" />
            <span className="text-xs font-medium text-foreground">
              {toolProvider}/{toolModel || 'local'}
            </span>
          </div>
        </div>
      </div>

      {/* Plugin List */}
      <div className="flex flex-col gap-2">
        {plugins.length === 0 && !isLoading && (
          <div className="text-xs text-muted-foreground text-center py-4">
            No plugins registered
          </div>
        )}
        {plugins.map((plugin) => (
          <div
            key={plugin.name}
            className="flex flex-col gap-2 p-3 bg-background border border-border rounded-lg hover:border-primary/30 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    plugin.loaded ? 'bg-green-500' : 'bg-muted-foreground/30'
                  }`}
                  title={plugin.loaded ? 'Loaded' : 'Not loaded'}
                />
                <span className="text-xs font-medium text-foreground">{plugin.name}</span>
                <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 bg-accent/10 rounded">
                  {plugin.type}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() =>
                    setExpandedPlugin(expandedPlugin === plugin.name ? null : plugin.name)
                  }
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  {expandedPlugin === plugin.name ? (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      Hide
                    </>
                  ) : (
                    <>
                      <ChevronRight className="h-3 w-3" />
                      Schema
                    </>
                  )}
                </button>
                {plugin.loaded && (
                  <button
                    onClick={() => handleUnload(plugin.name)}
                    className="ml-2 p-1 rounded hover:bg-destructive/10 text-destructive transition-colors"
                    title="Unload plugin to free memory"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Description */}
            <p className="text-xs text-muted-foreground">{plugin.description}</p>

            {/* Schema (expanded) */}
            {expandedPlugin === plugin.name && (
              <div className="flex flex-col gap-2 mt-1 p-2 bg-accent/5 rounded text-[10px]">
                <div>
                  <span className="font-semibold text-foreground">Input:</span>
                  <pre className="mt-1 p-2 bg-background rounded overflow-x-auto text-muted-foreground">
                    {JSON.stringify(plugin.input_schema, null, 2)}
                  </pre>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Output:</span>
                  <pre className="mt-1 p-2 bg-background rounded overflow-x-auto text-muted-foreground">
                    {JSON.stringify(plugin.output_schema, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
