import { useState } from 'react'
import './App.css'

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export default function App() {
    const [disease, setDisease] = useState('Type 2 diabetes')
    const [pathways, setPathways] = useState<any[]>([])
    const [selectedPathway, setSelectedPathway] = useState<any>(null)
    const [analysisLoading, setAnalysisLoading] = useState(false)
    const [analysisProgress, setAnalysisProgress] = useState(0)
    const [analysisTimeout, setAnalysisTimeout] = useState(false)
    const [researchLoading, setResearchLoading] = useState(false)
    const [debugLogs, setDebugLogs] = useState<string[]>([])
    const [showDebug, setShowDebug] = useState(false)
    const [etaSeconds, setEtaSeconds] = useState(0)
    const [etaRemaining, setEtaRemaining] = useState(0)
    const [showModal, setShowModal] = useState(false)
    const [activeTab, setActiveTab] = useState<'overview' | 'retrosynthesis' | 'manufacturing' | 'references'>('overview')
    const [sources, setSources] = useState<string[]>([])
    
    const addDebugLog = (msg: string) => {
      const timestamp = new Date().toLocaleTimeString()
      setDebugLogs(prev => [...prev, `[${timestamp}] ${msg}`])
    }

    return (
      <div style={{ padding: 16, maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif' }}>
        <h1>Drug Dev — Research → Retrosynthesis → Manufacturing</h1>

        <section>
          <h2>Disease Research</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={disease} onChange={(e)=>setDisease(e.target.value)} placeholder="Disease to research" style={{ flex: 1 }} />
            <button 
              disabled={researchLoading}
              onClick={async()=>{
                setResearchLoading(true);
                setPathways([])
                setSelectedPathway(null)
                setAnalysisTimeout(false)
                setDebugLogs([])
                addDebugLog(`Starting pathway research for: ${disease}`)
                try {
                  addDebugLog('Calling /api/researcher/pathways...')
                  const res = await api<any>('/researcher/pathways',{method:'POST', body: JSON.stringify({disease})});
                  addDebugLog(`Received ${res.pathways?.length || 0} pathways`)
                  setPathways(res.pathways || [])
                } catch(e:any) {
                  addDebugLog(`ERROR: ${e?.message || e}`)
                  alert('Pathway generation failed: ' + (e?.message || e))
                } finally {
                  setResearchLoading(false);
                }
              }}>
              {researchLoading ? 'Finding pathways...' : 'Find Pathways'}
            </button>
          </div>

          <div style={{ marginTop: 12 }}>
            <p style={{ color: '#666' }}>Pick one of the proposed pathways to run a deep analysis. The system will estimate how long the analysis takes and run the heavy LLM work in the background.</p>
          </div>

          {pathways && pathways.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {pathways.map((p:any)=>(
                <div key={p.id} style={{ border: '1px solid #ddd', padding: 12, borderRadius: 6, width: 320 }}>
                  <strong>{p.title}</strong>
                  <p style={{ minHeight: 48 }}>{p.summary}</p>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={async()=>{
                      setSelectedPathway(p);
                      setAnalysisLoading(true);
                      setAnalysisProgress(5);
                      setAnalysisTimeout(false);
                      setEtaSeconds(0);
                      setEtaRemaining(0);
                      addDebugLog(`Starting deep analysis for pathway: ${p.title}`)

                      try{
                        addDebugLog('Calling /api/researcher/deep_analyze/start...')
                        const start = await api<{task_id:string, eta_seconds:number}>('/researcher/deep_analyze/start', {method:'POST', body: JSON.stringify({disease, pathway_text: p.summary})});
                        const taskId = start.task_id;
                        const eta = start.eta_seconds || 60;
                        setEtaSeconds(eta);
                        setEtaRemaining(eta);
                        const startedAt = Date.now();
                        addDebugLog(`Task ${taskId} started. ETA: ${eta} seconds`)

                        // Poll status every 2s
                        const pollInterval = 2000;
                        const poll = setInterval(async ()=>{
                          try{
                            const st = await api<any>(`/researcher/deep_analyze/status/${taskId}`);
                            addDebugLog(`Poll: status=${st.status}, eta_remaining=${st.eta_remaining || 'N/A'}`)
                            setEtaRemaining(st.eta_remaining || 0);
                            
                            if(st.status === 'running' || st.status === 'pending'){
                              const elapsed = (Date.now() - startedAt)/1000;
                              const frac = Math.min(0.95, Math.max(0.05, elapsed / Math.max(1, eta)));
                              setAnalysisProgress(Math.round(5 + frac*90));
                            } else if(st.status === 'done'){
                              clearInterval(poll);
                              setAnalysisProgress(100);
                              setAnalysisLoading(false);
                              addDebugLog('Analysis completed successfully!')
                              // attach report to this pathway
                              setPathways(prev=>prev.map(x=> x.id===p.id ? {...x, report: st.result} : x));
                            } else if(st.status === 'failed'){
                              clearInterval(poll);
                              setAnalysisLoading(false);
                              setAnalysisTimeout(true);
                              addDebugLog(`ERROR: Analysis failed - ${st.error || 'unknown error'}`)
                              alert('Analysis failed: ' + (st.error || 'unknown error'))
                            }
                          }catch(e:any){
                            clearInterval(poll);
                            setAnalysisLoading(false);
                            setAnalysisTimeout(true);
                            addDebugLog(`ERROR: Polling failed - ${e?.message || e}`)
                            alert('Polling failed: ' + (e?.message || e))
                          }
                        }, pollInterval);

                        // Safety hang timer (5 minutes)
                        setTimeout(()=>{
                          setAnalysisTimeout(true);
                          setAnalysisLoading(false);
                          addDebugLog('WARNING: 5 minute timeout reached')
                        }, 300000);
                      }catch(e:any){
                        setAnalysisTimeout(true);
                        setAnalysisLoading(false);
                        addDebugLog(`ERROR: Failed to start analysis - ${e?.message || e}`)
                        alert('Failed to start analysis: ' + (e?.message || e))
                      }
                    }}>{analysisLoading && selectedPathway?.id===p.id ? 'Analyzing...' : 'Select & Analyze'}</button>
                  </div>

                  {p.report && (
                    <div style={{ marginTop: 10 }}>
                      <h5>Results</h5>
                      <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 220, overflowY: 'auto' }}>{p.report.deep_analysis}</pre>
                      <h6 style={{ marginTop: 8 }}>Candidates</h6>
                      {p.report.candidates.map((c:any, idx:number)=> (
                        <div key={idx} style={{ marginBottom: 8, padding: 8, border: '1px solid #eee', borderRadius:4 }}>
                          <strong>{c.name}</strong> {c.smiles && <span>({c.smiles})</span>}
                          <div style={{ fontSize: '0.9em', marginTop: 6 }}>
                            <div><strong>Retrosynthesis:</strong></div>
                            <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 120, overflowY: 'auto' }}>{JSON.stringify(c.retrosynthesis, null, 2)}</pre>
                            <div><strong>Manufacturability:</strong></div>
                            <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 120, overflowY: 'auto' }}>{JSON.stringify(c.manufacturability, null, 2)}</pre>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {analysisLoading && (
            <div style={{ marginTop: 12 }}>
              <div>Deep Analysis in Progress:</div>
              <div style={{ height: 80, border: '1px solid #eee', padding: 8, overflowY: 'auto', background: '#fafafa' }}>
                <div><em>Processing... progress: {Math.round(analysisProgress)}%</em></div>
                {etaSeconds > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <strong>Estimated time:</strong> {etaSeconds}s total | {etaRemaining}s remaining
                  </div>
                )}
                <div style={{ fontSize: '0.85em', marginTop: 4, color: '#666' }}>
                  Running: Ollama research → ChemLLM retrosynthesis → ChemLLM manufacturing
                </div>
              </div>
              <div style={{ marginTop: 8 }}>
                <div style={{ height: 8, background: '#eee', borderRadius: 4 }}>
                  <div style={{ width: `${analysisProgress}%`, height: '8px', background: '#4caf50', borderRadius: 4 }} />
                </div>
              </div>
            </div>
          )}

          {analysisTimeout && (
            <div style={{ marginTop: 12, color: 'crimson' }}>
              The analysis is taking unusually long — the model may be hanging. Try again or check that Ollama/ChemLLM are running locally.
            </div>
          )}
        </section>

        <p style={{marginTop:24, color:'#666'}}>Notes: the Researcher uses a local Ollama `llama3.1` model; retrosynthesis/manufacturing use ChemLLM. Ensure both services are available for full functionality.</p>

        <section style={{ marginTop: 32, borderTop: '2px solid #eee', paddingTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Debug Console</h3>
            <button onClick={() => setShowDebug(!showDebug)} style={{ padding: '6px 12px' }}>
              {showDebug ? 'Hide' : 'Show'} Debug Logs
            </button>
          </div>
          
          {showDebug && (
            <div style={{ 
              marginTop: 12, 
              background: '#1e1e1e', 
              color: '#d4d4d4', 
              padding: 12, 
              borderRadius: 4, 
              fontFamily: 'monospace', 
              fontSize: '0.85em',
              maxHeight: 400,
              overflowY: 'auto'
            }}>
              {debugLogs.length === 0 ? (
                <div style={{ color: '#888' }}>No logs yet. Start a pathway search to see activity.</div>
              ) : (
                debugLogs.map((log, idx) => (
                  <div key={idx} style={{ marginBottom: 4, whiteSpace: 'pre-wrap' }}>
                    {log}
                  </div>
                ))
              )}
            </div>
          )}
        </section>

      </div>
    )
  }
