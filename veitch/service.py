from .logic import parse, minimize, cubes
from .diagram import render_svg


def solve(source, model=None):
    function = parse(source)
    scores = model.predict(function) if model is not None else None
    result = minimize(function, scores)
    result["svg"] = render_svg(result)
    ones = sum(1 << i for i in function.ones)
    proposed = [p for p, _ in cubes(len(function.variables)) if scores and scores[p] >= .5]
    rejected = sum(1 for p, m in cubes(len(function.variables)) if p in proposed and m & ones != m)
    result["ml"] = {"enabled": model is not None, "proposed_groups": len(proposed),
                    "invalid_proposals": rejected, "verified": True}
    return result
