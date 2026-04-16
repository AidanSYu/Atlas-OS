"""Synthetic accessibility scoring plugin — fully self-contained, no app imports.

Computes SA Score (1-10, higher = harder) using RDKit SA_Score or heuristic fallback.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _heuristic_sa_score(smiles: str) -> float:
    length = len(smiles or "")
    if length <= 10:
        return 1.5
    if length <= 25:
        return 2.0 + (length - 10) / 30.0
    if length <= 50:
        return 3.5 + (length - 25) / 25.0
    if length <= 80:
        return 5.5 + (length - 50) / 30.0
    return min(10.0, 6.5 + (length - 80) / 20.0)


class ScoreSynthesizabilityWrapper:

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        smiles_list = args.get("smiles_list", [])
        if not isinstance(smiles_list, list):
            smiles_list = [smiles_list] if smiles_list else []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._score, smiles_list)

    @staticmethod
    def _score(smiles_list: List[str]) -> dict:
        scores: List[dict] = []
        use_sascorer = False
        try:
            from rdkit import Chem
            from rdkit.Contrib.SA_Score import sascorer
            use_sascorer = True
        except ImportError:
            logger.info("RDKit SA_Score not available; using heuristic.")

        for smi in smiles_list:
            smi = (smi or "").strip()
            if not smi:
                scores.append({"smiles": "", "sa_score": 5.0, "feasible": False})
                continue
            try:
                if use_sascorer:
                    mol = Chem.MolFromSmiles(smi)
                    sa = round(sascorer.calculateScore(mol), 2) if mol else round(_heuristic_sa_score(smi), 2)
                else:
                    sa = round(_heuristic_sa_score(smi), 2)
                scores.append({"smiles": smi, "sa_score": sa, "feasible": sa <= 6.0})
            except Exception as e:
                logger.exception("Error scoring SMILES %r: %s", smi, e)
                sa = round(_heuristic_sa_score(smi), 2)
                scores.append({"smiles": smi, "sa_score": sa, "feasible": sa <= 6.0})

        feasible_count = sum(1 for s in scores if s.get("feasible"))
        return {
            "scores": scores,
            "summary": f"SA scores for {len(scores)} molecules: {feasible_count} feasible (SA <= 6), {len(scores) - feasible_count} infeasible.",
        }


PLUGIN = ScoreSynthesizabilityWrapper()
