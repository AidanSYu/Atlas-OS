import random
from . import Route

class SynthesisPredictor:
    def predict(self, target: str):
        rnd = random.Random(hash(target) & 0xFFFFFFFF)
        base_steps = [
            "Fragment selection",
            "Coupling strategy",
            "Protecting group strategy",
            "Purification overview",
        ]
        routes = []
        for i, summary in enumerate([
            "Convergent route",
            "Modular FGI route",
            "Fragment coupling route",
        ]):
            steps = base_steps[:]
            rnd.shuffle(steps)
            routes.append(Route(f"route-{i+1}", round(0.6 + 0.1*rnd.random(),2), summary, steps))
        return routes
