"""
Retrosynthesis Engine
Uses RDKit + LLM to provide retrosynthesis analysis
"""

import requests
from typing import Dict, List, Any, Optional
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False


class RetrosynthesisEngine:
    """
    Open-source retrosynthesis engine using RDKit + LLM.
    Provides IBM RXN-like capabilities without needing paid API.
    """
    
    def __init__(self):
        self.common_reactions = self._load_reaction_templates()
    
    def _load_reaction_templates(self) -> List[Dict[str, str]]:
        """Common organic chemistry reaction templates."""
        return [
            {
                "name": "Ester Hydrolysis",
                "smarts": "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[OH].[OH][C:4]",
                "description": "Break ester to carboxylic acid + alcohol"
            },
            {
                "name": "Amide Formation",
                "smarts": "[C:1](=[O:2])[N:3]>>[C:1](=[O:2])[OH].[NH2:3]",
                "description": "Break amide to carboxylic acid + amine"
            },
            {
                "name": "Grignard Addition",
                "smarts": "[C:1]([OH:2])([C:3])[C:4]>>[C:1]=[O:2].[MgBr][C:4]",
                "description": "Disconnect alcohol to ketone + Grignard"
            },
            {
                "name": "Aldol Condensation",
                "smarts": "[C:1]=[C:2][C:3](=[O:4])[C:5]>>[C:1]=[O].[C:3](=[O:4])[C:5]",
                "description": "Disconnect α,β-unsaturated carbonyl"
            },
            {
                "name": "Wittig Reaction",
                "smarts": "[C:1]=[C:2]>>[C:1]=[O].[C:2]",
                "description": "Disconnect alkene to carbonyl + ylide"
            },
            {
                "name": "SN2 Substitution",
                "smarts": "[C:1][N,O,S:2]>>[C:1][Br,Cl,I].[N,O,S:2]",
                "description": "Disconnect C-heteroatom bond"
            },
            {
                "name": "Friedel-Crafts",
                "smarts": "[c:1][C:2]>>[c:1][H].[C:2]",
                "description": "Disconnect aromatic C-C bond"
            },
            {
                "name": "Reductive Amination",
                "smarts": "[C:1][NH:2][C:3]>>[C:1]=[O].[NH2:2][C:3]",
                "description": "Disconnect C-N to carbonyl + amine"
            }
        ]
    
    def _local_llm(self, prompt: str, timeout: int = 180) -> str:
        """Call local Ollama LLM."""
        try:
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": "mistral",
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            return f"[LLM unavailable: {e}]"
    
    def _analyze_molecule(self, smiles: str) -> Dict[str, Any]:
        """Analyze molecular properties using RDKit."""
        if not RDKIT_AVAILABLE or not smiles:
            return {"error": "RDKit not available or invalid SMILES"}
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return {"error": "Invalid SMILES structure"}
            
            return {
                "molecular_weight": Descriptors.MolWt(mol),
                "logp": Descriptors.MolLogP(mol),
                "h_bond_donors": Descriptors.NumHDonors(mol),
                "h_bond_acceptors": Descriptors.NumHAcceptors(mol),
                "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
                "aromatic_rings": Descriptors.NumAromaticRings(mol),
                "num_atoms": mol.GetNumAtoms(),
                "num_heavy_atoms": mol.GetNumHeavyAtoms(),
                "complexity_score": self._calculate_complexity(mol)
            }
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def _calculate_complexity(self, mol) -> float:
        """Calculate synthetic complexity score (0-100)."""
        # Higher = more complex
        score = 0
        score += mol.GetNumHeavyAtoms() * 2  # More atoms = more complex
        score += Descriptors.NumRotatableBonds(mol) * 3  # Flexibility
        score += Descriptors.NumAromaticRings(mol) * 5  # Aromatic systems
        score += len([a for a in mol.GetAtoms() if a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED]) * 10  # Stereocenters
        
        # Normalize to 0-100
        return min(score, 100)
    
    def _identify_functional_groups(self, smiles: str) -> List[str]:
        """Identify key functional groups in molecule."""
        if not RDKIT_AVAILABLE or not smiles:
            return []
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return []
            
            functional_groups = []
            
            # Common functional group SMARTS patterns
            patterns = {
                "Carboxylic Acid": "C(=O)[OH]",
                "Ester": "C(=O)O[C]",
                "Amide": "C(=O)N",
                "Amine": "[NH2,NH1,NH0]",
                "Alcohol": "[OH]",
                "Ketone": "[C]C(=O)[C]",
                "Aldehyde": "[CH](=O)",
                "Ether": "[C]O[C]",
                "Nitro": "N(=O)=O",
                "Halide": "[F,Cl,Br,I]",
                "Aromatic": "c",
                "Alkene": "C=C",
                "Alkyne": "C#C"
            }
            
            for name, smarts in patterns.items():
                pattern = Chem.MolFromSmarts(smarts)
                if pattern and mol.HasSubstructMatch(pattern):
                    functional_groups.append(name)
            
            return functional_groups
        except Exception:
            return []
    
    def _suggest_disconnections(self, smiles: str) -> List[Dict[str, str]]:
        """Suggest strategic bond disconnections using reaction templates."""
        if not RDKIT_AVAILABLE or not smiles:
            return []
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return []
            
            suggestions = []
            
            for rxn_template in self.common_reactions:
                try:
                    rxn = AllChem.ReactionFromSmarts(rxn_template["smarts"])
                    if rxn:
                        products = rxn.RunReactants((mol,))
                        if products:
                            suggestions.append({
                                "reaction": rxn_template["name"],
                                "description": rxn_template["description"],
                                "precursors": len(products[0])
                            })
                except Exception:
                    continue
            
            return suggestions[:5]  # Top 5 suggestions
        except Exception:
            return []
    
    def retrosynthesis_analysis(self, compound_name: str, smiles: str = None) -> Dict[str, Any]:
        """
        Perform comprehensive retrosynthesis analysis.
        This is the free alternative to IBM RXN.
        """
        
        result = {
            "compound_name": compound_name,
            "smiles": smiles,
            "molecular_properties": {},
            "functional_groups": [],
            "strategic_disconnections": [],
            "retrosynthetic_routes": [],
            "forward_synthesis": "",
            "complexity_assessment": "",
            "commercial_availability": ""
        }
        
        # Step 1: Analyze molecular properties
        if smiles:
            result["molecular_properties"] = self._analyze_molecule(smiles)
            result["functional_groups"] = self._identify_functional_groups(smiles)
            result["strategic_disconnections"] = self._suggest_disconnections(smiles)
        
        # Step 2: Generate retrosynthetic analysis with LLM
        properties_text = ""
        if result["molecular_properties"]:
            props = result["molecular_properties"]
            properties_text = f"""
Molecular Properties:
- MW: {props.get('molecular_weight', 'N/A'):.2f} g/mol
- LogP: {props.get('logp', 'N/A'):.2f}
- H-bond donors: {props.get('h_bond_donors', 'N/A')}
- H-bond acceptors: {props.get('h_bond_acceptors', 'N/A')}
- Aromatic rings: {props.get('aromatic_rings', 'N/A')}
- Complexity score: {props.get('complexity_score', 'N/A'):.1f}/100
"""
        
        functional_groups_text = ""
        if result["functional_groups"]:
            functional_groups_text = f"\nFunctional Groups Present: {', '.join(result['functional_groups'])}"
        
        disconnections_text = ""
        if result["strategic_disconnections"]:
            disconnections_text = "\nPossible Disconnections:\n"
            for disc in result["strategic_disconnections"]:
                disconnections_text += f"- {disc['reaction']}: {disc['description']}\n"
        
        retro_prompt = f"""You are an expert synthetic organic chemist. Provide detailed retrosynthetic analysis for: {compound_name}
{f"SMILES: {smiles}" if smiles else ""}
{properties_text}
{functional_groups_text}
{disconnections_text}

Provide THREE different retrosynthetic routes with the following structure:

**ROUTE 1: [Name the strategy, e.g., "Convergent Synthesis"]**
Key Disconnection: [Main strategic bond to break]
Retrosynthetic Steps:
1. [First disconnection and logic]
2. [Second disconnection]
3. [Continue until commercially available starting materials]

Starting Materials: [List 2-4 commercially available compounds]
Estimated Steps: [Number]
Expected Yield: [Percentage]
Key Challenges: [1-2 main issues]

**ROUTE 2: [Alternative strategy]**
[Same structure as Route 1]

**ROUTE 3: [Third strategy]**
[Same structure as Route 1]

Then provide:
**RECOMMENDED ROUTE:** [Which one and why]
**COMPLEXITY ASSESSMENT:** [Easy/Moderate/Difficult and rationale]

Be specific about reagents, conditions, and protecting groups where relevant."""

        retro_analysis = self._local_llm(retro_prompt)
        result["retrosynthetic_routes"] = retro_analysis
        
        # Step 3: Generate forward synthesis for best route
        forward_prompt = f"""Based on your retrosynthetic analysis for {compound_name}, provide a detailed FORWARD synthesis protocol for the recommended route.

Format as:

**Step 1: [Reaction name]**
Starting materials: [Specific compounds with quantities]
Reagents: [Specific reagents, solvents, catalysts]
Conditions: [Temperature, time, atmosphere]
Workup: [How to isolate product]
Expected yield: [Percentage]
Characterization: [Key NMR signals, MS, IR]

**Step 2: [Next reaction]**
[Same format]

Continue for all steps.

Include:
- Specific protecting group strategies if needed
- Purification methods (column chromatography, recrystallization, etc.)
- Critical safety considerations
- Scale-up considerations for each step"""

        forward_synthesis = self._local_llm(forward_prompt, timeout=240)
        result["forward_synthesis"] = forward_synthesis
        
        # Step 4: Commercial availability assessment
        if smiles:
            availability_prompt = f"""For the synthesis of {compound_name} (SMILES: {smiles}), assess:

1. Which starting materials in the proposed routes are commercially available from major suppliers (Sigma-Aldrich, TCI, Alfa Aesar)?
2. Estimated cost per gram for key starting materials (order of magnitude: $, $$, $$$, $$$$)
3. Which intermediates might need to be synthesized in-house vs purchased?
4. Overall commercial feasibility score (0-100)

Provide a brief practical assessment."""

            availability = self._local_llm(availability_prompt)
            result["commercial_availability"] = availability
        
        return result
    
    def compare_routes(self, routes_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compare multiple synthetic routes and recommend best one."""
        
        prompt = f"""You are a pharmaceutical process chemist. Analyze these synthetic routes and provide:

Routes Data:
{str(routes_data)[:2000]}

Provide:
1. **Route Comparison Table**: Rank routes by: (a) Step count (b) Overall yield (c) Cost (d) Complexity
2. **Recommended Route**: Which one for process development and why
3. **Key Optimization Opportunities**: Top 3 steps that need improvement
4. **Scale-Up Risks**: Main challenges going from lab to pilot to commercial scale
5. **Timeline Estimate**: Lab development → Process optimization → Commercial production

Be quantitative and specific."""

        comparison = self._local_llm(prompt, timeout=180)
        
        return {
            "comparison_analysis": comparison,
            "routes_analyzed": routes_data.get("compound_name", "Unknown")
        }
