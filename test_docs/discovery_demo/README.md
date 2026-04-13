# Discovery Demo Corpus: Xyloside GAG Primers

Upload the `.txt` files in this folder to a project, then start a Discovery session.

## Demo Prompts (pick one)

**Prompt 1 (recommended - triggers full pipeline):**
> Discover novel xyloside-based GAG primers for anti-fibrotic applications. Use the prior campaign data to avoid known liabilities, prioritize CS-selective scaffolds, and rank by a composite of safety, drug-likeness, and synthesis feasibility.

**Prompt 2 (shorter, still effective):**
> Design xyloside GAG primer candidates with clean ADMET, SA score under 6, and no PAINS alerts. Exclude nitro aromatics and flat polyaromatics.

**Prompt 3 (exploratory):**
> What xyloside scaffolds balance GAG priming potency with low hERG risk? Generate candidates and rank them.

## What the pipeline will do

The coordinator reads these docs and extracts: domain (organic_chemistry), scaffold type (xyloside), property constraints, safety exclusions, and success metrics. Then the executor runs the full plugin chain:

1. enumerate_fragments (xyloside preset - 21 built-in fragments)
2. standardize_smiles (canonicalize + deduplicate)
3. predict_properties (MW, LogP, TPSA, QED, Lipinski)
4. check_toxicity (PAINS + structural alerts)
5. score_synthesizability (SA score)
6. predict_admet (hERG, DILI, Caco2, CYP3A4)
7. plan_synthesis (retrosynthesis routes)
8. evaluate_strategy (route feasibility ranking)

## Files

- `target_brief_xyloside_gag.txt` - Project brief and constraints
- `prior_campaign_results.txt` - XYL-Alpha-01 results and lessons
- `admet_and_safety_guide.txt` - ADMET triage rules and exclusions
- `medicinal_chemistry_hypotheses.txt` - Design hypotheses for next cycle
- `literature_review_gag_priming.txt` - Published findings on xyloside GAG primers
- `synthesis_constraints.txt` - Route complexity and supply constraints
- `assay_protocols.txt` - Screening assays and decision tree
