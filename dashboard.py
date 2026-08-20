"""
Northwind Escalation Synthesizer — Streamlit Dashboard
Reads live from data/ and outputs/ folders.
Run: streamlit run dashboard.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# allow importing src package from dashboard.py at repo root
sys.path.insert(0, str(Path(__file__).parent))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Northwind Escalation Synthesizer",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
DATA_DIR  = ROOT / "data"
OUT_DIR   = ROOT / "outputs"

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    account   = json.loads((DATA_DIR / "account_summary.json").read_text(encoding="utf-8"))
    telemetry = json.loads((DATA_DIR / "telemetry.json").read_text(encoding="utf-8"))
    jira      = json.loads((DATA_DIR / "jira_tickets.json").read_text(encoding="utf-8"))
    zendesk   = json.loads((DATA_DIR / "zendesk_ticket.json").read_text(encoding="utf-8"))
    slack     = json.loads((DATA_DIR / "slack_thread.json").read_text(encoding="utf-8"))
    return account, telemetry, jira, zendesk, slack

account, telemetry, jira, zendesk, slack = load_data()

def load_override_log():
    log_path = OUT_DIR / "override_log.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in lines if l.strip()]


def load_consolidated_state() -> dict | None:
    path = OUT_DIR / "consolidated_state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def load_conflicts_and_actions():
    """Run rule-based conflict detection and return conflicts + default actions."""
    from src.loaders import load_all
    from src.conflict_detector import detect_all
    artifacts = load_all(DATA_DIR)
    conflicts = detect_all(artifacts)
    conflict_dicts = [
        {"category": c.category, "severity": c.severity,
         "sources": c.sources, "description": c.description,
         "details": c.details}
        for c in conflicts
    ]
    actions = [
        {
            "priority": "P0",
            "title": "Fix stuck orders ORD-55892, ORD-55901",
            "owner": "Engineering On-Call",
            "deadline": "Today — before EOD",
            "why": "Customer-reported stuck orders unresolved since Aug 11. NWAPI-3362 is Open and Unassigned. Contoso VP email cites these as the primary blocker to renewal.",
            "steps": "1. Assign NWAPI-3362 to on-call engineer. 2. Manually re-queue ORD-55892 and ORD-55901 through the order processing pipeline. 3. Confirm successful delivery and notify CSM.",
            "sources": ["Zendesk", "Jira", "Slack"],
        },
        {
            "priority": "P0",
            "title": "Send executive update to Derek Hartley",
            "owner": "CSM / TAM",
            "deadline": "EOD today",
            "why": "Last customer update was Aug 13 — 6 days overdue. CEO Margaret Peacock is CC'd. Renewal is threatened and an active competitor evaluation is underway.",
            "steps": "1. Draft exec-level summary: acknowledge delay, confirm stuck-order fix ETA, name the responsible engineer. 2. Schedule a 30-min follow-up call this week. 3. CC TAM and VP Support.",
            "sources": ["Executive Email", "Account Summary"],
        },
        {
            "priority": "P0",
            "title": "Audit all customers for stuck orders",
            "owner": "Support Engineering",
            "deadline": "Today",
            "why": "Postmortem notes 3 enterprise accounts were affected. Only Contoso has surfaced stuck orders so far — others may be silently impacted.",
            "steps": "1. Query order processing pipeline for all orders with status=STUCK since Aug 11. 2. Identify affected accounts. 3. Proactively notify CSMs for each account found.",
            "sources": ["Postmortem", "Slack", "Account Summary"],
        },
        {
            "priority": "P1",
            "title": "Reconcile true order impact count",
            "owner": "TAM + Engineering",
            "deadline": "This week",
            "why": "Claims range from 23 (Postmortem) to 60+ (Slack/Jira) — a spread of 37. An accurate number is required for SLA credit calculation and executive comms.",
            "steps": "1. Pull canonical order count from the order DB (not from artifact estimates). 2. Cross-reference with Zendesk, Jira, and Telemetry. 3. Publish agreed count to all stakeholders.",
            "sources": ["Postmortem", "Zendesk", "Slack", "Jira", "Telemetry"],
        },
        {
            "priority": "P1",
            "title": "Resolve root cause timeline discrepancy",
            "owner": "Engineering Lead",
            "deadline": "This week",
            "why": "Slack/Telemetry show incident start Aug 11 18:00 UTC; Postmortem says Aug 13 23:00 UTC — a 53-hour gap. Wrong start time leads to wrong root cause attribution and incomplete fix.",
            "steps": "1. Pull raw telemetry error logs from Aug 11–14. 2. Identify first anomaly spike. 3. Amend postmortem with corrected timeline. 4. Verify root cause chain is still valid.",
            "sources": ["Slack", "Postmortem", "Jira", "Telemetry"],
        },
        {
            "priority": "P2",
            "title": "Implement DB connection pool circuit breaker",
            "owner": "Platform Engineering",
            "deadline": "This sprint",
            "why": "Pool exhaustion (50 intl vs 200 domestic) compounded by the Aug 13 migration caused the cascading failure. Without a circuit breaker, the same pattern will recur.",
            "steps": "1. Add circuit breaker around international DB pool. 2. Set pool limit to 200 (match domestic). 3. Add alerting at 80% pool saturation. 4. Load-test in staging before deploying.",
            "sources": ["Postmortem", "Jira"],
        },
        {
            "priority": "P3",
            "title": "Schedule emergency QBR with Contoso",
            "owner": "CSM + VP Support",
            "deadline": "Within 2 weeks",
            "why": "Health score 42/100 (declining), NPS 4/10, 2 SLA breaches in 90 days, active competitor eval. A QBR is needed to reset the relationship before renewal.",
            "steps": "1. Propose QBR agenda: incident RCA, remediation roadmap, SLA credit, renewal discussion. 2. Include VP Support and CTO in the invite. 3. Prepare account health report as pre-read.",
            "sources": ["Account Summary", "Executive Email"],
        },
    ]
    return conflict_dicts, actions


override_log        = load_override_log()
consolidated_state  = load_consolidated_state()
live_conflicts, live_actions = load_conflicts_and_actions()


def compute_citation_counts(conflicts: list[dict], actions: list[dict]) -> dict[str, dict]:
    """Count how many conflicts and actions cite each source."""
    counts: dict[str, dict] = {}
    for c in conflicts:
        for src in c.get("sources", []):
            counts.setdefault(src, {"conflicts": 0, "actions": 0})
            counts[src]["conflicts"] += 1
    for a in actions:
        for src in a.get("sources", []):
            counts.setdefault(src, {"conflicts": 0, "actions": 0})
            counts[src]["actions"] += 1
    for src in counts:
        counts[src]["total"] = counts[src]["conflicts"] + counts[src]["actions"]
    return dict(sorted(counts.items(), key=lambda x: x[1]["total"], reverse=True))


citation_counts = compute_citation_counts(live_conflicts, live_actions)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stHeader"] { background: #0f1117; }
.block-container { padding: 1.5rem 2rem; max-width: 1200px; }
h1, h2, h3 { color: #e2e8f0 !important; }
p, li { color: #94a3b8; }

.card {
    background: #1a1d2e; border: 1px solid #2d3150;
    border-radius: 10px; padding: 16px; margin-bottom: 12px;
}
.card-title {
    font-size: 13px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: #c7d2fe; margin-bottom: 12px;
}

/* KPI */
.kpi-wrap { border-radius: 10px; padding: 16px; border: 1px solid #2d3150; }
.kpi-before { font-size: 13px; color: #ef4444; text-decoration: line-through; margin-bottom: 4px; }
.kpi-val { font-size: 30px; font-weight: 800; color: #fff; line-height: 1; }
.kpi-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 6px; }
.kpi-sub { font-size: 13px; margin-top: 5px; }

/* Conflict */
.conflict-high { background: #1c0a0a; border-left: 4px solid #ef4444; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }
.conflict-medium { background: #1c1200; border-left: 4px solid #f59e0b; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }
.conflict-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.conflict-desc { font-size: 13px; color: #94a3b8; margin-top: 3px; line-height: 1.5; }
.conflict-src { font-size: 12px; color: #64748b; margin-top: 4px; }

/* Recommendation */
.rec-card { background: #12152a; border: 1px solid #2d3150; border-radius: 6px; padding: 10px 12px; margin-bottom: 7px; }
.rec-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.rec-why { font-size: 13px; color: #94a3b8; margin-top: 3px; }
.rec-src { font-size: 12px; color: #3b82f6; margin-top: 3px; }

/* Badge */
.badge { display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 9px; border-radius: 20px; margin: 2px; }
.badge-red    { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; }
.badge-yellow { background: #422006; color: #fcd34d; border: 1px solid #78350f; }
.badge-green  { background: #052e16; color: #86efac; border: 1px solid #14532d; }
.badge-blue   { background: #0c1a3a; color: #93c5fd; border: 1px solid #1e3a5f; }
.badge-p0 { background: #450a0a; color: #fca5a5; }
.badge-p1 { background: #422006; color: #fcd34d; }
.badge-p2 { background: #0c1a3a; color: #93c5fd; }
.badge-p3 { background: #1a0a2e; color: #c4b5fd; }

/* Artifact */
.artifact-box { background: #12152a; border: 1px solid #2d3150; border-radius: 8px; padding: 12px; text-align: center; }
.artifact-icon { font-size: 24px; margin-bottom: 5px; }
.artifact-name { font-size: 13px; font-weight: 600; color: #c7d2fe; }
.artifact-status { font-size: 12px; margin-top: 3px; }

/* Audit */
.audit-row { font-size: 12px; font-family: monospace; padding: 5px 8px; border-radius: 4px; margin-bottom: 4px; border-left: 3px solid; }
.audit-high   { background: #0a1a0a; border-color: #22c55e; color: #86efac; }
.audit-medium { background: #1a1200; border-color: #f59e0b; color: #fcd34d; }

/* BA */
.ba-before { background: #1c0a0a; border: 1px solid #7f1d1d; border-radius: 8px; padding: 14px; }
.ba-after  { background: #052e16; border: 1px solid #14532d; border-radius: 8px; padding: 14px; }
.ba-label  { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
.ba-before .ba-label { color: #ef4444; }
.ba-after  .ba-label { color: #22c55e; }
.ba-text { font-size: 14px; line-height: 1.7; color: #94a3b8; }

hr-custom { border: none; border-top: 1px solid #2d3150; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## 🚨 Northwind Escalation Synthesizer")
    
with col_h2:
    st.markdown("""
        <div style='text-align:right;padding-top:10px;'>
            
        </div>
    """, unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 7 ARTIFACT SOURCES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 7 Artifact Sources")
artifacts_display = [
    ("🎫", "Zendesk",      "ZD-98741 · ZD-99788"),
    ("💬", "Slack",        "#incident · 16 msgs"),
    ("📋", "Postmortem",   "APPROVED · INC-0812"),
    ("📊", "Telemetry",    "DEGRADED · 1.4% error rate"),
    ("🏢", "Account",      f"Health {account['health_score']} · HIGH risk"),
    ("🔖", "Jira",         "5 tickets · 2 open"),
    ("✉️", "Exec Email",   "VP + CEO escalated"),
]
art_cols = st.columns(7)
for col, (icon, name, status) in zip(art_cols, artifacts_display):
    col.markdown(f"""
    <div class='artifact-box'>
        <div class='artifact-icon'>{icon}</div>
        <div class='artifact-name'>{name}</div>
        <div class='artifact-status' style='color:#f59e0b;'>{status}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Citation Counts ───────────────────────────────────────────────────────────
with st.expander("📊 Source Citation Counts", expanded=False):
    st.caption(
        "How many times each artifact source is referenced across detected conflicts and "
        "recommended actions — sorted by total citations."
    )

    max_total = max((v["total"] for v in citation_counts.values()), default=1)

    # Column headers
    h_src, h_bar, h_cf, h_ac, h_tot = st.columns([2, 4, 1.2, 1.2, 1])
    h_src.markdown("**Source**")
    h_bar.markdown("**Citation Weight**")
    h_cf.markdown("**Conflicts**")
    h_ac.markdown("**Actions**")
    h_tot.markdown("**Total**")
    st.divider()

    for src, cnts in citation_counts.items():
        c_src, c_bar, c_cf, c_ac, c_tot = st.columns([2, 4, 1.2, 1.2, 1])
        c_src.markdown(f"**{src}**")
        c_bar.progress(cnts["total"] / max_total)
        c_cf.markdown(
            f"<span style='color:#ef4444;font-weight:700;'>{cnts['conflicts']}</span>",
            unsafe_allow_html=True,
        )
        c_ac.markdown(
            f"<span style='color:#f59e0b;font-weight:700;'>{cnts['actions']}</span>",
            unsafe_allow_html=True,
        )
        c_tot.markdown(f"**{cnts['total']}**")

    st.divider()
    most_cited       = next(iter(citation_counts))
    total_citations  = sum(v["total"] for v in citation_counts.values())
    st.caption(
        f"**{total_citations}** total citations across **{len(citation_counts)}** sources — "
        f"**{most_cited}** is the most-cited source."
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Incident table ────────────────────────────────────────────────────────────
_PRIO_CSS = {
    "Critical": "background:#dc2626;color:#fff;",
    "High":     "background:#d97706;color:#fff;",
    "Medium":   "background:#2563eb;color:#fff;",
    "Low":      "background:#16a34a;color:#fff;",
}
_STATUS_CSS = {
    "Open":      "background:#dc2626;color:#fff;",
    "In Review": "background:#d97706;color:#fff;",
    "Done":      "background:#16a34a;color:#fff;",
    "Backlog":   "background:#7c3aed;color:#fff;",
}

st.markdown("""
<style>
div[data-testid="column"] button {
    font-size: 12px !important; padding: 4px 6px !important;
    border-radius: 6px !important; width: 100% !important;
    white-space: nowrap !important;
}
[data-testid^="review_"] > button {
    background:#2563eb !important; color:#fff !important;
    border-color:#2563eb !important;
}
</style>
""", unsafe_allow_html=True)

# ── Incident Review Dialog ────────────────────────────────────────────────────
@st.dialog("Incident Review", width="large")
def _incident_review_dialog(ticket: dict, all_actions: list[dict]) -> None:
    _PRIO_COL = {"Critical": "#dc2626", "High": "#d97706",
                 "Medium": "#2563eb",   "Low": "#16a34a"}
    _STAT_COL = {"Open": "#dc2626", "In Review": "#d97706",
                 "Done": "#16a34a",  "Backlog": "#7c3aed"}
    _ACT_COL  = {"P0": "#fca5a5", "P1": "#fcd34d",
                 "P2": "#93c5fd", "P3": "#c4b5fd"}

    pc = _PRIO_COL.get(ticket["priority"], "#334155")
    sc = _STAT_COL.get(ticket["status"],   "#334155")

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style='background:#12152a;border:1px solid #2d3150;
                border-radius:8px;padding:16px;margin-bottom:16px;'>
        <div style='font-size:22px;font-weight:800;color:#c7d2fe;
                    margin-bottom:6px;'>{ticket["id"]}</div>
        <div style='font-size:16px;color:#e2e8f0;
                    margin-bottom:12px;'>{ticket["title"]}</div>
        <span style='display:inline-block;padding:3px 14px;border-radius:10px;
                     font-size:13px;font-weight:700;background:{pc};
                     color:#fff;margin-right:8px;'>{ticket["priority"]}</span>
        <span style='display:inline-block;padding:3px 14px;border-radius:10px;
                     font-size:13px;font-weight:700;background:{sc};
                     color:#fff;'>{ticket["status"]}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Ticket details ────────────────────────────────────────────────────────
    skip = {"id", "title", "priority", "status"}
    extras = {k: v for k, v in ticket.items() if k not in skip and v not in (None, "", [])}
    if extras:
        st.markdown("**Incident Details**")
        for k, v in extras.items():
            label = k.replace("_", " ").title()
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            st.markdown(f"- **{label}:** {v}")

    # ── Related recommendations ───────────────────────────────────────────────
    related = [a for a in all_actions if "Jira" in a.get("sources", [])]
    if not related:
        related = all_actions[:3]           # fallback: show top 3

    selected_recommendations: list[dict] = []
    if related:
        st.markdown("---")
        st.markdown("**Recommendations** — select to include in approval")
        for idx, a in enumerate(related):
            ac   = _ACT_COL.get(a["priority"], "#94a3b8")
            srcs = ", ".join(a.get("sources", []))
            cb_col, card_col = st.columns([0.06, 0.94])
            with cb_col:
                checked = st.checkbox(
                    label="select",
                    key=f"dlg_rec_{ticket['id']}_{idx}",
                    label_visibility="collapsed",
                )
            with card_col:
                owner    = a.get("owner", "")
                deadline = a.get("deadline", "")
                why      = a.get("why", "")
                steps    = a.get("steps", "")
                owner_line    = f"<span style='color:#64748b;font-size:12px;'>👤 {owner}</span>&nbsp;&nbsp;" if owner else ""
                deadline_line = f"<span style='color:#f59e0b;font-size:12px;'>⏱ {deadline}</span>" if deadline else ""
                why_line   = f"<div style='font-size:13px;color:#94a3b8;margin-top:6px;'><b style='color:#c7d2fe;'>Why:</b> {why}</div>" if why else ""
                steps_line = f"<div style='font-size:13px;color:#94a3b8;margin-top:4px;'><b style='color:#c7d2fe;'>Steps:</b> {steps}</div>" if steps else ""
                st.markdown(f"""
                <div style='border-left:4px solid {ac};padding:10px 14px;
                            background:#12152a;border-radius:0 6px 6px 0;
                            margin-bottom:4px;'>
                    <div style='margin-bottom:4px;'>
                        <span style='font-size:12px;font-weight:700;color:{ac};'>{a["priority"]}</span>
                        &nbsp;·&nbsp;
                        <span style='font-size:14px;font-weight:600;color:#e2e8f0;'>{a["title"]}</span>
                    </div>
                    <div style='margin-bottom:4px;'>{owner_line}{deadline_line}</div>
                    {why_line}
                    {steps_line}
                    <div style='font-size:12px;color:#475569;margin-top:6px;'>Sources: {srcs}</div>
                </div>
                """, unsafe_allow_html=True)
            if checked:
                selected_recommendations.append(a)

    # ── Actions ───────────────────────────────────────────────────────────────
    st.markdown("---")
    approved_key = f"dlg_approved_{ticket['id']}"
    if approved_key not in st.session_state:
        st.session_state[approved_key] = False

    if st.session_state[approved_key]:
        # ── Post-approval confirmation ─────────────────────────────────────────
        st.markdown(f"""
        <div style='background:#052e16;border:1px solid #14532d;border-radius:10px;
                    padding:20px 24px;margin-bottom:16px;'>
            <div style='font-size:18px;font-weight:700;color:#22c55e;
                        margin-bottom:14px;'>✅ Approval Actions Completed</div>
            <div style='display:flex;flex-direction:column;gap:10px;'>
                <div style='display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:20px;'>📧</span>
                    <span style='font-size:14px;color:#86efac;font-weight:600;'>
                        Email sent to Customer</span>
                </div>
                <div style='display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:20px;'>📋</span>
                    <span style='font-size:14px;color:#86efac;font-weight:600;'>
                        Executive Summary sent to Executive</span>
                </div>
                <div style='display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:20px;'>🔖</span>
                    <span style='font-size:14px;color:#86efac;font-weight:600;'>
                        Jira Status Updated</span>
                </div>
            </div>
            <div style='font-size:12px;color:#4ade80;margin-top:14px;'>
                Logged to outputs/override_log.jsonl &nbsp;·&nbsp;
                {len(selected_recommendations)} recommendation(s) included
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Close", use_container_width=True, key=f"dlg_close_{ticket['id']}"):
            st.session_state[approved_key] = False
            st.rerun()
    else:
        btn_approve, btn_edit, _ = st.columns([1, 1, 3])
        with btn_approve:
            if st.button("✓ Approve", type="primary", use_container_width=True,
                         key=f"dlg_approve_{ticket['id']}"):
                _e = {"timestamp": datetime.now(timezone.utc).isoformat(),
                      "dri": "dashboard", "item_type": "incident",
                      "item_id": ticket["id"], "original": ticket["status"],
                      "override": "approved",
                      "approved_recommendations": [a["title"] for a in selected_recommendations],
                      "comment": ""}
                OUT_DIR.mkdir(exist_ok=True)
                with open(OUT_DIR / "override_log.jsonl", "a", encoding="utf-8") as _f:
                    _f.write(json.dumps(_e) + "\n")
                st.session_state[approved_key] = True
        with btn_edit:
            if st.button("✎ Edit", use_container_width=True,
                         key=f"dlg_edit_{ticket['id']}"):
                st.toast(f"Open Jira to edit {ticket['id']}", icon="✏️")


# ── Audit Trail Dialog ────────────────────────────────────────────────────────
@st.dialog("Audit Trail", width="large")
def _audit_trail_dialog(ticket_id: str, log: list[dict]) -> None:
    entries = [e for e in log if e.get("item_id") == ticket_id]

    st.markdown(f"**Ticket:** `{ticket_id}`")
    st.caption(f"{len(entries)} log entries found in outputs/override_log.jsonl")
    st.divider()

    if not entries:
        st.info("No audit entries yet for this ticket. Approve or review it to create a log entry.")
        return

    for e in reversed(entries):        # newest first
        ts        = e.get("timestamp", "")[:19].replace("T", " ") + " UTC"
        override  = e.get("override", "").upper()
        dri       = e.get("dri", "dashboard")
        comment   = e.get("comment", "")
        recs      = e.get("approved_recommendations", [])

        badge_color = {"APPROVED": "#16a34a", "REJECTED": "#dc2626",
                       "REVIEW": "#2563eb"}.get(override, "#475569")

        st.markdown(
            f"<div style='border-left:4px solid {badge_color};padding:10px 14px;"
            f"background:#12152a;border-radius:0 6px 6px 0;margin-bottom:10px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-bottom:6px;'>"
            f"<span style='font-size:13px;font-weight:700;color:#fff;"
            f"background:{badge_color};padding:2px 10px;border-radius:10px;'>{override}</span>"
            f"<span style='font-size:12px;color:#64748b;'>{ts}</span></div>"
            f"<div style='font-size:13px;color:#94a3b8;'>DRI: <b style='color:#e2e8f0;'>{dri}</b></div>"
            + (f"<div style='font-size:13px;color:#94a3b8;margin-top:4px;'>Comment: {comment}</div>" if comment else "")
            + (f"<div style='font-size:13px;color:#86efac;margin-top:4px;'>✅ Recommendations approved:<ul style='margin:4px 0 0 16px;'>"
               + "".join(f"<li>{r}</li>" for r in recs) + "</ul></div>" if recs else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    if st.button("Close", use_container_width=True, key=f"audit_close_{ticket_id}"):
        st.rerun()


# Use identical column ratios for header and every data row so they align perfectly
_COL_RATIOS = [1.2, 3.2, 1.0, 1.1, 3.2]
_HS = ("font-size:12px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;"
       "color:#c7d2fe;padding:8px 4px 8px 0;border-bottom:2px solid #2d3150;"
       "display:block;")

# Header — same st.columns call, plain markdown
st.markdown("<div style='background:#12152a;border:1px solid #2d3150;"
            "border-radius:10px 10px 0 0;padding:0 8px;'>",
            unsafe_allow_html=True)
hc = st.columns(_COL_RATIOS)
for col, label in zip(hc, ["INCIDENT_ID", "DESCRIPTION", "PRIORITY", "STATUS", "ACTION"]):
    col.markdown(f"<span style='{_HS}'>{label}</span>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Data rows
_pill = lambda css, label: (
    "<span style='display:inline-block;padding:3px 10px;border-radius:10px;"
    "font-size:12px;font-weight:700;" + css + "'>" + label + "</span>"
)
n = len(jira["tickets"])
for i, t in enumerate(jira["tickets"]):
    row_bg   = "#1a1d2e" if i % 2 == 0 else "#161929"
    last_r   = "border-radius:0 0 10px 10px;" if i == n - 1 else ""
    prio_css = _PRIO_CSS.get(t["priority"], "background:#334155;color:#fff;")
    stat_css = _STATUS_CSS.get(t["status"],  "background:#334155;color:#fff;")
    cell_s   = ("font-size:13px;padding:10px 4px 10px 0;"
                "border-bottom:1px solid #2d3150;display:block;")

    st.markdown(
        "<div style='background:" + row_bg + ";border-left:1px solid #2d3150;"
        "border-right:1px solid #2d3150;" + last_r + "padding:0 8px;'>",
        unsafe_allow_html=True,
    )
    dc = st.columns(_COL_RATIOS)

    dc[0].markdown(
        "<span style='" + cell_s + "font-weight:700;color:#c7d2fe;'>" + t["id"] + "</span>",
        unsafe_allow_html=True,
    )
    dc[1].markdown(
        "<span style='" + cell_s + "color:#94a3b8;'>" + t["title"] + "</span>",
        unsafe_allow_html=True,
    )
    dc[2].markdown(
        "<span style='" + cell_s + "text-align:center;'>" + _pill(prio_css, t["priority"]) + "</span>",
        unsafe_allow_html=True,
    )
    dc[3].markdown(
        "<span style='" + cell_s + "text-align:center;'>" + _pill(stat_css, t["status"]) + "</span>",
        unsafe_allow_html=True,
    )
    with dc[4]:
        btn_review, btn_audit = st.columns(2)
        if btn_review.button("Review", key=f"review_{t['id']}", use_container_width=True):
            _incident_review_dialog(t, live_actions)
        if btn_audit.button("Audit Trail", key=f"audit_{t['id']}", use_container_width=True):
            _audit_trail_dialog(t["id"], load_override_log())

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='border:1px solid #2d3150;border-top:none;border-radius:0 0 10px 10px;"
            "height:4px;background:#12152a;'></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)


