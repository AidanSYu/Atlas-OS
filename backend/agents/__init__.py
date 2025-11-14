# Placeholder for agent-specific logic; can be swapped with real models/services later
from dataclasses import dataclass
from typing import List

@dataclass
class Route:
    route_id: str
    confidence: float
    summary: str
    steps: List[str]
