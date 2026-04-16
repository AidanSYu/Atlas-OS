"""Toxicity screening plugin — fully self-contained, no app imports.

Uses SMARTS pattern matching for structural alerts and RDKit PAINS FilterCatalog.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STRUCTURAL_ALERTS: Dict[str, str] = {
    "michael_acceptor": "[CH2]=[CH][C,S,N]=O",
    "epoxide": "C1OC1",
    "aldehyde": "[CH1](=O)",
    "azide": "[N-]=[N+]=[N-]",
    "acyl_halide": "[CX3](=[OX1])[F,Cl,Br,I]",
    "sulfonyl_halide": "[SX4](=[OX1])(=[OX1])[F,Cl,Br,I]",
    "nitro_aromatic": "c[N+](=O)[O-]",
    "aniline": "c1ccccc1[NH2]",
    "polyhalogenated": "[#6]([F,Cl,Br,I])([F,Cl,Br,I])[F,Cl,Br,I]",
}


class CheckToxicityWrapper:

    def __init__(self):
        self._compiled: Optional[Dict[str, Any]] = None

    def _ensure_compiled(self) -> dict:
        if self._compiled is not None:
            return self._compiled
        from rdkit import Chem
        compiled = {}
        for alert_name, smarts in STRUCTURAL_ALERTS.items():
            pat = Chem.MolFromSmarts(smarts)
            if pat is not None:
                compiled[alert_name] = pat
        self._compiled = compiled
        return compiled

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        smiles_list = args.get("smiles_list")
        if smiles_list and isinstance(smiles_list, list):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._check_batch, smiles_list)
        smiles = args.get("smiles", "")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._check_single, smiles)

    def _check_batch(self, smiles_list: list) -> dict:
        results = [self._check_single(smi) for smi in smiles_list if (smi or "").strip()]
        clean_count = sum(1 for r in results if r.get("clean"))
        return {
            "toxicity_results": results,
            "summary": f"Toxicity check: {clean_count} clean, {len(results) - clean_count} flagged.",
        }

    def _check_single(self, smiles: str) -> dict:
        from rdkit import Chem
        from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"smiles": smiles, "valid": False, "error": "Invalid SMILES string"}

        compiled = self._ensure_compiled()
        alerts: List[Dict[str, str]] = []
        for alert_name, pattern in compiled.items():
            if mol.HasSubstructMatch(pattern):
                alerts.append({"name": alert_name, "smarts": STRUCTURAL_ALERTS[alert_name]})

        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog(params)
        pains_entry = catalog.GetFirstMatch(mol)
        pains_hits = 1 if pains_entry else 0
        pains_description = pains_entry.GetDescription() if pains_entry else None

        return {
            "smiles": smiles, "valid": True,
            "structural_alerts": alerts, "alert_count": len(alerts),
            "pains_hits": pains_hits, "pains_description": pains_description,
            "clean": len(alerts) == 0 and pains_hits == 0,
        }


PLUGIN = CheckToxicityWrapper()
