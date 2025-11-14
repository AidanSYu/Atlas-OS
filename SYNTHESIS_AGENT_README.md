# Synthesis & Manufacturability Agent

## Overview

A new agent (`SynthesisManufacturerAgent`) has been created that communicates with the researcher agent to provide comprehensive manufacturability analysis for drug candidates.

## Features

### 1. **Molecule Type Classification**
Automatically classifies compounds into:
- Small molecules (retrosynthesis analysis)
- Monoclonal antibodies
- Proteins/peptides
- Nucleic acids (mRNA, siRNA)
- Other biologics

### 2. **Synthesis Analysis**

#### Small Molecules
- **IBM RXN Integration**: Ready to use IBM RXN API for AI-powered retrosynthesis (requires API key)
- **LLM Fallback**: Uses local Ollama/Mistral for retrosynthesis when IBM RXN unavailable
- Provides:
  - Retrosynthetic disconnections
  - Forward synthesis routes (3-5 steps)
  - Key challenges (stereochemistry, functional groups)
  - Starting materials
  - Estimated yields
  - Scale-up considerations

#### Biologics (Proteins, Antibodies, etc.)
- Expression system recommendations (E. coli, CHO, yeast)
- Production process details
- Purification strategies
- Post-translational modifications
- Quality control parameters
- Scale-up pathways
- Formulation considerations
- Cost of goods estimates

### 3. **Manufacturability Assessment**
- Manufacturability score (0-100)
- Critical risk factors
- Regulatory considerations (CMC, stability)
- Cost drivers
- Timeline estimates (research → Phase I → commercial)
- Specific recommendations

## API Endpoints

### 1. Analyze Single Compound
```bash
curl -X POST http://localhost:8000/api/synthesis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "compound_name": "Metformin",
    "smiles": "CN(C)C(=N)NC(=N)N",
    "researcher_context": "Treatment for Type 2 diabetes"
  }'
```

**Response includes:**
- `compound_name`: Name of compound
- `molecule_type`: Classification (small_molecule, protein_peptide, etc.)
- `smiles`: SMILES string (if provided)
- `synthesis_analysis`: Detailed synthesis route
- `manufacturability`: Assessment with score and risks
- `integrated_summary`: Executive summary

### 2. Integrated Research + Manufacturing
```bash
curl -X POST http://localhost:8000/api/integrated/research-and-manufacture \
  -H "Content-Type: application/json" \
  -d '{"disease": "Type 2 diabetes"}'
```

**Process:**
1. Researcher agent searches for treatments
2. Extracts compound names from research
3. Analyzes each compound for manufacturability
4. Returns comprehensive report

**Response includes:**
- `disease`: Disease name
- `research_summary`: Treatment research findings
- `research_sources`: URLs from web search
- `compound_analyses`: Array of synthesis/manufacturability analyses

### 3. Original Research Endpoint (still available)
```bash
curl -X POST http://localhost:8000/api/researcher/research \
  -H "Content-Type: application/json" \
  -d '{"disease": "Type 2 diabetes"}'
```

## IBM RXN Integration

To use IBM RXN for retrosynthesis:

1. Get API key from https://rxn.res.ibm.com/
2. Configure in code:
```python
agent = SynthesisManufacturerAgent(ibm_rxn_api_key="your_api_key_here")
```

Without API key, the agent automatically falls back to LLM-based analysis.

## Architecture

```
User Request
    ↓
ResearcherAgent
    ↓ (research findings)
SynthesisManufacturerAgent
    ↓
├── Classify molecule type
├── Small Molecule → Retrosynthesis (IBM RXN or LLM)
├── Biologic → Production process (LLM)
└── Manufacturability Assessment
    ↓
Integrated Response
```

## File Structure

```
backend/
├── app.py                           # API endpoints
└── agents/
    ├── researcher.py                # Research agent
    ├── synthesis_manufacturer.py    # NEW: Synthesis & manufacturing agent
    ├── synthesis.py                 # Legacy synthesis predictor
    └── manufacturability.py         # Legacy manufacturability
```

## Example Use Cases

### 1. Small Molecule Drug
Input: Metformin (antidiabetic)
Output: Retrosynthetic analysis, commercial synthesis route, yield estimates, scale-up considerations

### 2. Biologic Drug
Input: Semaglutide (GLP-1 agonist peptide)
Output: CHO cell expression strategy, purification methods, formulation, COGS estimate

### 3. Monoclonal Antibody
Input: Adalimumab
Output: mAb production process, glycosylation considerations, downstream processing

### 4. Disease Research
Input: "Type 2 diabetes"
Output: Complete report with multiple treatments and their manufacturing analyses

## Performance Notes

- Single compound analysis: ~30-60 seconds (depends on LLM)
- Integrated analysis: ~2-5 minutes (multiple compounds, sequential LLM calls)
- IBM RXN calls: ~20-30 seconds per compound (when API available)

## Future Enhancements

1. Parallel LLM calls for batch processing
2. PubChem/ChEMBL integration for SMILES lookup
3. Cost estimation models
4. Patent landscape analysis
5. Supplier database integration
6. Regulatory database linkage
