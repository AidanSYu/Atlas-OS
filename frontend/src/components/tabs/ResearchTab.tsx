import { useState } from 'react'
import '../../styles/ResearchTab.css'

interface Project {
  id: string
  name: string
  disease: string
}

interface ResearchTabProps {
  project: Project
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  references?: Array<{
    title: string
    url: string
    snippet?: string
    doi?: string
  }>
}

interface Paper {
  id: number
  title: string
  url: string
  description: string
  snippet: string
  doi: string | null
}

interface Pathway {
  id: number
  pathway_name: string
  molecular_targets: string[]
  mechanism: string
  stage: string
  compounds: string[]
}

type TabType = 'chatbot' | 'pathways'

export default function ResearchTab({ project }: ResearchTabProps) {
  const [activeTab, setActiveTab] = useState<TabType>('chatbot')

  // Chatbot state
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `Hello! I'm your professional pharmaceutical research assistant for ${project.disease}. I can answer technical questions, explain mechanisms, and search for scientific literature using real-time web access. Ask me anything about ${project.disease}.`,
      timestamp: new Date()
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)



  // Pathways state
  const [pathways, setPathways] = useState<Pathway[]>([])
  const [pathwayDisease, setPathwayDisease] = useState(project.disease)
  const [isGeneratingPathways, setIsGeneratingPathways] = useState(false)

  // Chatbot handler
  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    const currentInput = input
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/research/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: currentInput,
          disease_context: project.disease
        })
      })

      if (!response.ok) {
        throw new Error(`Chat request failed: ${response.statusText}`)
      }

      const data = await response.json()

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        references: data.references || []
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error.message}. Please check if the backend server is running.`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }



  // Pathways handler
  const handleGeneratePathways = async () => {
    if (!pathwayDisease.trim() || isGeneratingPathways) return

    setIsGeneratingPathways(true)
    setPathways([])

    try {
      const response = await fetch('/api/research/pathways', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          disease: pathwayDisease
        })
      })

      if (!response.ok) {
        throw new Error(`Pathway generation failed: ${response.statusText}`)
      }

      const data = await response.json()
      setPathways(data.pathways || [])
    } catch (error: any) {
      console.error('Pathway generation error:', error)
    } finally {
      setIsGeneratingPathways(false)
    }
  }

  return (
    <div className="research-tab">
      <div className="research-header">
        <div className="tab-navigation">
          <button
            className={`tab-btn ${activeTab === 'chatbot' ? 'active' : ''}`}
            onClick={() => setActiveTab('chatbot')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            Professional Chatbot
          </button>

          <button
            className={`tab-btn ${activeTab === 'pathways' ? 'active' : ''}`}
            onClick={() => setActiveTab('pathways')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            Disease Pathways
          </button>
        </div>
      </div>

      <div className="research-content">
        {/* CHATBOT TAB */}
        {activeTab === 'chatbot' && (
          <div className="chatbot-section">
            <div className="context-banner">
              <strong>Project:</strong> {project.name} | <strong>Disease:</strong> {project.disease}
            </div>
            <div className="chat-messages">
              {messages.map(msg => (
                <div key={msg.id} className={`message ${msg.role}`}>
                  <div className="message-avatar">
                    {msg.role === 'user' ? (
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                      </svg>
                    )}
                  </div>
                  <div className="message-content">
                    <div className="message-text">{msg.content}</div>
                    {msg.references && msg.references.length > 0 && (
                      <div className="message-references">
                        <div className="references-header">References:</div>
                        {msg.references.map((ref, idx) => (
                          <div key={idx} className="reference-item">
                            <a href={ref.url} target="_blank" rel="noopener noreferrer">
                              {ref.title}
                              {ref.doi && <span className="ref-doi"> (DOI: {ref.doi})</span>}
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="message-time">
                      {msg.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-avatar">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                    </svg>
                  </div>
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="chat-input-container">
              <div className="chat-input-wrapper">
                <textarea
                  className="chat-input"
                  placeholder="Ask technical questions about pharmacology, mechanisms, clinical trials..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  rows={1}
                />
                <button
                  className="send-btn"
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}



        {/* DISEASE PATHWAYS TAB */}
        {activeTab === 'pathways' && (
          <div className="pathways-section">
            <div className="pathways-header">
              <h2>Therapeutic Pathways Generator</h2>
              <p>Generate molecular pathway analyses for specific diseases</p>
            </div>

            <div className="pathway-input-group">
              <input
                type="text"
                className="pathway-disease-input"
                placeholder="Enter disease name"
                value={pathwayDisease}
                onChange={(e) => setPathwayDisease(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleGeneratePathways()
                  }
                }}
              />
              <button
                className="generate-btn"
                onClick={handleGeneratePathways}
                disabled={isGeneratingPathways || !pathwayDisease.trim()}
              >
                {isGeneratingPathways ? 'Generating...' : 'Generate Pathways'}
              </button>
            </div>

            {pathways.length > 0 && (
              <div className="pathways-grid">
                {pathways.map(pathway => (
                  <div key={pathway.id} className="pathway-card">
                    <div className="pathway-header">
                      <h3>{pathway.pathway_name}</h3>
                      <span className="stage-badge">{pathway.stage}</span>
                    </div>

                    <div className="pathway-section">
                      <h4>Molecular Targets</h4>
                      <div className="targets-list">
                        {pathway.molecular_targets.map((target, idx) => (
                          <span key={idx} className="target-tag">{target}</span>
                        ))}
                      </div>
                    </div>

                    <div className="pathway-section">
                      <h4>Mechanism of Action</h4>
                      <p>{pathway.mechanism}</p>
                    </div>

                    {pathway.compounds && pathway.compounds.length > 0 && (
                      <div className="pathway-section">
                        <h4>Key Compounds</h4>
                        <div className="compounds-list">
                          {pathway.compounds.map((compound, idx) => (
                            <span key={idx} className="compound-tag">{compound}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {!isGeneratingPathways && pathways.length === 0 && (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
                <p>Enter a disease name to generate therapeutic pathways</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
