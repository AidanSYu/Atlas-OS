import { useState } from 'react'
import './App.css'

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export default function App() {
  const [target, setTarget] = useState('Example target')
  const [synth, setSynth] = useState<any>(null)
  const [candidate, setCandidate] = useState('Candidate-001')
  const [scale, setScale] = useState(1)
  const [mfg, setMfg] = useState<any>(null)
  const [objective, setObjective] = useState('Improve efficacy')
  const [plan, setPlan] = useState<any>(null)
  const [disease, setDisease] = useState('Type 2 diabetes')
  const [research, setResearch] = useState<any>(null)
  const [compoundName, setCompoundName] = useState('aspirin')
  const [compoundSmiles, setCompoundSmiles] = useState('')
  const [compoundAnalysis, setCompoundAnalysis] = useState<any>(null)
  const [integratedDisease, setIntegratedDisease] = useState('Type 2 diabetes')
  const [integratedResults, setIntegratedResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  return (
    <div style={{ padding: 16, maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif' }}>
      <h1>Drug Dev Agents (Prototype)</h1>

      <section>
        <h2>Synthesis predictor</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={target} onChange={(e)=>setTarget(e.target.value)} placeholder="Target molecule or protein" style={{ flex: 1 }} />
          <button onClick={async()=>setSynth(await api('/synthesis/predict',{method:'POST', body: JSON.stringify({target})}))}>Predict</button>
        </div>
        {synth && (
          <ul>
            {synth.routes.map((r: any)=>(
              <li key={r.route_id}>
                <strong>{r.route_id}</strong> • conf {r.confidence} • {r.summary}
                <ul>
                  {r.steps.map((s: string, i: number)=>(<li key={i}>{s}</li>))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Manufacturability agent</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={candidate} onChange={(e)=>setCandidate(e.target.value)} placeholder="Candidate name" style={{ flex: 1 }} />
          <input type="number" value={scale} onChange={(e)=>setScale(parseFloat(e.target.value))} style={{ width: 120 }} /> kg
          <button onClick={async()=>setMfg(await api('/manufacturability/assess',{method:'POST', body: JSON.stringify({candidate, scale_kg: scale})}))}>Assess</button>
        </div>
        {mfg && (
          <div>
            <div>Score: {mfg.score}</div>
            <div>Risks: {mfg.risks.join(', ')}</div>
            <div style={{ fontStyle: 'italic' }}>{mfg.notes}</div>
          </div>
        )}
      </section>

      <section>
        <h2>Researcher agent</h2>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <input value={objective} onChange={(e)=>setObjective(e.target.value)} placeholder="Objective" style={{ flex: 1 }} />
          <button onClick={async()=>setPlan(await api('/researcher/plan',{method:'POST', body: JSON.stringify({objective})}))}>Generate plan</button>
        </div>
        {plan && (
          <div>
            <h3>Hypotheses</h3>
            <ul>{plan.hypotheses.map((h:string,i:number)=>(<li key={i}>{h}</li>))}</ul>
            <h3>Experiments</h3>
            <ul>{plan.experiments.map((ex:any,i:number)=>(<li key={i}><strong>{ex.name}</strong> — {ex.readouts?.join(', ')} {ex.notes?`• ${ex.notes}`:''}</li>))}</ul>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <input value={disease} onChange={(e)=>setDisease(e.target.value)} placeholder="Disease to research" style={{ flex: 1 }} />
          <button onClick={async()=>setResearch(await api('/researcher/research',{method:'POST', body: JSON.stringify({disease})}))}>Research disease</button>
        </div>
        {research && (
          <div style={{ marginTop: 8 }}>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{research.summary}</pre>
            <div>Sources:</div>
            <ul>
              {research.sources.map((s:string,i:number)=>(<li key={i}><a href={s} target="_blank">{s}</a></li>))}
            </ul>
          </div>
        )}
      </section>

      <section>
        <h2>Compound Analysis</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={compoundName} onChange={(e)=>setCompoundName(e.target.value)} placeholder="Compound name" style={{ flex: 1 }} />
          <input value={compoundSmiles} onChange={(e)=>setCompoundSmiles(e.target.value)} placeholder="SMILES (optional)" style={{ flex: 1 }} />
          <button onClick={async()=>setCompoundAnalysis(await api('/synthesis/analyze',{method:'POST', body: JSON.stringify({compound_name: compoundName, smiles: compoundSmiles || undefined})}))}>Analyze</button>
        </div>
        {compoundAnalysis && (
          <div style={{ marginTop: 8 }}>
            <h3>{compoundAnalysis.compound_name} ({compoundAnalysis.molecule_type})</h3>
            {compoundAnalysis.smiles && <div><strong>SMILES:</strong> {compoundAnalysis.smiles}</div>}
            <h4>Synthesis Analysis</h4>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em' }}>{JSON.stringify(compoundAnalysis.synthesis_analysis, null, 2)}</pre>
            <h4>Manufacturability</h4>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em' }}>{JSON.stringify(compoundAnalysis.manufacturability, null, 2)}</pre>
            <h4>Summary</h4>
            <p style={{ whiteSpace: 'pre-wrap' }}>{compoundAnalysis.integrated_summary}</p>
          </div>
        )}
      </section>

      <section>
        <h2>Integrated Research & Manufacturing</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={integratedDisease} onChange={(e)=>setIntegratedDisease(e.target.value)} placeholder="Disease to research" style={{ flex: 1 }} />
          <button 
            disabled={loading}
            onClick={async()=>{
              setLoading(true);
              try {
                setIntegratedResults(await api('/integrated/research-and-manufacture',{method:'POST', body: JSON.stringify({disease: integratedDisease})}));
              } finally {
                setLoading(false);
              }
            }}>
            {loading ? 'Processing...' : 'Research & Analyze'}
          </button>
        </div>
        {integratedResults && (
          <div style={{ marginTop: 8 }}>
            <h3>Research Summary for {integratedResults.disease}</h3>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{integratedResults.research_summary}</pre>
            <div>Sources:</div>
            <ul>
              {integratedResults.research_sources.map((s:string,i:number)=>(<li key={i}><a href={s} target="_blank">{s}</a></li>))}
            </ul>
            <h3>Compound Analyses</h3>
            {integratedResults.compound_analyses.map((ca:any,i:number)=>(
              <div key={i} style={{ marginBottom: 16, padding: 12, border: '1px solid #ddd', borderRadius: 4 }}>
                <h4>{ca.compound_name} ({ca.molecule_type})</h4>
                {ca.smiles && <div><strong>SMILES:</strong> {ca.smiles}</div>}
                <div><strong>Synthesis feasibility:</strong> {ca.synthesis_analysis.feasibility_score}/10</div>
                <div><strong>Manufacturability score:</strong> {ca.manufacturability.score}/10</div>
                <p style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{ca.integrated_summary}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <p style={{marginTop:24, color:'#666'}}>All outputs are conceptual placeholders and not lab instructions.</p>
    </div>
  )
}
