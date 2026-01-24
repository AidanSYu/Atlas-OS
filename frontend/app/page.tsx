'use client';

import React, { useState, useEffect } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import FileSidebar from '@/components/FileSidebar';
import ChatInterface from '@/components/ChatInterface';
import PDFViewer from '@/components/PDFViewer';
import GraphCanvas from '@/components/GraphCanvas';
import { api } from '@/lib/api';
import { FileText, Network } from 'lucide-react';

export default function Home() {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'document' | 'graph'>('document');
  const [pdfPage, setPdfPage] = useState<number>(1);
  const [centerDimensions, setCenterDimensions] = useState({ width: 800, height: 600 });

  const handleCitationClick = (filename: string, page: number) => {
    // We only have filename here; PDF view needs docId to stream.
    // The sidebar click sets both; citation jumps will just switch to Document tab.
    setPdfPage(page);
    setActiveView('document');
  };

  const handleFileSelect = (docId: string, filename: string) => {
    setSelectedDocId(docId);
    setSelectedFilename(filename);
    setPdfPage(1);
    setActiveView('document');
  };

  useEffect(() => {
    const updateDimensions = () => {
      const centerPanel = document.getElementById('center-panel');
      if (centerPanel) {
        setCenterDimensions({
          width: centerPanel.clientWidth,
          height: centerPanel.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  return (
    <main className="h-screen w-screen overflow-hidden bg-gray-900">
      <PanelGroup direction="horizontal">
        {/* Left Panel: File Sidebar */}
        <Panel defaultSize={20} minSize={15} maxSize={30}>
          <FileSidebar onFileSelect={handleFileSelect} selectedDocId={selectedDocId} />
        </Panel>

        <PanelResizeHandle className="w-1 bg-gray-300 hover:bg-blue-500 transition-colors" />

        {/* Center Panel: Document/Graph View */}
        <Panel defaultSize={50} minSize={30}>
          <div id="center-panel" className="h-full flex flex-col bg-white">
            {/* Tabs */}
            <div className="flex border-b border-gray-200 bg-gray-50">
              <button
                onClick={() => setActiveView('document')}
                className={`
                  flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors
                  ${
                    activeView === 'document'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }
                `}
              >
                <FileText className="h-4 w-4" />
                Document View
              </button>
              <button
                onClick={() => setActiveView('graph')}
                className={`
                  flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors
                  ${
                    activeView === 'graph'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }
                `}
              >
                <Network className="h-4 w-4" />
                Graph View
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-hidden">
              {activeView === 'document' ? (
                selectedDocId && selectedFilename ? (
                  <PDFViewer
                    fileUrl={api.getFileUrl(selectedDocId)}
                    filename={selectedFilename}
                    initialPage={pdfPage}
                  />
                ) : (
                  <div className="h-full flex items-center justify-center bg-gray-50">
                    <div className="text-center">
                      <FileText className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-500 mb-2">No document selected</p>
                      <p className="text-sm text-gray-400">
                        Select a file from the sidebar or click a citation in the chat
                      </p>
                    </div>
                  </div>
                )
              ) : (
                <GraphCanvas
                  height={centerDimensions.height}
                  width={centerDimensions.width}
                />
              )}
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-1 bg-gray-300 hover:bg-blue-500 transition-colors" />

        {/* Right Panel: Chat Interface */}
        <Panel defaultSize={30} minSize={25} maxSize={40}>
          <ChatInterface onCitationClick={handleCitationClick} />
        </Panel>
      </PanelGroup>
    </main>
  );
}
