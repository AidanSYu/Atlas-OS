from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import random

app = FastAPI(title="Drug Dev Agents API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SynthesisRequest(BaseModel):
    target: str = Field(..., description="Target molecule or protein name/ID")
    context: Optional[str] = None

class SynthesisRoute(BaseModel):
    route_id: str
    confidence: float
    summary: str
    steps: List[str]

class SynthesisResponse(BaseModel):
    routes: List[SynthesisRoute]

class ManufacturabilityRequest(BaseModel):
    candidate: str
    route_id: Optional[str] = None
    scale_kg: float = 1.0

class ManufacturabilityAssessment(BaseModel):
    score: float
    risks: List[str]
    notes: str

class ResearchPlanRequest(BaseModel):
    objective: str
    prior_observations: List[str] = []

class ResearchPlan(BaseModel):
    plan_id: str
    hypotheses: List[str]
    experiments: List[Dict[str, Any]]

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/synthesis/predict", response_model=SynthesisResponse)
def synthesis_predict(req: SynthesisRequest):
    rnd = random.Random(hash(req.target) & 0xFFFFFFFF)
    templates = [
        "Two-stage convergent route using readily available building blocks",
        "Modular approach focusing on functional group interconversions",
        "Fragment coupling strategy with late-stage diversification",
    ]
    routes = []
    for i in range(3):
        steps = [
            "Identify commercially available fragments",
            "Plan high-level coupling strategy",
            "Evaluate protection/deprotection needs",
            "Outline purification and analytics",
        ]
        rnd.shuffle(steps)
        routes.append(
            SynthesisRoute(
                route_id=f"route-{i+1}",
                confidence=round(0.6 + 0.1 * rnd.random(), 2),
                summary=templates[i],
                steps=steps,
            )
        )
    return SynthesisResponse(routes=routes)

@app.post("/api/manufacturability/assess", response_model=ManufacturabilityAssessment)
def manufacturability_assess(req: ManufacturabilityRequest):
    # Mock heuristic scoring: longer names and larger scale lower score
    base = max(0.0, 1.0 - min(len(req.candidate) / 200.0, 0.5))
    scale_penalty = min(req.scale_kg / 100.0, 0.5)
    score = round(max(0.1, base - scale_penalty), 2)
    risks = []
    if req.scale_kg > 10:
        risks.append("Process scale-up complexity")
    if any(k in req.candidate.lower() for k in ["peroxide", "azide", "nitro"]):
        risks.append("Potential energetic or safety-sensitive functional groups")
    if len(req.candidate) > 80:
        risks.append("Complexity may impact yield and cost")
    if not risks:
        risks = ["No major red flags from high-level screen"]
    notes = (
        "High-level manufacturability screen only; not experimental guidance. "
        "Consult process safety and regulatory experts."
    )
    return ManufacturabilityAssessment(score=score, risks=risks, notes=notes)

@app.post("/api/researcher/plan", response_model=ResearchPlan)
def researcher_plan(req: ResearchPlanRequest):
    rnd = random.Random(hash(req.objective) & 0xFFFFFFFF)
    hypotheses = [
        f"Modulating target engagement improves {req.objective}",
        f"Solubility constraints limit observed efficacy in {req.objective}",
        f"Off-target interactions drive variability in {req.objective}",
    ]
    rnd.shuffle(hypotheses)
    experiments = [
        {
            "name": "In vitro screening (conceptual)",
            "readouts": ["affinity proxy", "selectivity proxy"],
            "notes": "Design placeholder assays; do not use as lab protocol.",
        },
        {
            "name": "Formulation exploration (high-level)",
            "readouts": ["solubility class", "stability class"],
            "notes": "High-level decision support only.",
        },
        {
            "name": "Data loop",
            "readouts": ["capture results", "iterate hypotheses"],
            "notes": "Feed outcomes back to agents for prioritization.",
        },
    ]
    rnd.shuffle(experiments)
    return ResearchPlan(plan_id="plan-1", hypotheses=hypotheses[:3], experiments=experiments)



class ResearchDiseaseRequest(BaseModel):
    disease: str

class ResearchDiseaseResponse(BaseModel):
    query: str
    summary: str
    sources: List[str]

from .agents.researcher import ResearcherAgent

@app.post("/api/researcher/research", response_model=ResearchDiseaseResponse)
def researcher_research(req: ResearchDiseaseRequest):
    agent = ResearcherAgent()
    result = agent.research_disease(req.disease)
    return ResearchDiseaseResponse(**result)
