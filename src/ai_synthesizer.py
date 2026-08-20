"""
AI-powered escalation synthesis using Claude claude-opus-5.

Two-phase agentic architecture:
  Phase 1 — Conflict analysis: Claude autonomously reads all 7 artifacts and
             uses structured tools to flag conflicts and surface action items.
             The Tool Runner drives the agentic loop.
  Phase 2 — Report generation: Three streaming calls produce the output reports
             from the structured analysis produced in Phase 1.
"""

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


# ── Agentic tools ─────────────────────────────────────────────────────────────

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

def _build_artifact_context(artifacts: list[dict]) -> str:
    """Flatten all 7 artifacts into a single structured prompt block."""
    lines = [
        "# 7 Escalation Artifacts\n",
        "Analyze every artifact carefully. Flag ALL conflicts between sources.",
        "Add an action item for every concrete step that needs to happen.\n",
    ]
    for a in artifacts:
        lines.append(f"## [{a['source']}]  (file: {a['file']})")
        skip = {"source", "file", "raw", "raw_text"}
        for k, v in a.items():
            if k in skip or v is None:
                continue
            if isinstance(v, datetime):
                v = v.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"  {k}: {v}")
        # Include raw text preview for markdown artifacts
        if "raw_text" in a:
            lines.append("  --- content ---")
            lines.append(a["raw_text"][:1200])
            lines.append("  --- end ---")
        # Include comments / messages for structured artifacts
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

ANALYSIS_SYSTEM = """You are an expert customer escalation analyst. You have 7 artifacts from
a live software escalation incident involving a strategic customer at risk of churning.

Your job:
1. Read every artifact carefully and completely.
2. Use flag_conflict for EVERY contradiction between sources — timeline disagreements,
   status conflicts (one says resolved, another says open), impact-count differences,
   root-cause disputes, revenue-estimate gaps, etc. Do not miss conflicts.
3. Use add_action_item for EVERY concrete action needed — technical fixes, comms,
   process improvements, account health steps. Prioritize P0/P1/P2/P3.

Be exhaustive. Missing a conflict or action item in an escalation costs the customer relationship."""


def run_agentic_analysis(artifacts: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Phase 1: Claude uses tool calls to flag conflicts and action items.
    Returns (conflicts, action_items).
    """
    global _current_conflicts, _current_actions
    _current_conflicts = []
    _current_actions = []

    client = anthropic.Anthropic()
    context = _build_artifact_context(artifacts)

    print("  Running agentic analysis (claude-opus-5 + Tool Runner)...\n", flush=True)

    # cache_control on both the system prompt and the large artifact context block
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

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        tools=[flag_conflict, add_action_item],
        system=cached_system,
        messages=cached_messages,
    )

    for _ in runner:
        pass  # Tool Runner drives the loop; tools append to _current_conflicts / _current_actions

    conflicts = list(_current_conflicts)
    actions = list(_current_actions)
    return conflicts, actions


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
    print(f"done ({len(full_text):,} chars)", flush=True)
    return full_text


def generate_reports(
    artifacts: list[dict],
    ai_conflicts: list[dict],
    ai_actions: list[dict],
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
        f"AI-DETECTED CONFLICTS ({len(ai_conflicts)}):\n"
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
    exec_summary    = _stream_report(client, cached_ctx_block, exec_prompt,     "Executive Summary")
    conflict_report = _stream_report(client, cached_ctx_block, conflict_prompt, "Conflict Report")
    action_items    = _stream_report(client, cached_ctx_block, action_prompt,   "Action Items")

    return exec_summary, conflict_report, action_items


# ── Public entry point ─────────────────────────────────────────────────────────

def synthesize(artifacts: list[dict]) -> tuple[list[dict], list[dict], str, str, str]:
    """
    Full two-phase AI synthesis.
    Returns (conflicts, actions, executive_summary, conflict_report, action_items).
    Raises anthropic.AuthenticationError if ANTHROPIC_API_KEY is not set.
    """
    conflicts, actions = run_agentic_analysis(artifacts)
    exec_md, conflict_md, actions_md = generate_reports(artifacts, conflicts, actions)
    return conflicts, actions, exec_md, conflict_md, actions_md
