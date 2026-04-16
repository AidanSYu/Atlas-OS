"""Fragment enumeration plugin — fully self-contained, no app imports.

Combinatorial fragment assembly: takes a scaffold template with an {attachment}
slot and a list of fragment SMILES, produces every valid combination.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

SCAFFOLD_PRESETS: Dict[str, dict] = {
    "xyloside": {
        "description": "beta-D-xylopyranoside O-linked glycosides (GAG priming)",
        "template": "OC[C@H]1O[C@@H]({attachment})[C@@H](O)[C@H](O)[C@H]1O",
        "fragments": [
            ("phenyl", "Oc1ccccc1"),
            ("4-methylphenyl", "Oc1ccc(C)cc1"),
            ("4-methoxyphenyl", "Oc1ccc(OC)cc1"),
            ("4-fluorophenyl", "Oc1ccc(F)cc1"),
            ("4-chlorophenyl", "Oc1ccc(Cl)cc1"),
            ("3-methoxyphenyl", "Oc1cccc(OC)c1"),
            ("3,4-dimethoxyphenyl", "Oc1ccc(OC)c(OC)c1"),
            ("2-naphthyl", "Oc1ccc2ccccc2c1"),
            ("1-naphthyl", "Oc1cccc2ccccc12"),
            ("4-hydroxymethylphenyl", "Oc1ccc(CO)cc1"),
            ("4-carboxyphenyl", "Oc1ccc(C(=O)O)cc1"),
            ("4-acetylphenyl", "Oc1ccc(C(C)=O)cc1"),
            ("3-hydroxyphenyl", "Oc1cccc(O)c1"),
            ("benzofuran-5-yl", "Oc1ccc2occc2c1"),
            ("5-indanyl", "Oc1ccc2CCCc2c1"),
            ("biphenyl-4-yl", "Oc1ccc(-c2ccccc2)cc1"),
            ("7-methylcoumarin-4-yl", "Oc1cc(=O)oc2cc(C)ccc12"),
            ("benzyl", "OCc1ccccc1"),
            ("4-methylbenzyl", "OCc1ccc(C)cc1"),
            ("4-methoxybenzyl", "OCc1ccc(OC)cc1"),
        ],
    },
}


class EnumerateFragmentsWrapper:

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        scaffold_name = args.get("scaffold_name")
        custom_template = args.get("template")
        custom_fragments = args.get("fragments", [])
        max_candidates = int(args.get("max_candidates", 25))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._enumerate, scaffold_name, custom_template, custom_fragments, max_candidates
        )

    @staticmethod
    def _enumerate(scaffold_name, custom_template, custom_fragments, max_candidates) -> dict:
        preset_label = "custom"
        if scaffold_name and scaffold_name in SCAFFOLD_PRESETS:
            preset = SCAFFOLD_PRESETS[scaffold_name]
            template = preset["template"]
            fragments = preset["fragments"]
            preset_label = scaffold_name
        elif custom_template:
            template = custom_template
            fragments = []
            for f in custom_fragments:
                if isinstance(f, (list, tuple)) and len(f) == 2:
                    fragments.append((str(f[0]), str(f[1])))
                elif isinstance(f, str):
                    fragments.append((f[:20], f))
        else:
            return {"molecules": [], "smiles_list": [],
                    "summary": "No scaffold specified. Provide scaffold_name or template + fragments."}

        try:
            from rdkit import Chem
            rdkit_available = True
        except ImportError:
            rdkit_available = False

        molecules: List[dict] = []
        seen_keys: set = set()

        for name, frag_smiles in fragments:
            if len(molecules) >= max_candidates:
                break
            try:
                raw_smiles = template.format(attachment=frag_smiles)
                if rdkit_available:
                    mol = Chem.MolFromSmiles(raw_smiles)
                    if mol is None:
                        continue
                    canonical = Chem.MolToSmiles(mol, canonical=True)
                    try:
                        inchikey = Chem.MolToInchiKey(mol)
                    except Exception:
                        inchikey = ""
                    if inchikey and inchikey in seen_keys:
                        continue
                    if inchikey:
                        seen_keys.add(inchikey)
                else:
                    canonical = raw_smiles
                    inchikey = ""

                molecules.append({
                    "smiles": canonical, "compound_id": f"ATLAS-{uuid4().hex[:8].upper()}",
                    "inchikey": inchikey, "valid": True,
                    "source": "fragment_enumeration", "name": f"{name} ({preset_label})",
                })
            except Exception:
                pass

        return {
            "molecules": molecules,
            "smiles_list": [m["smiles"] for m in molecules],
            "summary": f"Generated {len(molecules)} candidates from {len(fragments)} fragments (preset: {preset_label}).",
        }


PLUGIN = EnumerateFragmentsWrapper()
