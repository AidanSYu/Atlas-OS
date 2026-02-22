'use client';

import { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface TourStep {
  target: string;
  title: string;
  description: string;
  placement: 'top' | 'bottom' | 'left' | 'right';
}

const TOUR_STEPS: TourStep[] = [
  {
    target: '#atlas-library-sidebar',
    title: 'Document Library',
    description: 'Upload PDFs, search your documents, and see ingestion status here. Drag documents onto the canvas for spatial organization.',
    placement: 'right',
  },
  {
    target: '#atlas-view-tabs',
    title: 'Research Views',
    description: 'Switch between Documents, Editor, Knowledge Graph, Deep Chat, and Canvas. Each view offers different ways to interact with your research.',
    placement: 'bottom',
  },
  {
    target: '#atlas-context-engine',
    title: 'Context Engine',
    description: 'See related concepts, citations, and graph insights automatically as you work. The AI proactively surfaces relevant information.',
    placement: 'left',
  },
  {
    target: '#atlas-omnibar-trigger',
    title: 'Command Palette',
    description: 'Press Cmd/Ctrl+K anywhere to open the command palette for quick navigation and actions.',
    placement: 'bottom',
  },
];

export function WelcomeTour() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('atlas-tour-seen');
    if (!hasSeenTour) {
      setTimeout(() => setIsOpen(true), 1500);
    }
  }, []);

  const handleComplete = () => {
    localStorage.setItem('atlas-tour-seen', 'true');
    setIsOpen(false);
  };

  const handleSkip = () => {
    if (confirm('Skip the tour? You can restart it from settings.')) {
      handleComplete();
    }
  };

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];
  const progress = ((currentStep + 1) / TOUR_STEPS.length) * 100;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[300] pointer-events-none">
        {/* Overlay */}
        <div 
          className="absolute inset-0 bg-background/90 backdrop-blur-sm pointer-events-auto"
          onClick={handleSkip}
        />

        {/* Tooltip */}
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -10 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="absolute pointer-events-auto max-w-sm rounded-xl border border-primary/40 bg-card/98 backdrop-blur-xl p-6 shadow-2xl"
          style={{
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        >
          {/* Progress Bar */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-surface overflow-hidden rounded-t-xl">
            <motion.div 
              className="h-full bg-gradient-to-r from-primary to-accent"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>

          <button
            onClick={handleComplete}
            className="absolute right-3 top-3 p-1.5 hover:bg-surface rounded-lg transition-colors"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>

          <div className="mt-2">
            <div className="text-base font-semibold text-foreground mb-2 font-serif">
              {step.title}
            </div>
            <div className="text-sm text-muted-foreground leading-relaxed mb-6">
              {step.description}
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                {TOUR_STEPS.map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 rounded-full transition-all ${
                      i === currentStep
                        ? 'w-6 bg-primary'
                        : i < currentStep
                        ? 'w-1.5 bg-accent'
                        : 'w-1.5 bg-surface'
                    }`}
                  />
                ))}
              </div>
              
              <div className="flex gap-2">
                {currentStep > 0 && (
                  <button
                    onClick={() => setCurrentStep(currentStep - 1)}
                    className="flex items-center gap-1.5 rounded-lg bg-surface px-3 py-2 text-xs font-medium text-foreground hover:bg-surface/80 transition-colors"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Back
                  </button>
                )}
                <button
                  onClick={() => {
                    if (currentStep < TOUR_STEPS.length - 1) {
                      setCurrentStep(currentStep + 1);
                    } else {
                      handleComplete();
                    }
                  }}
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  {currentStep < TOUR_STEPS.length - 1 ? 'Next' : 'Get Started'}
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
