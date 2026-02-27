"""RDKit Molecular Property Predictor Plugin.

Pure algorithmic plugin -- zero model loading required.
Uses RDKit descriptor calculators for molecular properties.
All computation runs on CPU via run_in_executor().
"""
import asyncio
from typing import Any

from app.services.plugins.base import BasePlugin


class PropertyPredictorPlugin(BasePlugin):

    @property
    def name(self) -> str:
        return "predict_properties"

    @property
    def description(self) -> str:
        return (
            "Calculate molecular properties (MW, LogP, TPSA, HBD, HBA, QED, "
            "Lipinski rule-of-five) from a SMILES string."
        )

    async def load(self) -> Any:
        """RDKit is pure Python/C++ -- no model to load."""
        return None

    async def execute(self, model: Any, **kwargs) -> dict:
        """Calculate molecular properties for a SMILES string.

        Args (in kwargs):
            smiles: str -- SMILES representation of the molecule.

        Returns:
            Dict with molecular descriptors and Lipinski check.
        """
        smiles = kwargs.get("smiles", "")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._compute, smiles)

    def _compute(self, smiles: str) -> dict:
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
            "smiles": smiles,
            "valid": True,
            "MolWt": round(mw, 2),
            "LogP": round(logp, 2),
            "TPSA": round(Descriptors.TPSA(mol), 2),
            "HBD": hbd,
            "HBA": hba,
            "NumRotatableBonds": Descriptors.NumRotatableBonds(mol),
            "RingCount": Descriptors.RingCount(mol),
            "QED": round(QEDModule.qed(mol), 4),
            "Lipinski": {
                "MW_ok": mw <= 500,
                "LogP_ok": logp <= 5,
                "HBD_ok": hbd <= 5,
                "HBA_ok": hba <= 10,
                "passes": all([mw <= 500, logp <= 5, hbd <= 5, hba <= 10]),
            },
        }

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "smiles": {
                    "type": "string",
                    "description": "SMILES representation of the molecule",
                }
            },
            "required": ["smiles"],
        }

    def output_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "valid": {"type": "boolean"},
                "MolWt": {"type": "number"},
                "LogP": {"type": "number"},
                "TPSA": {"type": "number"},
                "HBD": {"type": "integer"},
                "HBA": {"type": "integer"},
                "NumRotatableBonds": {"type": "integer"},
                "RingCount": {"type": "integer"},
                "QED": {"type": "number"},
            },
        }
