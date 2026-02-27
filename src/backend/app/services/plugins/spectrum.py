"""NMR Spectrum Verifier Plugin.

Reads JCAMP-DX (.jdx) NMR files via nmrglue, detects peaks via
scipy.signal.find_peaks, and optionally compares observed peak count
against expected hydrogen count from an RDKit SMILES structure.

All computation runs on CPU via run_in_executor().
"""
import asyncio
import os
from typing import Any, Dict, List, Optional

from app.services.plugins.base import BasePlugin


class SpectrumVerifierPlugin(BasePlugin):

    @property
    def name(self) -> str:
        return "verify_spectrum"

    @property
    def description(self) -> str:
        return (
            "Verify an NMR spectrum (.jdx file) against a molecular structure. "
            "Returns observed peaks, match score, and metadata. "
            "Required: file_path. Optional: smiles (for structure comparison), tolerance (ppm, default 0.05)."
        )

    async def load(self) -> Any:
        return None

    async def execute(self, model: Any, **kwargs) -> dict:
        file_path = kwargs.get("file_path", "")
        smiles = kwargs.get("smiles", "")
        tolerance = kwargs.get("tolerance", 0.05)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._compute, file_path, smiles, tolerance
        )

    def _compute(
        self, file_path: str, smiles: str, tolerance: float
    ) -> dict:
        if not file_path or not os.path.isfile(file_path):
            return {
                "file": file_path,
                "valid": False,
                "error": f"File not found or empty path: {file_path}",
            }

        try:
            import nmrglue
        except ImportError:
            return {"valid": False, "error": "nmrglue is not installed"}

        try:
            from scipy.signal import find_peaks
            import numpy as np
        except ImportError:
            return {"valid": False, "error": "scipy is not installed"}

        # Read JCAMP-DX file
        try:
            dic, data = nmrglue.jcampdx.read(file_path)
        except Exception as e:
            return {
                "file": os.path.basename(file_path),
                "valid": False,
                "error": f"Failed to read .jdx file: {e}",
            }

        # Handle complex data (take real part)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        data = np.asarray(data, dtype=float)
        if data.ndim != 1:
            return {
                "file": os.path.basename(file_path),
                "valid": False,
                "error": f"Expected 1D data, got {data.ndim}D",
            }

        # Extract chemical shift axis from metadata
        metadata = self._extract_metadata(dic)
        n_points = len(data)
        first_x = metadata.get("first_x")
        last_x = metadata.get("last_x")

        if first_x is not None and last_x is not None and n_points > 1:
            ppm_axis = np.linspace(first_x, last_x, n_points)
        else:
            ppm_axis = np.arange(n_points, dtype=float)

        # Peak detection
        data_norm = data / (np.max(np.abs(data)) or 1.0)
        prominence = 0.05
        distance = max(1, n_points // 200)
        peak_indices, properties = find_peaks(
            data_norm, prominence=prominence, distance=distance
        )

        observed_peaks: List[Dict[str, Any]] = []
        for idx in peak_indices:
            observed_peaks.append({
                "ppm": round(float(ppm_axis[idx]), 4),
                "intensity": round(float(data_norm[idx]), 4),
            })

        # Sort peaks by ppm descending (standard NMR convention)
        observed_peaks.sort(key=lambda p: p["ppm"], reverse=True)

        # Optional: compare against SMILES hydrogen count
        expected_h_count: Optional[int] = None
        match_score: Optional[float] = None
        if smiles:
            expected_h_count = self._get_hydrogen_count(smiles)
            if expected_h_count is not None and expected_h_count > 0:
                ratio = len(observed_peaks) / expected_h_count
                match_score = round(max(0.0, 1.0 - abs(1.0 - ratio)), 4)

        return {
            "file": os.path.basename(file_path),
            "valid": True,
            "smiles": smiles or None,
            "observed_peaks": observed_peaks[:50],
            "peak_count": len(observed_peaks),
            "expected_h_count": expected_h_count,
            "match_score": match_score,
            "metadata": metadata,
        }

    @staticmethod
    def _extract_metadata(dic: dict) -> dict:
        """Pull relevant NMR metadata from the JCAMP-DX header dict."""
        def _get(key: str):
            for k, v in dic.items():
                if k.upper().replace(" ", "").replace("_", "") == key.upper().replace(" ", "").replace("_", ""):
                    return v
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        if k2.upper().replace(" ", "").replace("_", "") == key.upper():
                            return v2
            return None

        def _float(val):
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return {
            "nucleus": _get("NUCLIDE") or _get(".OBSERVENUCLEUS") or _get("NUC1"),
            "frequency": _float(_get("OBSERVEFREQUENCY") or _get(".OBSERVEFREQUENCY")),
            "solvent": _get("SOLVENTNAME") or _get(".SOLVENTNAME"),
            "first_x": _float(_get("FIRSTX")),
            "last_x": _float(_get("LASTX")),
            "n_points": _float(_get("NPOINTS")),
            "title": _get("TITLE"),
        }

    @staticmethod
    def _get_hydrogen_count(smiles: str) -> Optional[int]:
        """Use RDKit to count total hydrogens (implicit + explicit)."""
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None
            mol_h = Chem.AddHs(mol)
            return sum(1 for atom in mol_h.GetAtoms() if atom.GetAtomicNum() == 1)
        except Exception:
            return None

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the .jdx NMR data file",
                },
                "smiles": {
                    "type": "string",
                    "description": "SMILES string of the expected molecule (optional)",
                },
                "tolerance": {
                    "type": "number",
                    "description": "Peak matching tolerance in ppm (default 0.05)",
                },
            },
            "required": ["file_path"],
        }

    def output_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "valid": {"type": "boolean"},
                "smiles": {"type": "string"},
                "observed_peaks": {"type": "array"},
                "peak_count": {"type": "integer"},
                "expected_h_count": {"type": "integer"},
                "match_score": {"type": "number"},
                "metadata": {"type": "object"},
            },
        }
