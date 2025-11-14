import requests
import re
from typing import Dict, List, Any
from .retrosynthesis import FreeRetrosynthesisEngine


class SynthesisManufacturerAgent:
    """
    Agent for analyzing manufacturability and synthesis routes for drug candidates.
    Handles small molecules (retrosynthesis) and biologics (protein/antibody synthesis).
    Can integrate with IBM RXN API or use local LLM for synthesis planning.
    """
    
    def __init__(self, ibm_rxn_api_key: str = None, use_free_retrosynthesis: bool = True):
        self.ibm_rxn_api_key = ibm_rxn_api_key
        self.ibm_rxn_base_url = "https://rxn.res.ibm.com/rxn/api/api/v1"
        self.use_free_retrosynthesis = use_free_retrosynthesis
        self.free_retro_engine = FreeRetrosynthesisEngine() if use_free_retrosynthesis else None
    
    def _local_llm(self, prompt: str) -> str:
        """Use local Ollama for synthesis planning."""
        try:
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": "mistral",
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "ConnectTimeout" in error_msg:
                raise RuntimeError(
                    "Ollama is not running. Please start it:\n"
                    "1. Install: brew install ollama (or https://ollama.ai)\n"
                    "2. Pull model: ollama pull mistral\n"
                    "3. Start server: ollama serve"
                )
            elif "Read timed out" in error_msg:
                raise RuntimeError(
                    "Ollama request timed out. The model may be taking too long.\n"
                    "Try a smaller/faster model: ollama pull llama2:7b"
                )
            else:
                raise RuntimeError(f"Ollama error: {error_msg}")
    
    def _classify_molecule_type(self, compound_name: str) -> str:
        """Classify if compound is small molecule, protein, antibody, etc."""
        compound_lower = compound_name.lower()
        
        # Check for biologics indicators
        if any(term in compound_lower for term in ["mab", "antibody", "immunoglobulin", "-ximab", "-zumab", "-mumab"]):
            return "monoclonal_antibody"
        elif any(term in compound_lower for term in ["protein", "peptide", "insulin", "enzyme", "growth factor"]):
            return "protein_peptide"
        elif any(term in compound_lower for term in ["vaccine", "viral vector", "gene therapy"]):
            return "biologic_other"
        elif any(term in compound_lower for term in ["rna", "mrna", "sirna"]):
            return "nucleic_acid"
        else:
            return "small_molecule"
    
    def _ibm_rxn_retrosynthesis(self, smiles: str) -> Dict[str, Any]:
        """
        Call IBM RXN API for retrosynthesis (if API key available).
        Returns synthesis routes and steps.
        """
        if not self.ibm_rxn_api_key:
            return {"error": "IBM RXN API key not configured", "routes": []}
        
        try:
            headers = {
                "Authorization": f"Bearer {self.ibm_rxn_api_key}",
                "Content-Type": "application/json"
            }
            
            # Start retrosynthesis prediction
            predict_url = f"{self.ibm_rxn_base_url}/retrosynthesis"
            payload = {
                "product": smiles,
                "availability_pricing_threshold": 0,
                "available_smiles": None,
                "exclude_smiles": None,
                "exclude_substructures": None,
                "exclude_target_molecule": False,
                "fap": 0.6,
                "max_steps": 6,
                "nbeams": 10,
                "pruning_steps": 2
            }
            
            response = requests.post(predict_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            prediction_id = response.json().get("prediction_id")
            
            # Poll for results
            result_url = f"{self.ibm_rxn_base_url}/retrosynthesis/{prediction_id}"
            for _ in range(10):
                import time
                time.sleep(2)
                result_response = requests.get(result_url, headers=headers, timeout=30)
                result_data = result_response.json()
                
                if result_data.get("status") == "SUCCESS":
                    return {"routes": result_data.get("retrosynthetic_paths", []), "error": None}
            
            return {"error": "IBM RXN prediction timed out", "routes": []}
            
        except Exception as e:
            return {"error": f"IBM RXN API error: {str(e)}", "routes": []}
    
    def _llm_retrosynthesis(self, compound_name: str, smiles: str = None) -> Dict[str, Any]:
        """Use enhanced free retrosynthesis engine or basic LLM."""
        
        # Use FREE retrosynthesis engine if available (RDKit + LLM)
        if self.free_retro_engine and smiles:
            retro_analysis = self.free_retro_engine.retrosynthesis_analysis(compound_name, smiles)
            return {
                "method": "free_retrosynthesis_engine",
                "molecular_properties": retro_analysis.get("molecular_properties", {}),
                "functional_groups": retro_analysis.get("functional_groups", []),
                "strategic_disconnections": retro_analysis.get("strategic_disconnections", []),
                "retrosynthetic_routes": retro_analysis.get("retrosynthetic_routes", ""),
                "forward_synthesis": retro_analysis.get("forward_synthesis", ""),
                "commercial_availability": retro_analysis.get("commercial_availability", ""),
                "analysis": f"""
**Molecular Properties**
{retro_analysis.get('molecular_properties', {})}

**Functional Groups**
{', '.join(retro_analysis.get('functional_groups', []))}

**Retrosynthetic Routes**
{retro_analysis.get('retrosynthetic_routes', '')}

**Forward Synthesis Protocol**
{retro_analysis.get('forward_synthesis', '')}

**Commercial Availability**
{retro_analysis.get('commercial_availability', '')}
"""
            }
        
        # Fallback to basic LLM if no SMILES or engine not available
        smiles_info = f" (SMILES: {smiles})" if smiles else ""
        
        prompt = f"""You are an expert synthetic organic chemist. Provide a detailed retrosynthetic analysis for: {compound_name}{smiles_info}

Provide:
1. Retrosynthetic Analysis: Break down the target into key fragments and disconnections
2. Forward Synthesis Route (3-5 steps): Specific reactions with reagents and conditions
3. Key Challenges: Potential issues (stereochemistry, functional group compatibility, yield)
4. Starting Materials: Commercially available precursors
5. Estimated Overall Yield: Approximate percentage
6. Scale-Up Considerations: What changes needed for kg-scale production

Format as structured sections."""

        response = self._local_llm(prompt)
        return {"analysis": response, "method": "llm_basic"}
    
    def _llm_protein_synthesis(self, compound_name: str) -> Dict[str, Any]:
        """Use local LLM for protein/peptide synthesis planning."""
        
        prompt = f"""You are an expert in biopharmaceutical manufacturing. Provide detailed synthesis strategy for: {compound_name}

Provide:
1. Expression System: Recommended host (E. coli, CHO, yeast, etc.) and rationale
2. Production Process: Key steps (transformation, fermentation, purification)
3. Purification Strategy: Chromatography methods, yield expectations
4. Post-Translational Modifications: If needed (glycosylation, phosphorylation)
5. Quality Control: Critical quality attributes to monitor
6. Scale-Up Path: Lab scale to commercial production considerations
7. Formulation: Stability, excipients, delivery considerations
8. Estimated Cost of Goods: Rough $/gram at commercial scale

Format as structured sections with specific technical details."""

        response = self._local_llm(prompt)
        return {"analysis": response, "method": "biologic_production"}
    
    def _assess_manufacturability(self, compound_name: str, molecule_type: str, synthesis_data: Dict) -> Dict[str, Any]:
        """Assess manufacturability based on molecule type and synthesis complexity."""
        
        prompt = f"""You are a pharmaceutical manufacturing expert. Assess manufacturability for:

Compound: {compound_name}
Type: {molecule_type}
Synthesis Analysis: {str(synthesis_data.get('analysis', ''))[:2000]}

Provide:
1. Manufacturability Score: 0-100 (100 = highly manufacturable)
2. Critical Risk Factors: Top 3-5 risks for commercial production
3. Regulatory Considerations: Key regulatory hurdles (CMC, stability)
4. Cost Drivers: Main factors affecting production cost
5. Timeline Estimate: Research → Phase I → Commercial production
6. Recommendations: Specific actions to improve manufacturability

Be specific and technical. Consider scale, cost, complexity, regulatory path."""

        assessment = self._local_llm(prompt)
        
        # Extract score if possible
        score_match = re.search(r'score[:\s]+(\d+)', assessment.lower())
        score = int(score_match.group(1)) if score_match else 70
        
        return {
            "manufacturability_score": score,
            "assessment": assessment,
            "molecule_type": molecule_type
        }
    
    def analyze_compound(self, compound_name: str, smiles: str = None, researcher_context: str = None) -> Dict[str, Any]:
        """
        Main entry point: Analyze a compound for synthesis and manufacturability.
        
        Args:
            compound_name: Name of the compound/drug
            smiles: SMILES string (optional, for small molecules)
            researcher_context: Additional context from researcher agent
        
        Returns:
            Complete analysis with synthesis routes and manufacturability assessment
        """
        
        # Classify molecule type
        molecule_type = self._classify_molecule_type(compound_name)
        
        result = {
            "compound_name": compound_name,
            "molecule_type": molecule_type,
            "smiles": smiles,
            "synthesis_analysis": {},
            "manufacturability": {},
            "integrated_summary": ""
        }
        
        # Get synthesis analysis based on type
        if molecule_type == "small_molecule":
            # Try IBM RXN first if available, fallback to LLM
            if smiles and self.ibm_rxn_api_key:
                ibm_result = self._ibm_rxn_retrosynthesis(smiles)
                if not ibm_result.get("error"):
                    result["synthesis_analysis"] = {
                        "method": "ibm_rxn",
                        "routes": ibm_result["routes"]
                    }
                else:
                    result["synthesis_analysis"] = self._llm_retrosynthesis(compound_name, smiles)
            else:
                result["synthesis_analysis"] = self._llm_retrosynthesis(compound_name, smiles)
        
        elif molecule_type in ["protein_peptide", "monoclonal_antibody", "nucleic_acid"]:
            result["synthesis_analysis"] = self._llm_protein_synthesis(compound_name)
        
        else:  # biologic_other
            result["synthesis_analysis"] = self._llm_protein_synthesis(compound_name)
        
        # Assess manufacturability
        result["manufacturability"] = self._assess_manufacturability(
            compound_name, 
            molecule_type, 
            result["synthesis_analysis"]
        )
        
        # Generate integrated summary
        summary_prompt = f"""Provide a 3-4 sentence executive summary for manufacturing readiness of {compound_name}.

Synthesis approach: {result['synthesis_analysis'].get('method', 'N/A')}
Manufacturability score: {result['manufacturability'].get('manufacturability_score', 'N/A')}
Type: {molecule_type}

Focus on: feasibility, timeline, major challenges, recommendation."""

        result["integrated_summary"] = self._local_llm(summary_prompt)
        
        return result
    
    def batch_analyze_from_research(self, research_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze multiple compounds identified in researcher agent results.
        
        Args:
            research_results: Output from ResearcherAgent.research_disease()
        
        Returns:
            List of analysis results for each identified compound
        """
        
        # Extract compound names from research summary using LLM
        extract_prompt = f"""From the following research summary, extract a list of specific drug compounds or therapeutic molecules mentioned. 
Return ONLY the compound names, one per line, no numbering or extra text.

Research Summary:
{research_results.get('summary', '')[:3000]}"""

        compounds_text = self._local_llm(extract_prompt)
        
        # Parse compound names
        compound_lines = [line.strip() for line in compounds_text.split('\n') if line.strip() and len(line.strip()) > 3]
        compounds = compound_lines[:5]  # Limit to top 5 compounds
        
        if not compounds:
            return []
        
        # Analyze each compound
        analyses = []
        for compound in compounds:
            analysis = self.analyze_compound(
                compound_name=compound,
                researcher_context=research_results.get('summary', '')[:1000]
            )
            analyses.append(analysis)
        
        return analyses
