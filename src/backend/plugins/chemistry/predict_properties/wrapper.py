"""Molecular property prediction plugin — fully self-contained, no app imports.

Uses RDKit descriptor calculators for MW, LogP, TPSA, HBD, HBA, QED, Lipinski.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PredictPropertiesWrapper:

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        smiles_list = args.get("smiles_list")
        if smiles_list and isinstance(smiles_list, list):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._compute_batch, smiles_list)
        smiles = args.get("smiles", "")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._compute, smiles)

    def _compute_batch(self, smiles_list: list) -> dict:
        results = [self._compute(smi) for smi in smiles_list if (smi or "").strip()]
        valid_count = sum(1 for r in results if r.get("valid"))
        return {
            "properties": results,
            "summary": f"Properties computed for {valid_count}/{len(results)} molecules.",
        }

    @staticmethod
    def _compute(smiles: str) -> dict:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, QED as QEDModule

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"smiles": smiles, "valid": False, "error": "Invalid SMILES string"}

        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)

        return {
            "smiles": smiles, "valid": True,
            "MolWt": round(mw, 2), "LogP": round(logp, 2),
            "TPSA": round(Descriptors.TPSA(mol), 2),
            "HBD": hbd, "HBA": hba,
            "NumRotatableBonds": Descriptors.NumRotatableBonds(mol),
            "RingCount": Descriptors.RingCount(mol),
            "QED": round(QEDModule.qed(mol), 4),
            "Lipinski": {
                "MW_ok": mw <= 500, "LogP_ok": logp <= 5,
                "HBD_ok": hbd <= 5, "HBA_ok": hba <= 10,
                "passes": all([mw <= 500, logp <= 5, hbd <= 5, hba <= 10]),
            },
        }


PLUGIN = PredictPropertiesWrapper()
