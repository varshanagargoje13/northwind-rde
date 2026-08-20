"""
Context router — selects and assembles the correct layer subset for each LLM phase
and writes context_manifest.json as an audit trail of what each call received.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .assembler import build_analysis_context, build_report_context
from .compressor import compress_layers, assemble


def route_analysis(
    artifacts:        list[dict],
    schemas:          dict[str, dict],
    ontology_facts:   str,
    sparql_conflicts: list[dict],
    out_dir:          Path | None = None,
) -> str:
    """
    Build the full 6-layer context string for Phase 1 (Tool Runner agentic analysis).
    Saves an entry to context_manifest.json if out_dir is provided.
    Returns the assembled context string.
    """
    try:
        layers  = build_analysis_context(artifacts, schemas, ontology_facts, sparql_conflicts)
        layers  = compress_layers(layers)
        context = assemble(layers)
    except Exception as exc:
        raise RuntimeError(f"Phase 1 context assembly failed: {exc}") from exc
    if out_dir:
        _append_manifest(out_dir, "phase1_analysis", layers, context)
    return context


def route_report(
    artifacts:  list[dict],
    conflicts:  list[dict],
    actions:    list[dict],
    violations: list[dict] | None = None,
    out_dir:    Path | None = None,
) -> str:
    """
    Build the condensed context string for Phase 2 (streaming report generation).
    """
    try:
        ctx_dict = build_report_context(artifacts, conflicts, actions, violations)
        context  = ctx_dict["full"]
    except Exception as exc:
        raise RuntimeError(f"Phase 2 context assembly failed: {exc}") from exc
    if out_dir:
        _append_manifest(out_dir, "phase2_reports", {"full": context}, context)
    return context


def _append_manifest(out_dir: Path, phase: str, layers: dict, assembled: str) -> None:
    path = out_dir / "context_manifest.json"
    entry = {
        "phase":       phase,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "total_chars": len(assembled),
        "layer_sizes": {k: len(v) for k, v in layers.items()},
    }
    existing: list = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
