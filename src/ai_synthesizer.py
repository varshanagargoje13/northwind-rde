"""
AI-powered escalation synthesis using Claude claude-opus-5.

Two-phase agentic architecture:
  Phase 1 — Conflict analysis: Claude reads all 7 artifacts and their JSON schemas
             from data/schema/, checks each artifact against its schema constraints,
             flags cross-source conflicts, and surfaces action items via structured tools.
             The Tool Runner drives the agentic loop.
  Phase 2 — Report generation: Three streaming calls produce the output reports
             from the structured analysis produced in Phase 1.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from anthropic import beta_tool

MODEL = "claude-opus-5"

# ── Shared state for the current analysis run ─────────────────────────────────
# Reset at the top of run_agentic_analysis() before each pipeline execution.
_current_conflicts: list[dict] = []
_current_actions: list[dict] = []
_current_schema_violations: list[dict] = []


# ── Schema loader ─────────────────────────────────────────────────────────────

_SCHEMA_FILE_TO_SOURCE: dict[str, str] = {
    "zendesk_ticket":  "Zendesk",
    "slack_thread":    "Slack",
    "postmortem":      "Postmortem",
    "telemetry":       "Telemetry",
    "account_summary": "Account Summary",
    "jira_tickets":    "Jira",
    "executive_email": "Executive Email",
}


def load_schemas(schema_dir: Path) -> dict[str, dict]:
    """Load all *.schema.json files from data/schema/ → {source_name: schema_dict}."""
    schemas: dict[str, dict] = {}
    if not schema_dir or not schema_dir.exists():
        return schemas
    for f in sorted(schema_dir.glob("*.schema.json")):
        stem = f.name[: f.name.index(".")]          # "zendesk_ticket.schema.json" → "zendesk_ticket"
        source = _SCHEMA_FILE_TO_SOURCE.get(stem)
        if source:
            try:
                schemas[source] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
    return schemas


def _summarize_schema(schema: dict) -> str:
    """Build a compact schema summary for inclusion in the LLM prompt."""
    lines: list[str] = []
    props    = schema.get("properties", {})
    defs     = schema.get("definitions", {})
    required = set(schema.get("required", []))

    for field, spec in props.items():
        req_mark = "*" if field in required else " "
        ftype    = spec.get("type", "object" if "$ref" in spec else "?")
        parts: list[str] = []
        if "enum"    in spec: parts.append("enum: " + " | ".join(str(v) for v in spec["enum"]))
        if "minimum" in spec: parts.append(f"min={spec['minimum']}")
        if "maximum" in spec: parts.append(f"max={spec['maximum']}")
        if "pattern" in spec: parts.append(f"pattern={spec['pattern']}")
        if "$ref"    in spec:
            ref_name  = spec["$ref"].split("/")[-1]
            ref_props = list(defs.get(ref_name, {}).get("properties", {}).keys())
            preview   = ", ".join(ref_props[:5]) + ("…" if len(ref_props) > 5 else "")
            parts.append(f"→ {ref_name}({preview})")
        suffix = f"  [{', '.join(parts)}]" if parts else ""
        lines.append(f"    [{req_mark}] {field}: {ftype}{suffix}")

    return "\n".join(lines) if lines else "    (no top-level properties)"


# ── Agentic tools ─────────────────────────────────────────────────────────────

@beta_tool
def flag_schema_violation(
    source: str,
    field: str,
    expected: str,
    actual: str,
    severity: str,
) -> str:
    """Flag a field that violates its JSON schema definition.

    Call this whenever an artifact's data does not conform to its schema:
    missing required fields, values outside an allowed enum, numbers outside
    min/max bounds, wrong type, or unexpected additional properties.

    Args:
        source: Artifact source name (e.g., 'Zendesk', 'Jira', 'Account Summary').
        field: Field name or JSON path (e.g., 'renewal_risk', 'tickets[2].status').
        expected: Schema constraint (e.g., 'enum: LOW|MEDIUM|HIGH|CRITICAL', 'integer ≥ 0').
        actual: The actual value found in the artifact.
        severity: 'HIGH' (blocks analysis), 'MEDIUM' (suspicious), or 'LOW' (advisory).
    """
    _current_schema_violations.append({
        "source": source,
        "field": field,
        "expected": expected,
        "actual": actual,
        "severity": severity,
    })
    col = "\033[91m" if severity == "HIGH" else "\033[93m" if severity == "MEDIUM" else "\033[92m"
    print(
        f"    {col}[SCHEMA {severity}]\033[0m [{source}] {field}: "
        f"expected {expected!r}, got {actual!r}",
        flush=True,
    )
    return f"Schema violation registered: [{source}] {field}"


@beta_tool
def flag_conflict(
    category: str,
    severity: str,
    sources: list[str],
    description: str,
    implication: str,
) -> str:
    """Flag a factual conflict detected between two or more artifact sources.

    Call this for EVERY contradiction you find: timeline disagreements, status
    conflicts, impact-count differences, root-cause disputes, or anything where
    two sources make mutually incompatible claims about the same fact.

    Args:
        category: Short label, e.g. 'Timeline', 'Resolution Status', 'Impact Count',
                  'Root Cause', 'Revenue at Risk'.
        severity: Operational impact — 'HIGH', 'MEDIUM', or 'LOW'.
        sources: Names of the artifact sources that contradict each other.
        description: Precise description of what each source claims and why they conflict.
                     Include specific values (dates, numbers, statuses).
        implication: Why this conflict matters for the customer relationship or
                     engineering response — what bad decision it could lead to.
    """
    _current_conflicts.append({
        "category": category,
        "severity": severity,
        "sources": sources,
        "description": description,
        "implication": implication,
    })
    col = "\033[91m" if severity == "HIGH" else "\033[93m" if severity == "MEDIUM" else "\033[92m"
    print(f"    {col}[{severity}]\033[0m {category}: {description[:80]}...", flush=True)
    return f"Conflict registered: [{severity}] {category}"


@beta_tool
def add_action_item(
    priority: str,
    title: str,
    owner: str,
    sources: list[str],
    description: str,
) -> str:
    """Add a prioritized action item derived from the escalation artifacts.

    Call this for EVERY concrete action that needs to happen — technical fixes,
    customer communications, process improvements, or account health actions.

    Args:
        priority: 'P0' (do today), 'P1' (this week), 'P2' (this sprint),
                  or 'P3' (account health / renewal).
        title: Short imperative phrase starting with a verb, e.g. 'Fix stuck orders'.
        owner: Name or role of the person/team responsible.
        sources: Artifact source names that justify this action.
        description: What to do, why it matters, and the expected outcome.
    """
    _current_actions.append({
        "priority": priority,
        "title": title,
        "owner": owner,
        "sources": sources,
        "description": description,
    })
    p_col = "\033[91m" if priority == "P0" else "\033[93m" if priority == "P1" else "\033[0m"
    print(f"    {p_col}[{priority}]\033[0m {title} (Owner: {owner})", flush=True)
    return f"Action registered: [{priority}] {title}"


# ── Artifact context builder ───────────────────────────────────────────────────

def _build_artifact_context(artifacts: list[dict], schemas: dict[str, dict]) -> str:
    """Flatten all 7 artifacts — with their JSON schemas — into a single prompt block."""
    lines = [
        "# 7 Escalation Artifacts + JSON Schemas\n",
        "For EACH artifact below you have both its SCHEMA and its DATA.",
        "Steps:",
        "  1. Read the schema — note required(*) fields, enum values, and numeric bounds.",
        "  2. Check each data field against its schema — call flag_schema_violation for",
        "     any missing required field, invalid enum value, out-of-range number, or wrong type.",
        "  3. Call flag_conflict for every contradiction between two or more sources.",
        "  4. Call add_action_item for every concrete action needed.\n",
    ]

    schemas_loaded = sorted(schemas.keys())
    if schemas_loaded:
        lines.append(f"Schemas loaded from data/schema/: {', '.join(schemas_loaded)}\n")
    else:
        lines.append("(No schemas found — skipping schema validation step)\n")

    for a in artifacts:
        source = a["source"]
        lines.append(f"{'─' * 60}")
        lines.append(f"## [{source}]  (file: {a['file']})\n")

        # ── Schema block ──────────────────────────────────────────────────────
        if source in schemas:
            schema = schemas[source]
            lines.append(f"### Schema  ({schema.get('title', source)})")
            lines.append(f"  Description: {schema.get('description', '')}")
            lines.append(f"  Fields (* = required):")
            lines.append(_summarize_schema(schema))
        else:
            lines.append("### Schema: (not available for this source)")
        lines.append("")

        # ── Data block ────────────────────────────────────────────────────────
        lines.append("### Data")
        skip = {"source", "file", "raw", "raw_text"}
        for k, v in a.items():
            if k in skip or v is None:
                continue
            if isinstance(v, datetime):
                v = v.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"  {k}: {v}")

        # Raw text preview for markdown artifacts
        if "raw_text" in a:
            lines.append("  --- content ---")
            lines.append(a["raw_text"][:1200])
            lines.append("  --- end ---")
        # Comments / messages for structured artifacts
        elif "raw" in a and isinstance(a.get("raw"), dict):
            raw = a["raw"]
            if "comments" in raw:
                lines.append("  comments:")
                for c in raw["comments"]:
                    lines.append(
                        f"    [{c.get('timestamp', '')[:10]}] {c.get('author', '')}: "
                        f"{c.get('body', '')[:200]}"
                    )
            if "messages" in raw:
                lines.append("  messages:")
                for m in raw["messages"][:10]:
                    lines.append(
                        f"    [{m.get('timestamp', '')[:10]}] {m.get('user', '')}: "
                        f"{m.get('text', '')[:200]}"
                    )
        lines.append("")

    return "\n".join(lines)


# ── Phase 1: Agentic conflict + action analysis ────────────────────────────────

ANALYSIS_SYSTEM = """You are an expert customer escalation analyst. You have 7 escalation artifacts
AND their JSON schemas from data/schema/. Your task is schema-aware conflict analysis.

STEP 1 — Schema validation (use flag_schema_violation):
  For each artifact, check every data field against its schema:
  • Missing required fields (marked * in the schema listing)
  • Values outside allowed enums (e.g., renewal_risk must be LOW/MEDIUM/HIGH/CRITICAL)
  • Numbers outside min/max bounds (e.g., error_rate_pct must be 0–100, health_score 0–100)
  • Wrong types (e.g., sla_breach must be boolean, not string)
  • Pattern mismatches (e.g., ticket_id must match ^ZD-\\d+$)

STEP 2 — Cross-source conflict detection (use flag_conflict):
  For every contradiction between two or more artifacts:
  • Timeline disagreements (incident start time differs between sources)
  • Resolution status conflicts (one says RESOLVED, another says OPEN)
  • Order count mismatches (47 vs 23 vs 60 affected orders)
  • Root-cause disputes (DB migration vs gateway connection leak)
  • Revenue / impact figure differences

STEP 3 — Action items (use add_action_item):
  For every concrete step needed — technical fixes, customer comms, process improvements,
  account health actions. Prioritize P0 (today) / P1 (this week) / P2 (sprint) / P3 (account).

Be exhaustive. Missing a schema violation, conflict, or action item in an escalation costs
the customer relationship."""


def run_agentic_analysis(
    artifacts:        list[dict],
    schemas:          dict[str, dict],
    ontology_facts:   str = "",
    sparql_conflicts: list[dict] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Phase 1: Claude reads artifact schemas then data, calls tools to register
    schema violations, conflicts, and action items.
    When ontology_facts are provided the 6-layer context router is used;
    otherwise falls back to the flat _build_artifact_context prompt.
    Returns (conflicts, action_items, schema_violations).
    """
    global _current_conflicts, _current_actions, _current_schema_violations
    _current_conflicts        = []
    _current_actions          = []
    _current_schema_violations = []

    client = anthropic.Anthropic()

    if ontology_facts:
        from .context.router import route_analysis as _route
        context = _route(
            artifacts, schemas, ontology_facts, sparql_conflicts or [],
            out_dir=None,
        )
    else:
        context = _build_artifact_context(artifacts, schemas)

    n_schemas = len(schemas)
    print(
        f"  Running schema-aware agentic analysis "
        f"(claude-opus-5 + Tool Runner, {n_schemas} schemas loaded)...\n",
        flush=True,
    )

    # cache_control on both the system prompt and the large artifact+schema context
    # so repeated tool-loop turns reuse the cached prefix instead of re-tokenizing
    cached_system = [
        {"type": "text", "text": ANALYSIS_SYSTEM, "cache_control": {"type": "ephemeral"}}
    ]
    cached_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}}
            ],
        }
    ]

    try:
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            tools=[flag_schema_violation, flag_conflict, add_action_item],
            system=cached_system,
            messages=cached_messages,
        )
        for _ in runner:
            pass  # Tool Runner drives the loop
    except anthropic.AuthenticationError as exc:
        raise anthropic.AuthenticationError(
            "ANTHROPIC_API_KEY is invalid or missing."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise RuntimeError(
            f"Claude API rate limit reached during agentic analysis: {exc}"
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(
            f"Could not connect to Claude API during agentic analysis: {exc}"
        ) from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"Claude API returned error {exc.status_code} during agentic analysis: {exc.message}"
        ) from exc

    conflicts  = list(_current_conflicts)
    actions    = list(_current_actions)
    violations = list(_current_schema_violations)
    return conflicts, actions, violations


# ── Phase 2: Streaming report generation ──────────────────────────────────────

_REPORT_SYSTEM = """You are a senior technical account manager writing urgent escalation reports.
Be precise, specific, and cite sources explicitly with [Source Name] notation.
Do not hedge — state what the data shows. Surface the risk clearly."""

# Cached system block — same for all 3 report calls; only tokenized once per session
_CACHED_REPORT_SYSTEM = [
    {"type": "text", "text": _REPORT_SYSTEM, "cache_control": {"type": "ephemeral"}}
]


def _stream_report(
    client: anthropic.Anthropic,
    cached_ctx_block: dict,
    report_prompt: str,
    label: str,
) -> str:
    """
    Stream one report from Claude.

    cached_ctx_block  — shared context content block with cache_control (reused across
                        all 3 calls; only billed as input tokens on the first call).
    report_prompt     — the per-report instruction (not cached; unique per call).
    """
    print(f"  Streaming [{label}]...", end=" ", flush=True)
    full_text = ""
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=_CACHED_REPORT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        cached_ctx_block,                         # cached — free on calls 2 & 3
                        {"type": "text", "text": report_prompt},  # unique per report
                    ],
                }
            ],
        ) as stream:
            for text in stream.text_stream:
                full_text += text
    except anthropic.RateLimitError as exc:
        raise RuntimeError(
            f"Rate limit reached while streaming [{label}]: {exc}"
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(
            f"Connection lost while streaming [{label}]: {exc}"
        ) from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"API error {exc.status_code} while streaming [{label}]: {exc.message}"
        ) from exc
    print(f"done ({len(full_text):,} chars)", flush=True)
    return full_text


def generate_reports(
    artifacts: list[dict],
    ai_conflicts: list[dict],
    ai_actions: list[dict],
    ai_schema_violations: list[dict] | None = None,
) -> tuple[str, str, str]:
    """
    Phase 2: Three streaming calls — one per output report.
    Returns (executive_summary, conflict_report, action_items).
    """
    client = anthropic.Anthropic()

    # Build shared context — same text for all 3 reports; cache it so calls 2 & 3 are free
    account   = next((a for a in artifacts if a["source"] == "Account Summary"), {})
    telemetry = next((a for a in artifacts if a["source"] == "Telemetry"), {})
    jira      = next((a for a in artifacts if a["source"] == "Jira"), {})
    email     = next((a for a in artifacts if a["source"] == "Executive Email"), {})

    violations = ai_schema_violations or []

    ctx = (
        f"CUSTOMER: {account.get('customer')} ({account.get('tier')})\n"
        f"CONTRACT: ${account.get('contract_value_usd', 0):,}/year | "
        f"Renewal: {account.get('renewal_date')} | Risk: {account.get('renewal_risk')}\n"
        f"HEALTH: {account.get('health_score')}/100 (declining) | NPS: {account.get('nps_score')}/10\n"
        f"EXEC CONTACT: {account.get('executive_contact')} | VP email received: {email.get('date', 'N/A')}\n"
        f"CURRENT ERROR RATE: {telemetry.get('current_error_rate_pct')}% (baseline 0.2%) | "
        f"STATUS: {telemetry.get('current_status', '').upper()}\n"
        f"STUCK ORDERS: {telemetry.get('stuck_orders_count')} (telemetry) | "
        f"Known: {', '.join(jira.get('known_affected_orders', []))}\n"
        f"OPEN JIRA: {', '.join(jira.get('critical_open_tickets', []))}\n\n"
        + (
            f"SCHEMA VIOLATIONS DETECTED ({len(violations)}):\n"
            + "\n".join(
                f"  [{v['severity']}] [{v['source']}] {v['field']}: "
                f"expected {v['expected']!r}, got {v['actual']!r}"
                for v in violations
            )
            + "\n\n"
            if violations else ""
        )
        + f"AI-DETECTED CONFLICTS ({len(ai_conflicts)}):\n"
        + "\n".join(
            f"  [{c['severity']}] {c['category']}: {c['description']}"
            for c in ai_conflicts
        )
        + f"\n\nAI-DETECTED ACTIONS ({len(ai_actions)}):\n"
        + "\n".join(
            f"  [{a['priority']}] {a['title']} (Owner: {a['owner']})"
            for a in ai_actions
        )
    )

    # Single cached content block — Anthropic bills input tokens only on the first hit;
    # the second and third streaming calls read from the prompt cache at ~10% of the cost.
    cached_ctx_block = {"type": "text", "text": ctx, "cache_control": {"type": "ephemeral"}}

    # ── Executive Summary ──────────────────────────────────────────────────────
    exec_prompt = f"""Write a complete Executive Escalation Summary for this incident.

{ctx}

Format as markdown with these sections:
# Executive Escalation Summary — [Customer] [Incident ID]
## Situation at a Glance (2-3 sentences, include renewal risk)
## Incident Timeline (table: When | Event | Source)
## Impact (bullet list with source citations [Source])
## Root Cause Summary (numbered list, each cited)
## Data Conflicts Detected (table: Severity | Category | Finding)
## Open Items Requiring Immediate Attention (table: # | Item | Owner | Status)

Cite every fact with [Source Name]. Be direct about risks. Max 2 pages."""

    # ── Conflict Report ────────────────────────────────────────────────────────
    conflict_prompt = f"""Write a full Cross-Artifact Conflict Report.

{ctx}

Format as markdown:
# Conflict Report — Cross-Artifact Analysis
## Conflict Index (numbered list)
Then for each conflict:
## Conflict N: [SEVERITY] — [Category]
**Summary:** ...
**Source breakdown:** (bullet per source with their specific claim)
**Why this matters:** ...

End with:
## Artifact Summary Table
| Source | Incident Start Claim | Orders Affected | Resolution Status |
Include all 7 sources. Be specific about each conflict."""

    # ── Action Items ───────────────────────────────────────────────────────────
    action_prompt = f"""Write a complete Prioritized Action Items report.

{ctx}

Format as markdown:
# Prioritized Action Items — [Customer] Escalation
## P0 — Immediate (Today)
### N. [Title]
- **Why:** ...
- **Owner:** ...
- **Sources:** [Source1] [Source2]
- **Action:** specific steps

## P1 — This Week
## P2 — This Sprint
## P3 — Account Health

End with a 'Conflict-Driven Items' section noting which actions exist specifically
because of cross-source conflicts. Cite every source."""

    print("\n  Generating 3 reports via streaming (ctx cached across calls):\n", flush=True)

    def _safe_stream(prompt: str, label: str, fallback_heading: str) -> str:
        try:
            return _stream_report(client, cached_ctx_block, prompt, label)
        except RuntimeError as exc:
            print(f"\n  [WARN] {label} streaming failed: {exc}", flush=True)
            return f"# {fallback_heading}\n\n*Report generation failed: {exc}*\n"

    exec_summary    = _safe_stream(exec_prompt,     "Executive Summary", "Executive Escalation Summary")
    conflict_report = _safe_stream(conflict_prompt, "Conflict Report",   "Conflict Report")
    action_items    = _safe_stream(action_prompt,   "Action Items",      "Prioritized Action Items")

    return exec_summary, conflict_report, action_items


# ── Public entry point ─────────────────────────────────────────────────────────

def synthesize(
    artifacts:        list[dict],
    data_dir:         Path | None = None,
    knowledge_graph=None,
    sparql_conflicts: list[dict] | None = None,
) -> tuple[list[dict], list[dict], str, str, str]:
    """
    Full two-phase schema-aware AI synthesis with optional ontology context.

    Phase 1: Loads JSON schemas from data_dir/schema/, then runs the agentic loop —
             Claude validates each artifact against its schema, flags cross-source
             conflicts, and surfaces action items.  When knowledge_graph is supplied,
             the 6-layer context router is used and SPARQL-derived ontology facts
             are injected as Layer 2.
    Phase 2: Three streaming report calls using cached context.

    Returns (conflicts, actions, executive_summary, conflict_report, action_items).
    Raises anthropic.AuthenticationError if ANTHROPIC_API_KEY is not set.
    """
    schema_dir = (data_dir / "schema") if data_dir else None
    schemas    = load_schemas(schema_dir) if schema_dir else {}

    if schemas:
        print(f"  Schemas loaded: {', '.join(sorted(schemas))}", flush=True)
    else:
        print("  [WARN] No schemas found — schema validation step will be skipped.", flush=True)

    ontology_facts = ""
    if knowledge_graph is not None:
        try:
            from .ontology.sparql_detector import extract_facts
            ontology_facts = extract_facts(knowledge_graph)
            print(f"  Ontology facts extracted ({len(ontology_facts):,} chars)", flush=True)
        except Exception as exc:
            print(f"  [WARN] Ontology fact extraction failed: {exc}", flush=True)

    conflicts, actions, violations = run_agentic_analysis(
        artifacts, schemas, ontology_facts, sparql_conflicts
    )

    if violations:
        print(
            f"\n  Schema violations: {len(violations)} "
            f"({sum(1 for v in violations if v['severity'] == 'HIGH')} HIGH / "
            f"{sum(1 for v in violations if v['severity'] == 'MEDIUM')} MEDIUM / "
            f"{sum(1 for v in violations if v['severity'] == 'LOW')} LOW)",
            flush=True,
        )

    exec_md, conflict_md, actions_md = generate_reports(
        artifacts, conflicts, actions, violations
    )
    return conflicts, actions, exec_md, conflict_md, actions_md
