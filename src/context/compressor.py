"""
Token-aware context compression.

Priority order for trimming when total exceeds budget:
  Keep (never trim): layer1, layer2, layer3, layer5, layer6
  Trim last:         layer4 (artifact data — largest, most compressible)
"""


def compress_layers(layers: dict, max_chars: int = 120_000) -> dict:
    """
    Trim layer4 (artifact data) if the total context exceeds max_chars.
    Returns a new dict — original is not mutated.
    """
    fixed  = sum(len(v) for k, v in layers.items() if k != "layer4")
    budget = max_chars - fixed
    l4     = layers.get("layer4", "")

    if budget >= len(l4):
        return layers  # fits — no trimming needed

    out = dict(layers)
    out["layer4"] = (
        l4[: max(budget, 4000)]
        + "\n\n  [... artifact data trimmed to fit token budget — "
        "see outputs/consolidated_state.json for full data]"
    )
    return out


def assemble(layers: dict) -> str:
    """Concatenate layers in fixed order into a single context string."""
    order = ["layer1", "layer2", "layer3", "layer4", "layer5", "layer6"]
    return "\n\n".join(layers[k] for k in order if k in layers and layers[k].strip())
