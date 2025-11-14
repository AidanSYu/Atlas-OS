class ManufacturabilityAgent:
    def assess(self, candidate: str, scale_kg: float = 1.0):
        score = max(0.1, round(1.0 - min(len(candidate)/200.0, 0.5) - min(scale_kg/100.0, 0.5), 2))
        risks = []
        if scale_kg > 10:
            risks.append("Scale-up risk")
        if any(k in candidate.lower() for k in ["peroxide","azide","nitro"]):
            risks.append("Energetic group risk")
        if len(candidate) > 80:
            risks.append("Complexity risk")
        if not risks:
            risks = ["No major red flags from high-level screen"]
        notes = "Conceptual assessment only."
        return {"score": score, "risks": risks, "notes": notes}
