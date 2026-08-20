"""
Context Engineering — assembles the 6-layer context dict for each LLM phase.

Layer priority (highest → lowest for token budget):
  Layer 1 — System role + ontology vocabulary
  Layer 2 — Ontology facts (SPARQL-extracted RDF triples)
  Layer 3 — JSON Schema constraints per artifact
  Layer 5 — SPARQL-detected conflicts (structured seed)
  Layer 4 — Guardrailed artifact data  (trimmed last if over budget)
  Layer 6 — Task instruction (never trimmed)
"""

from datetime import datetime


def _fmt_artifact(a: dict, max_chars: int = 1800) -> str:
    skip = {"source", "file", "raw", "raw_text"}
    lines = [f"### [{a['source']}]  (file: {a.get('file', '')})"]
    for k, v in a.items():
        if k in skip or v is None:
            continue
        if isinstance(v, datetime):
            v = v.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"  {k}: {v}")
    if "raw_text" in a:
        lines.append("  --- content ---")
        lines.append(a["raw_text"][:800])
        lines.append("  --- end ---")
    elif "raw" in a and isinstance(a.get("raw"), dict):
        raw = a["raw"]
        for key in ("comments", "messages"):
            entries = raw.get(key, [])
            if entries:
                lines.append(f"  {key}:")
                for e in entries[:6]:
                    ts  = e.get("timestamp", "")[:10]
                    who = e.get("author") or e.get("user", "")
                    txt = (e.get("body") or e.get("text", ""))[:160]
                    lines.append(f"    [{ts}] {who}: {txt}")
    return "\n".join(lines)[:max_chars]


def _fmt_schema(source: str, schema: dict) -> str:
    props    = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines    = [f"### [{source}] schema"]
    for field, spec in props.items():
        req = "*" if field in required else " "
        parts = []
        if "enum"    in spec: parts.append("enum:" + "|".join(str(v) for v in spec["enum"]))
        if "minimum" in spec: parts.append(f"min={spec['minimum']}")
        if "maximum" in spec: parts.append(f"max={spec['maximum']}")
        if "pattern" in spec: parts.append(f"pattern={spec['pattern']}")
        suffix = f" [{', '.join(parts)}]" if parts else ""
        lines.append(f"  [{req}] {field}: {spec.get('type', '?')}{suffix}")
    return "\n".join(lines)


def _fmt_conflicts(conflicts: list[dict]) -> str:
    if not conflicts:
        return "No SPARQL conflicts pre-detected."
    lines = [f"### SPARQL Conflicts ({len(conflicts)} detected — verify and extend)\n"]
    for i, c in enumerate(conflicts, 1):
        lines.append(f"{i}. [{c['severity']}] {c['category']}")
        lines.append(f"   {c['description']}")
        for d in c.get("details", [])[:4]:
            lines.append(f"   {d}")
        lines.append("")
    return "\n".join(lines)


def build_analysis_context(
    artifacts:        list[dict],
    schemas:          dict[str, dict],
    ontology_facts:   str,
    sparql_conflicts: list[dict],
) -> dict:
    """
    Assemble all 6 context layers for Phase 1 (Tool Runner agentic analysis).
    Returns dict with keys layer1..layer6.
    """
    layer1 = (
        "You are an expert escalation analyst. You have an RDF knowledge graph built from "
        "the northwind_escalation.ttl domain ontology, JSON schemas, and 7 guardrailed artifacts.\n\n"
        "Ontology classes: Incident, Artifact, Order, Customer, RootCause, IncidentStatus, Conflict.\n"
        "Key OWL constraint: nw:Open owl:disjointWith nw:Resolved — any source claiming both is a "
        "confirmed ontology violation.\n"
        "Available tools: flag_schema_violation, flag_conflict, add_action_item."
    )

    layer2 = ontology_facts if ontology_facts.strip() else "(Ontology graph not available)"

    schema_parts = ["## JSON Schema Constraints per Artifact\n"]
    for source, schema in schemas.items():
        schema_parts.append(_fmt_schema(source, schema))
        schema_parts.append("")
    layer3 = "\n".join(schema_parts)

    art_parts = ["## Guardrailed Artifact Data\n"]
    for a in artifacts:
        art_parts.append(_fmt_artifact(a))
        art_parts.append("")
    layer4 = "\n".join(art_parts)

    layer5 = (
        "## Pre-Detected SPARQL Conflicts (seed — confirm each with flag_conflict; add any missed)\n\n"
        + _fmt_conflicts(sparql_conflicts)
    )

    layer6 = (
        "## Your Task\n"
        "Step 1 — Ontology validation: review Layer 2 triples. For any field violating its "
        "Layer 3 schema constraint, call flag_schema_violation.\n"
        "Step 2 — Conflict confirmation: for each SPARQL conflict in Layer 5, call flag_conflict "
        "to confirm it; also detect any additional conflicts the SPARQL queries missed.\n"
        "Step 3 — Actions: call add_action_item for every concrete remediation needed (P0/P1/P2/P3).\n"
        "Be exhaustive — every missed conflict or action costs the customer relationship."
    )

    return {
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3,
        "layer4": layer4,
        "layer5": layer5,
        "layer6": layer6,
    }


def build_report_context(
    artifacts:  list[dict],
    conflicts:  list[dict],
    actions:    list[dict],
    violations: list[dict] | None = None,
) -> dict:
    """
    Assemble condensed context for Phase 2 (streaming report generation).
    Returns dict with 'full' key containing the assembled string.
    """
    acc  = next((a for a in artifacts if a["source"] == "Account Summary"), {})
    tele = next((a for a in artifacts if a["source"] == "Telemetry"), {})
    jira = next((a for a in artifacts if a["source"] == "Jira"), {})
    em   = next((a for a in artifacts if a["source"] == "Executive Email"), {})
    viol = violations or []

    header = (
        f"CUSTOMER: {acc.get('customer')} ({acc.get('tier')})\n"
        f"CONTRACT: ${acc.get('contract_value_usd', 0):,}/yr | "
        f"Renewal: {acc.get('renewal_date')} | Risk: {acc.get('renewal_risk')}\n"
        f"HEALTH: {acc.get('health_score')}/100 | NPS: {acc.get('nps_score')}/10\n"
        f"ERROR RATE: {tele.get('current_error_rate_pct')}% | "
        f"STATUS: {tele.get('current_status', '').upper()}\n"
        f"STUCK ORDERS: {tele.get('stuck_orders_count')} | "
        f"Known: {', '.join(jira.get('known_affected_orders', []))}\n"
        f"OPEN JIRA: {', '.join(jira.get('critical_open_tickets', []))}\n"
        f"VP EMAIL: \"{em.get('subject', '')[:60]}\"\n"
    )

    conflict_block = (
        f"\nCONFLICTS ({len(conflicts)}):\n"
        + "\n".join(
            f"  [{c.get('severity','?')}] {c.get('category','?')}: {c.get('description','')}"
            for c in conflicts
        )
    )

    actions_block = (
        f"\nACTIONS ({len(actions)}):\n"
        + "\n".join(
            f"  [{a.get('priority','?')}] {a.get('title','?')} (Owner: {a.get('owner','?')})"
            for a in actions
        )
    )

    violations_block = ""
    if viol:
        violations_block = (
            f"\nSCHEMA VIOLATIONS ({len(viol)}):\n"
            + "\n".join(
                f"  [{v['severity']}] [{v['source']}] {v['field']}: "
                f"expected {v['expected']!r}, got {v['actual']!r}"
                for v in viol
            )
        )

    full = header + conflict_block + actions_block + violations_block
    return {"header": header, "conflicts": conflict_block, "actions": actions_block,
            "violations": violations_block, "full": full}
