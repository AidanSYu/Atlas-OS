'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Loader2, Database, Brain, FolderOpen } from 'lucide-react';
import { api, getApiBase } from '@/lib/api';

interface SetupStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'success' | 'error';
  errorMessage?: string;
}

interface SetupWizardProps {
  onComplete: () => void;
  onSkip?: () => void;
}

/**
 * First-run setup wizard for Atlas desktop app.
 * Verifies all required services and models are available.
 */
export function SetupWizard({ onComplete, onSkip }: SetupWizardProps) {
  const [steps, setSteps] = useState<SetupStep[]>([
    {
      id: 'directories',
      name: 'Initialize Data Directories',
      description: 'Creating required folders for data storage',
      status: 'pending',
    },
    {
      id: 'database',
      name: 'Connect to Database',
      description: 'Verifying embedded SQLite database',
      status: 'pending',
    },
    {
      id: 'vector',
      name: 'Connect to Vector Store',
      description: 'Verifying embedded Qdrant vector store',
      status: 'pending',
    },
    {
      id: 'models',
      name: 'Verify AI Models',
      description: 'Checking LLM and embedding models',
      status: 'pending',
    },
  ]);

  const [currentStep, setCurrentStep] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [hasError, setHasError] = useState(false);

  const updateStep = (index: number, update: Partial<SetupStep>) => {
    setSteps(prev => prev.map((step, i) => 
      i === index ? { ...step, ...update } : step
    ));
  };

  const runSetup = async () => {
    setIsRunning(true);
    setHasError(false);

    for (let i = 0; i < steps.length; i++) {
      setCurrentStep(i);
      updateStep(i, { status: 'running' });

      try {
        await runStepCheck(steps[i].id);
        updateStep(i, { status: 'success' });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        updateStep(i, { status: 'error', errorMessage });
        setHasError(true);
        setIsRunning(false);
        return;
      }

      // Small delay between steps for visual feedback
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setIsRunning(false);
    
    // Mark setup as complete
    if (typeof window !== 'undefined') {
      localStorage.setItem('atlas_setup_complete', 'true');
    }
    
    // Small delay before completing
    await new Promise(resolve => setTimeout(resolve, 1000));
    onComplete();
  };

  const runStepCheck = async (stepId: string): Promise<void> => {
    switch (stepId) {
      case 'directories': {
        const framework = await api.getFrameworkStatus();
        if (framework.status !== 'ok') {
          throw new Error(framework.message || 'Framework startup check failed');
        }
        break;
      }

      case 'database': {
        const framework = await api.getFrameworkStatus();
        if (framework.status !== 'ok') {
          throw new Error(framework.message || 'Database check failed');
        }
        break;
      }

      case 'vector': {
        const runtime = await api.getFrameworkRuntime();
        if (runtime.status !== 'ok') {
          throw new Error('Vector store runtime check failed');
        }
        break;
      }

      case 'models': {
        const response = await fetch(`${getApiBase()}/models`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.error || `Service check failed: ${response.status}`);
        }
        
        const inventory = await response.json();
        if (!inventory.models_dir) {
          throw new Error(`Model inventory unavailable: ${JSON.stringify(inventory)}`);
        }
        break;
      }

      default:
        throw new Error(`Unknown step: ${stepId}`);
    }
  };

  const getStepIcon = (status: SetupStep['status']) => {
    switch (status) {
      case 'pending':
        return <div className="w-6 h-6 rounded-full border-2 border-gray-300" />;
      case 'running':
        return <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />;
      case 'success':
        return <CheckCircle className="w-6 h-6 text-green-500" />;
      case 'error':
        return <XCircle className="w-6 h-6 text-red-500" />;
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-900 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <Brain className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome to Atlas</h1>
          <p className="text-gray-600 mt-2">
            Setting up your knowledge management system
          </p>
        </div>

        {/* Steps */}
        <div className="space-y-4 mb-8">
          {steps.map((step, index) => (
            <div
              key={step.id}
              className={`flex items-start gap-4 p-4 rounded-lg transition-colors ${
                index === currentStep && isRunning
                  ? 'bg-blue-50 border border-blue-200'
                  : step.status === 'error'
                  ? 'bg-red-50 border border-red-200'
                  : step.status === 'success'
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-gray-50'
              }`}
            >
              <div className="flex-shrink-0 mt-0.5">
                {getStepIcon(step.status)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900">{step.name}</p>
                <p className="text-sm text-gray-500">{step.description}</p>
                {step.status === 'error' && step.errorMessage && (
                  <p className="text-sm text-red-600 mt-1">{step.errorMessage}</p>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          {!isRunning && !hasError && steps.every(s => s.status === 'pending') && (
            <>
              <button
                onClick={runSetup}
                className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                Start Setup
              </button>
              {onSkip && (
                <button
                  onClick={onSkip}
                  className="px-4 py-3 text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Skip
                </button>
              )}
            </>
          )}

          {isRunning && (
            <div className="flex-1 bg-gray-100 text-gray-500 py-3 px-4 rounded-lg font-medium text-center">
              Setting up...
            </div>
          )}

          {hasError && (
            <button
              onClick={runSetup}
              className="flex-1 bg-red-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-red-700 transition-colors"
            >
              Retry Setup
            </button>
          )}

          {!isRunning && !hasError && steps.every(s => s.status === 'success') && (
            <div className="flex-1 bg-green-100 text-green-700 py-3 px-4 rounded-lg font-medium text-center">
              Setup Complete!
            </div>
          )}
        </div>

        {/* Help text */}
        {hasError && (
          <p className="text-sm text-gray-500 text-center mt-4">
            Make sure all services are running and try again.
            Check the console for more details.
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Hook to check if setup is needed.
 */
export function useSetupCheck(): { needsSetup: boolean; markComplete: () => void } {
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const setupComplete = localStorage.getItem('atlas_setup_complete');
      setNeedsSetup(!setupComplete);
    }
  }, []);

  const markComplete = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('atlas_setup_complete', 'true');
    }
    setNeedsSetup(false);
  };

  return { needsSetup, markComplete };
}
