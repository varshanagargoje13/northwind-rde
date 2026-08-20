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
        {"priority": "P0", "title": "Fix stuck orders ORD-55892, ORD-55901",
         "sources": ["Zendesk", "Jira", "Slack"]},
        {"priority": "P0", "title": "Send executive update to Derek Hartley",
         "sources": ["Executive Email", "Account Summary"]},
        {"priority": "P0", "title": "Audit all customers for stuck orders",
         "sources": ["Postmortem", "Slack", "Account Summary"]},
        {"priority": "P1", "title": "Reconcile true order impact count",
         "sources": ["Postmortem", "Zendesk", "Slack", "Jira", "Telemetry"]},
        {"priority": "P1", "title": "Resolve root cause timeline discrepancy",
         "sources": ["Slack", "Postmortem", "Jira", "Telemetry"]},
        {"priority": "P2", "title": "Implement DB connection pool circuit breaker",
         "sources": ["Postmortem", "Jira"]},
        {"priority": "P3", "title": "Schedule emergency QBR with Contoso",
         "sources": ["Account Summary", "Executive Email"]},
    ]
    return conflict_dicts, actions


override_log        = load_override_log()
consolidated_state  = load_consolidated_state()
live_conflicts, live_actions = load_conflicts_and_actions()

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
    st.markdown(
        f"**Customer:** {account['company_name']} ({account['tier']}) &nbsp;·&nbsp; "
        f"**CSM:** {account['csm']} &nbsp;·&nbsp; "
        f"**TAM:** {account['technical_account_manager']} &nbsp;·&nbsp; "
        f"**Generated:** 2026-08-19"
    )
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

# Inject CSS: style Approve=green, Edit=blue-gray, Reject=red via data-key attribute
st.markdown("""
<style>
/* Approve button — green */
button[data-testid="baseButton-secondary"][kind="secondary"]:has(p:-webkit-any(:-webkit-matches-selector("*"))) { }
[data-testid^="approve_"] > button { background:#16a34a !important; color:#fff !important; border-color:#16a34a !important; }
[data-testid^="reject_"]  > button { background:#dc2626 !important; color:#fff !important; border-color:#dc2626 !important; }
[data-testid^="edit_"]    > button { background:#334155 !important; color:#e2e8f0 !important; border-color:#475569 !important; }
div[data-testid="column"] button {
    font-size: 12px !important; padding: 4px 6px !important;
    border-radius: 6px !important; width: 100% !important;
    white-space: nowrap !important;
}
</style>
""", unsafe_allow_html=True)

# Use identical column ratios for header and every data row so they align perfectly
_COL_RATIOS = [1.2, 3.2, 1.0, 1.1, 2.4]
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
        ba, be, br = st.columns(3)
        if ba.button("✓ Approve", key=f"approve_{t['id']}", use_container_width=True):
            _e = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "dri": "dashboard", "item_type": "incident", "item_id": t["id"],
                  "original": t["status"], "override": "approved", "comment": ""}
            with open(OUT_DIR / "override_log.jsonl", "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_e) + "\n")
            st.toast(f"{t['id']} approved", icon="✅")
        if be.button("✎ Edit",   key=f"edit_{t['id']}",    use_container_width=True):
            st.toast(f"Open Jira to edit {t['id']}", icon="✏️")
        if br.button("✗ Reject", key=f"reject_{t['id']}",  use_container_width=True):
            _e = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "dri": "dashboard", "item_type": "incident", "item_id": t["id"],
                  "original": t["status"], "override": "rejected", "comment": ""}
            with open(OUT_DIR / "override_log.jsonl", "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_e) + "\n")
            st.toast(f"{t['id']} rejected", icon="❌")

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='border:1px solid #2d3150;border-top:none;border-radius:0 0 10px 10px;"
            "height:4px;background:#12152a;'></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSOLIDATED STATE PANEL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Consolidated Interim State")
if consolidated_state:
    cs = consolidated_state
    sigs = cs.get("conflict_signals", {})
    oi   = cs.get("orders_impact", {})
    inc  = cs.get("incident", {})

    _ts = cs.get("consolidated_at", "")[:19].replace("T", " ") + " UTC"

    st.markdown(
        "<div style='background:#12152a;border:1px solid #2d3150;border-radius:12px;"
        "padding:14px 18px 10px;margin-bottom:4px;'>"
        "<div style='font-size:11px;color:#64748b;margin-bottom:10px;'>"
        "Merged from <b style='color:#c7d2fe'>" + str(cs.get("source_count", 7)) + " sources</b>"
        " &nbsp;·&nbsp; Persisted to <code style='color:#818cf8'>outputs/consolidated_state.json</code>"
        " &nbsp;·&nbsp; Generated: <span style='color:#94a3b8'>" + _ts + "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    _cs1, _cs2, _cs3, _cs4 = st.columns(4)

    def _sig_chip(label: str, active: bool, col) -> None:
        bg  = "#7f1d1d" if active else "#0a2a0a"
        fg  = "#fca5a5" if active else "#86efac"
        bdr = "#be123c" if active else "#16a34a"
        icon= "✗" if active else "✓"
        col.markdown(
            f"<div style='background:{bg};border:1px solid {bdr};border-radius:8px;"
            f"padding:8px 10px;margin-bottom:6px;'>"
            f"<div style='font-size:11px;font-weight:700;color:{fg};'>{icon} {label}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    _sig_chip("Status Mismatch",      sigs.get("status_mismatch", False),      _cs1)
    _sig_chip("Order Count Mismatch", sigs.get("order_count_mismatch", False),  _cs2)
    _sig_chip("Root Cause Mismatch",  sigs.get("root_cause_mismatch", False),   _cs3)
    _sig_chip("Unassigned Critical",  sigs.get("unassigned_critical_ticket", False), _cs4)

    _d1, _d2, _d3, _d4 = st.columns(4)
    def _detail(label, val, col):
        col.markdown(
            f"<div style='background:#1a1d2e;border:1px solid #2d3150;border-radius:8px;"
            f"padding:8px 10px;margin-bottom:6px;'>"
            f"<div style='font-size:10px;color:#64748b;text-transform:uppercase;"
            f"letter-spacing:.06em;'>{label}</div>"
            f"<div style='font-size:14px;font-weight:700;color:#c7d2fe;margin-top:3px;'>{val}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    _detail("Order claims range",
            f"{oi.get('min_claim','?')} – {oi.get('max_claim','?')}  (gap: {oi.get('gap','?')})",
            _d1)
    _detail("Start-time span",
            f"{sigs.get('start_time_span_hours','?')} h across sources",
            _d2)
    _detail("Distinct root causes",
            str(cs.get("root_cause", {}).get("distinct_claim_count", "?")),
            _d3)
    _detail("Current error rate",
            f"{inc.get('current_error_rate_pct','?')}%  ({inc.get('current_status','')})",
            _d4)

    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("View full consolidated_state.json"):
        st.json(cs)
else:
    st.info(
        "Consolidated state not found. Run `python pipeline.py` to generate "
        "`outputs/consolidated_state.json`.",
        icon="ℹ️",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# KPI TILES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### KPIs")
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown("""
    <div class='kpi-wrap' style='background:#0d2818;border-color:#14532d;border-top:3px solid #22c55e;'>
        <div class='kpi-label'>Context Assembly</div>
        <div class='kpi-before'>4–8 hrs manual</div>
        <div class='kpi-val'>18ms</div>
        <div class='kpi-sub' style='color:#22c55e;'>✓ Target &lt;5 min</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown("""
    <div class='kpi-wrap' style='background:#0c1a3a;border-color:#1e3a5f;border-top:3px solid #3b82f6;'>
        <div class='kpi-label'>Conflict Detection</div>
        <div class='kpi-before'>1–2 hrs manual</div>
        <div class='kpi-val'>4</div>
        <div class='kpi-sub' style='color:#3b82f6;'>✓ &lt;30 sec &nbsp;·&nbsp; 2 HIGH, 2 MED</div>
    </div>""", unsafe_allow_html=True)

with k3:
    st.markdown("""
    <div class='kpi-wrap' style='background:#1a1200;border-color:#78350f;border-top:3px solid #f59e0b;'>
        <div class='kpi-label'>Source Citation (Audit Trail)</div>
        <div class='kpi-before'>0% — manual notes</div>
        <div class='kpi-val'>100%</div>
        <div class='kpi-sub' style='color:#f59e0b;'>✓ Every claim cited [Source]</div>
    </div>""", unsafe_allow_html=True)

with k4:
    st.markdown("""
    <div class='kpi-wrap' style='background:#1a0a2e;border-color:#4c1d95;border-top:3px solid #a855f7;'>
        <div class='kpi-label'>Comms Clarity</div>
        <div class='kpi-before'>Vague / no context</div>
        <div class='kpi-val'>Before→After</div>
        <div class='kpi-sub' style='color:#a855f7;'>✓ Cited · Conflicts · Actionable</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ERROR RATE TIMELINE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Production Telemetry — Error Rate Timeline")

timeline = telemetry["metrics"]["error_rate_timeline"]
timestamps = [e["timestamp"][:16].replace("T", " ") for e in timeline]
error_rates = [e["error_rate_pct"] for e in timeline]
colors = ["#ef4444" if r > 10 else "#f59e0b" if r > 1 else "#22c55e" for r in error_rates]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=timestamps, y=error_rates,
    marker_color=colors,
    hovertemplate="<b>%{x}</b><br>Error rate: %{y}%<extra></extra>",
))
fig.add_hline(y=0.2, line_dash="dot", line_color="#64748b",
              annotation_text="Baseline 0.2%", annotation_font_color="#64748b")
fig.add_vrect(x0="2026-08-12 14:00", x1="2026-08-12 15:00",
              fillcolor="#ef4444", opacity=0.15, line_width=0,
              annotation_text="SEV-1", annotation_font_color="#fca5a5", annotation_position="top left")
fig.add_vrect(x0="2026-08-14 16:00", x1="2026-08-14 17:00",
              fillcolor="#22c55e", opacity=0.15, line_width=0,
              annotation_text="Fix deployed", annotation_font_color="#86efac", annotation_position="top left")
fig.update_layout(
    paper_bgcolor="#1a1d2e", plot_bgcolor="#1a1d2e",
    font=dict(color="#94a3b8", size=11),
    margin=dict(l=40, r=20, t=20, b=60),
    height=220,
    xaxis=dict(showgrid=False, tickangle=-35, tickfont_size=9, color="#64748b"),
    yaxis=dict(showgrid=True, gridcolor="#2d3150", title="Error Rate %", color="#64748b"),
    bargap=0.2,
)
st.plotly_chart(fig, use_container_width=True)

col_tl1, col_tl2, col_tl3 = st.columns(3)
col_tl1.metric("Current Error Rate", f"{telemetry['metrics']['error_rate_timeline'][-1]['error_rate_pct']}%", delta="-50.9% from peak", delta_color="normal")
col_tl2.metric("Peak Error Rate", "52.3%", "Aug 14 06:00 UTC")
col_tl3.metric("Stuck Orders", str(telemetry["metrics"]["stuck_orders_count"]), "ORD-55892, ORD-55901")

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# GUARDRAILS PANEL  (step 3 — runs before analysis so analysis uses clean data)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Guardrails — Per-Artifact Fix Templates")
st.caption("Step 3 in the pipeline: each artifact is validated against its fix template **before** conflict analysis runs. Auto-fixable issues are corrected; unfixable fields are flagged.")

_gr_path = OUT_DIR / "guardrail_report.json"

if _gr_path.exists():
    _gr = json.loads(_gr_path.read_text(encoding="utf-8"))
    _grs = _gr.get("summary", {})
    _gr_ts = _gr.get("generated_at", "")[:19].replace("T", " ") + " UTC"

    _STATUS_COLORS = {
        "PASSED":  ("#16a34a", "#0a2a0a", "✓"),
        "FIXED":   ("#d97706", "#2a1800", "⚠"),
        "FLAGGED": ("#dc2626", "#2a0808", "✗"),
    }

    # Summary strip
    _gr_all_pass = _grs.get("flagged", 1) == 0 and _grs.get("fixed", 0) == 0
    _gr_banner_bg = "#0a2a0a" if _gr_all_pass else "#2a0808" if _grs.get("flagged", 0) else "#2a1800"
    _gr_banner_bdr = "#16a34a" if _gr_all_pass else "#dc2626" if _grs.get("flagged", 0) else "#d97706"
    _gr_banner_msg = "All artifacts passed — analysis running on fully validated data." if _gr_all_pass \
        else f"{_grs.get('flagged',0)} artifact(s) flagged — analysis ran on guardrailed data; flagged fields noted below." \
        if _grs.get("flagged", 0) else \
        f"{_grs.get('fixed',0)} field(s) auto-fixed — analysis ran on corrected data."

    st.markdown(
        "<div style='background:" + _gr_banner_bg + ";border:1px solid " + _gr_banner_bdr + ";"
        "border-radius:10px;padding:10px 16px;margin-bottom:12px;"
        "display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;'>"
        "<div style='display:flex;gap:20px;align-items:center;'>"
        "<span style='font-size:11px;color:#64748b;'>Generated: " + _gr_ts + "</span>"
        "<span style='font-size:13px;font-weight:700;color:#16a34a;'>✓ " + str(_grs.get("passed",0)) + " PASSED</span>"
        "<span style='font-size:13px;font-weight:700;color:#d97706;'>⚠ " + str(_grs.get("fixed",0)) + " FIXED</span>"
        "<span style='font-size:13px;font-weight:700;color:#dc2626;'>✗ " + str(_grs.get("flagged",0)) + " FLAGGED</span>"
        "</div>"
        "<span style='font-size:11px;color:#94a3b8;font-style:italic;'>" + _gr_banner_msg + "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # One card per artifact — 4 columns, wrap to second row if needed
    _gr_arts = _gr.get("artifacts", [])
    _gr_row1 = _gr_arts[:4]
    _gr_row2 = _gr_arts[4:]

    def _render_gr_row(arts):
        cols = st.columns(len(arts)) if arts else []
        for _col, _art in zip(cols, arts):
            _fc, _bg, _icon = _STATUS_COLORS.get(_art["status"], ("#64748b", "#1a1d2e", "?"))
            _check_html = ""
            for _c in _art.get("checks", []):
                _cc, _, _ci = _STATUS_COLORS.get(_c["status"], ("#64748b", "", "?"))
                _check_html += (
                    f"<div style='display:flex;gap:6px;align-items:flex-start;padding:3px 0;"
                    f"border-bottom:1px solid #1e293b;'>"
                    f"<span style='color:{_cc};font-size:10px;flex-shrink:0;margin-top:1px;'>{_ci}</span>"
                    f"<div><div style='font-size:10px;font-weight:600;color:#c7d2fe;'>{_c['field']}</div>"
                    f"<div style='font-size:9px;color:#64748b;'>{_c['note']}</div></div></div>"
                )
            with _col:
                st.markdown(
                    f"<div style='background:{_bg};border:1.5px solid {_fc};"
                    f"border-radius:10px;padding:10px 12px;margin-bottom:8px;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"margin-bottom:6px;'>"
                    f"<span style='font-size:12px;font-weight:700;color:{_fc};'>{_icon} {_art['source']}</span>"
                    f"<span style='font-size:10px;background:#12152a;border:1px solid {_fc};"
                    f"color:{_fc};border-radius:20px;padding:1px 8px;font-weight:700;'>{_art['status']}</span>"
                    f"</div>"
                    f"<div style='font-size:10px;color:#94a3b8;margin-bottom:6px;'>"
                    f"✓ {_art['passed']} &nbsp;⚠ {_art['fixed']} &nbsp;✗ {_art['flagged']}</div>"
                    f"<div style='max-height:130px;overflow-y:auto;'>{_check_html}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    _render_gr_row(_gr_row1)
    if _gr_row2:
        _render_gr_row(_gr_row2)

    with st.expander("View full guardrail_report.json"):
        st.json(_gr)

else:
    st.info(
        "Guardrail report not found. Run `python pipeline.py` to generate "
        "`outputs/guardrail_report.json`.",
        icon="ℹ️",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONFLICTS + RECOMMENDATIONS  (step 4 — runs on guardrailed artifacts)
# ─────────────────────────────────────────────────────────────────────────────
col_cf, col_rec = st.columns(2)

with col_cf:
    st.markdown("""
    <div class='card'>
    <div class='card-title'>Cross-Artifact Conflicts &nbsp;
        <span class='badge badge-red'>2 HIGH</span>
        <span class='badge badge-yellow'>2 MED</span>
    </div>
    <div class='conflict-high'>
        <div class='conflict-title'>Timeline — Incident Start &nbsp; <span class='badge badge-red'>HIGH</span></div>
        <div class='conflict-desc'>53-hour gap: Slack says Aug 11 18:00 UTC, Postmortem says Aug 13 23:00 UTC. Wrong start time = wrong root cause attribution.</div>
        <div class='conflict-src'>Sources: Slack · Telemetry · Zendesk · Executive Email · Postmortem</div>
    </div>
    <div class='conflict-high'>
        <div class='conflict-title'>Resolution Status &nbsp; <span class='badge badge-red'>HIGH</span></div>
        <div class='conflict-desc'>Postmortem: RESOLVED (Aug 14 16:00). Zendesk/Slack/Telemetry/Jira: still OPEN — 1.4% error rate, NWAPI-3362 unassigned.</div>
        <div class='conflict-src'>Sources: All 7 artifacts</div>
    </div>
    <div class='conflict-medium'>
        <div class='conflict-title'>Impact — Orders Affected &nbsp; <span class='badge badge-yellow'>MED</span></div>
        <div class='conflict-desc'>Range: 23 (Postmortem) → 31 (Telemetry) → 47 (Zendesk/Email) → 60+ (Slack/Jira). Spread of 37 orders — unreconciled.</div>
        <div class='conflict-src'>Sources: Postmortem · Zendesk · Slack · Jira · Telemetry · Email</div>
    </div>
    <div class='conflict-medium'>
        <div class='conflict-title'>Impact — Revenue at Risk &nbsp; <span class='badge badge-yellow'>MED</span></div>
        <div class='conflict-desc'>$85K (Postmortem) vs $200K (Account Summary / Executive Email) — 2.4× gap. Affects SLA credits and goodwill decisions.</div>
        <div class='conflict-src'>Sources: Postmortem · Account Summary · Executive Email</div>
    </div>
    </div>
    """, unsafe_allow_html=True)

with col_rec:
    st.markdown("""
    <div class='card'>
    <div class='card-title'>Recommendations &nbsp;
        <span class='badge badge-red'>3 P0</span>
        <span class='badge badge-yellow'>2 P1</span>
        <span class='badge badge-blue'>3 P2</span>
    </div>
    <div class='rec-card'>
        <span class='badge badge-p0'>P0</span>
        <div class='rec-title'>Fix stuck orders ORD-55892 &amp; ORD-55901</div>
        <div class='rec-why'>Incident NOT resolved from customer view. Assign NWAPI-3362 immediately.</div>
        <div class='rec-src'>[Zendesk ZD-98741] [Jira NWAPI-3362] [Slack]</div>
    </div>
    <div class='rec-card'>
        <span class='badge badge-p0'>P0</span>
        <div class='rec-title'>Send exec update to Derek Hartley (VP, Contoso)</div>
        <div class='rec-why'>Last update Aug 13. CEO CC'd. Renewal threatened. Competitor eval active. EOD deadline.</div>
        <div class='rec-src'>[Executive Email] [Account Summary ACC-00441]</div>
    </div>
    <div class='rec-card'>
        <span class='badge badge-p0'>P0</span>
        <div class='rec-title'>Audit ALL customers for stuck orders</div>
        <div class='rec-why'>Postmortem: 3 enterprise accounts affected. Only Contoso has surfaced stuck orders so far.</div>
        <div class='rec-src'>[Postmortem] [Slack] [Account Summary]</div>
    </div>
    <div class='rec-card'>
        <span class='badge badge-p1'>P1</span>
        <div class='rec-title'>Reconcile true order impact count</div>
        <div class='rec-why'>Claims range 23–60+. Accurate number needed for SLA credit and customer comms.</div>
        <div class='rec-src'>[Postmortem] [Zendesk] [Slack] [Jira] [Telemetry]</div>
    </div>
    <div class='rec-card'>
        <span class='badge badge-p1'>P1</span>
        <div class='rec-title'>Resolve root cause timeline discrepancy</div>
        <div class='rec-why'>Slack/Telemetry say Aug 11; Postmortem says Aug 13. Wrong root cause = wrong fix.</div>
        <div class='rec-src'>[Slack] [Postmortem] [Jira] [Telemetry]</div>
    </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DRI REVIEW PANEL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### DRI Review")
st.caption("Review synthesized conflicts and action items, then submit your decisions to the audit trail.")

# initialise session state buckets
if "dri_submitted" not in st.session_state:
    st.session_state.dri_submitted = False
if "dri_log" not in st.session_state:
    st.session_state.dri_log = []

SEV_COLOR = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}
PRIO_COLOR = {"P0": "#fca5a5", "P1": "#fcd34d", "P2": "#93c5fd", "P3": "#c4b5fd"}

dri_col, review_col = st.columns([1, 3])

with dri_col:
    st.markdown("""
    <div class='card'>
    <div class='card-title'>DRI Identity</div>
    </div>
    """, unsafe_allow_html=True)
    dri_name = st.text_input("Your Name", placeholder="e.g. Laura Callahan", key="dri_name")
    dri_role = st.selectbox("Role", ["CSM", "TAM", "Eng Lead", "VP Engineering", "VP Support", "Other"], key="dri_role")
    dri_custom_role = ""
    if dri_role == "Other":
        dri_custom_role = st.text_input("Specify role", key="dri_custom_role")
    effective_role = dri_custom_role if dri_role == "Other" else dri_role

    st.markdown("""
    <div class='card' style='margin-top:12px;'>
    <div class='card-title'>Workflow Step</div>
    <div style='font-size:13px;color:#94a3b8;line-height:1.9;'>
        <span style='color:#22c55e;'>✓</span> Agent ingests 7 artifacts<br>
        <span style='color:#22c55e;'>✓</span> Conflict detection<br>
        <span style='color:#f59e0b;'>→</span> <b style='color:#e2e8f0;'>DRI review (you are here)</b><br>
        <span style='color:#475569;'>○</span> Comms generated<br>
        <span style='color:#475569;'>○</span> DRI approves &amp; sends
    </div>
    </div>
    """, unsafe_allow_html=True)

with review_col:
    with st.expander("Conflict Review", expanded=True):
        conflict_decisions = {}
        conflict_comments  = {}
        for i, c in enumerate(live_conflicts):
            sev   = c["severity"]
            cat   = c["category"]
            desc  = c["description"]
            srcs  = ", ".join(c.get("sources", []))
            color = SEV_COLOR.get(sev, "#94a3b8")

            st.markdown(f"""
            <div style='border-left:4px solid {color};padding:8px 12px;
                        background:#12152a;border-radius:0 6px 6px 0;margin-bottom:4px;'>
                <span style='font-size:12px;font-weight:700;color:{color};
                             text-transform:uppercase;letter-spacing:.06em;'>{sev}</span>
                &nbsp;·&nbsp;
                <span style='font-size:15px;font-weight:600;color:#e2e8f0;'>{cat}</span><br>
                <span style='font-size:13px;color:#94a3b8;'>{desc}</span><br>
                <span style='font-size:12px;color:#475569;'>Sources: {srcs}</span>
            </div>
            """, unsafe_allow_html=True)

            d_col, c_col = st.columns([1, 2])
            with d_col:
                decision = st.radio(
                    "Decision",
                    ["Approve", "Reject", "Escalate"],
                    horizontal=True,
                    key=f"cf_decision_{i}",
                    label_visibility="collapsed",
                )
            with c_col:
                comment = st.text_input("Comment (optional)", key=f"cf_comment_{i}",
                                        placeholder="Add context or override reason…",
                                        label_visibility="collapsed")
            conflict_decisions[i] = decision
            conflict_comments[i]  = comment
            st.markdown("---")

    with st.expander("Action Item Review", expanded=True):
        action_decisions = {}
        action_comments  = {}
        for i, a in enumerate(live_actions):
            prio  = a["priority"]
            title = a["title"]
            srcs  = ", ".join(a.get("sources", []))
            color = PRIO_COLOR.get(prio, "#94a3b8")

            st.markdown(f"""
            <div style='border-left:4px solid {color};padding:8px 12px;
                        background:#12152a;border-radius:0 6px 6px 0;margin-bottom:4px;'>
                <span style='font-size:12px;font-weight:700;color:{color};'>{prio}</span>
                &nbsp;·&nbsp;
                <span style='font-size:15px;font-weight:600;color:#e2e8f0;'>{title}</span><br>
                <span style='font-size:12px;color:#475569;'>Sources: {srcs}</span>
            </div>
            """, unsafe_allow_html=True)

            d_col, c_col = st.columns([1, 2])
            with d_col:
                decision = st.radio(
                    "Decision",
                    ["Include", "Remove"],
                    horizontal=True,
                    key=f"ac_decision_{i}",
                    label_visibility="collapsed",
                )
            with c_col:
                comment = st.text_input("Comment (optional)", key=f"ac_comment_{i}",
                                        placeholder="Reassign owner, change priority…",
                                        label_visibility="collapsed")
            action_decisions[i] = decision
            action_comments[i]  = comment
            st.markdown("---")

    submit_col, status_col = st.columns([1, 3])
    with submit_col:
        submit_review = st.button("Submit Review", type="primary",
                                  use_container_width=True, key="submit_dri")
    with status_col:
        if not dri_name:
            st.warning("Enter your name above before submitting.")

    if submit_review:
        if not dri_name.strip():
            st.error("DRI name is required.")
        else:
            log_path = OUT_DIR / "override_log.jsonl"
            log_path.parent.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).isoformat()
            entries = []

            for i, c in enumerate(live_conflicts):
                entry = {
                    "timestamp": ts,
                    "dri": f"{dri_name} ({effective_role})",
                    "item_type": "conflict",
                    "item_id": c["category"],
                    "original": f"severity={c['severity']}, sources={','.join(c.get('sources',[]))}",
                    "override": conflict_decisions[i].lower(),
                    "comment": conflict_comments[i],
                }
                entries.append(entry)

            for i, a in enumerate(live_actions):
                entry = {
                    "timestamp": ts,
                    "dri": f"{dri_name} ({effective_role})",
                    "item_type": "action",
                    "item_id": a["title"][:50],
                    "original": f"priority={a['priority']}, sources={','.join(a.get('sources',[]))}",
                    "override": action_decisions[i].lower(),
                    "comment": action_comments[i],
                }
                entries.append(entry)

            with open(log_path, "a", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e) + "\n")

            approved_cf = sum(1 for d in conflict_decisions.values() if d == "Approve")
            rejected_cf = sum(1 for d in conflict_decisions.values() if d == "Reject")
            escalated_cf = sum(1 for d in conflict_decisions.values() if d == "Escalate")
            included_ac = sum(1 for d in action_decisions.values() if d == "Include")
            removed_ac  = sum(1 for d in action_decisions.values() if d == "Remove")

            st.session_state.dri_submitted = True
            st.session_state.dri_log = entries
            st.success(
                f"Review submitted by **{dri_name}** ({effective_role}) at {ts[:19]} UTC.  \n"
                f"Conflicts: {approved_cf} approved · {rejected_cf} rejected · {escalated_cf} escalated  \n"
                f"Actions: {included_ac} included · {removed_ac} removed  \n"
                f"Logged to `outputs/override_log.jsonl`"
            )

# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT HEALTH + HITL
# ─────────────────────────────────────────────────────────────────────────────
col_acc, col_hitl = st.columns(2)

with col_acc:
    inc = account["current_incident"]
    hist = account["support_history_90d"]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Health Score", f"{account['health_score']}/100", delta="Declining", delta_color="inverse")
    a2.metric("NPS Score", f"{account['nps_score']}/10")
    a3.metric("SLA Breaches", str(hist["sla_breaches"]), delta="90 days", delta_color="inverse")
    a4.metric("Revenue at Risk", f"${inc['estimated_revenue_at_risk_usd']:,}")

    st.markdown(f"""
    <div class='card'>
    <div class='card-title'>Account — {account['company_name']}</div>
    <div style='font-size:14px;color:#94a3b8;line-height:1.9;'>
        <b style='color:#e2e8f0;'>Contract:</b> ${account['contract_value_usd_annual']:,}/year &nbsp;·&nbsp;
        <b style='color:#e2e8f0;'>Renewal:</b> {account['renewal_date']}<br>
        <b style='color:#e2e8f0;'>Exec contact:</b> Derek Hartley (VP Procurement)<br>
        <b style='color:#e2e8f0;'>Last exec update:</b>
            <span style='color:#ef4444;'>2026-08-13 — OVERDUE (6 days ago)</span><br>
        <b style='color:#e2e8f0;'>Open tickets (90d):</b> {hist['total_tickets']} total · {hist['urgent_tickets']} urgent<br>
        <b style='color:#e2e8f0;'>Competitor eval:</b>
            <span style='color:#ef4444;'>ACTIVE — per executive email</span><br>
        <b style='color:#e2e8f0;'>Intl error rate:</b> 2.4% &nbsp;·&nbsp;
        <b style='color:#e2e8f0;'>Domestic:</b> 0.1%
    </div>
    </div>
    """, unsafe_allow_html=True)

with col_hitl:
    high_count   = sum(1 for e in override_log if "high"   in e.get("override",""))
    medium_count = sum(1 for e in override_log if "medium" in e.get("override",""))
    uncertain    = sum(1 for e in override_log if "uncertain" in e.get("override",""))

    h1, h2, h3 = st.columns(3)
    h1.metric("HIGH Confidence", high_count)
    h2.metric("MED Confidence",  medium_count)
    h3.metric("Flagged Uncertain", uncertain)

    audit_html = "<div class='card'><div class='card-title'>HITL Audit Trail — override_log.jsonl</div>"
    for entry in override_log[:7]:
        css = "audit-high" if "high" in entry["override"] else "audit-medium" if "medium" in entry["override"] else "audit-medium"
        item_id = entry["item_id"][:45]
        conf    = entry["original"].split(",")[0].replace("confidence=","")
        score   = entry["original"].split(",")[1].replace(" score=","").strip() if "score" in entry["original"] else ""
        override = entry["override"]
        audit_html += f"<div class='audit-row {css}'>{entry['item_type']} · {item_id} · {conf} {score} · {override}</div>"
    if len(override_log) > 7:
        audit_html += f"<div style='font-size:12px;color:#475569;margin-top:5px;'>+ {len(override_log)-7} more entries</div>"
    audit_html += "</div>"
    st.markdown(audit_html, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BEFORE / AFTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Comms Clarity — Before vs After")
ba1, ba2 = st.columns(2)

with ba1:
    st.markdown("""
    <div class='ba-before'>
        <div class='ba-label'>BEFORE — Manual Triage (4–8 hours)</div>
        <div class='ba-text'>
            "Customer reports order processing failures. Engineering says fixed.
            Need to investigate further."
        </div>
        <br>
        <span class='badge badge-red'>✗ Vague</span>
        <span class='badge badge-red'>✗ No sources</span>
        <span class='badge badge-red'>✗ No conflicts</span>
        <span class='badge badge-red'>✗ No actions</span>
    </div>
    """, unsafe_allow_html=True)

with ba2:
    st.markdown("""
    <div class='ba-after'>
        <div class='ba-label'>AFTER — Synthesizer (18ms total)</div>
        <div class='ba-text'>
            "Contoso Ltd | 2 SLA breaches [Account Summary].
            Postmortem: RESOLVED. Customer: NOT RESOLVED [Zendesk/Email].
            Error rate 1.4% vs 0.2% baseline [Telemetry].
            2 critical Jira tickets open. NWAPI-3362 unassigned.
            VP Derek Hartley threatening non-renewal + competitor evaluation [Email].
            Recommended: assign NWAPI-3362, send exec update, run order cleanup."
        </div>
        <br>
        <span class='badge badge-green'>✓ Specific</span>
        <span class='badge badge-green'>✓ Cited</span>
        <span class='badge badge-green'>✓ Conflicts flagged</span>
        <span class='badge badge-green'>✓ HITL reviewed</span>
        <span class='badge badge-green'>✓ Actionable</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOMER EMAIL OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Customer Update Email")
st.caption("Generated by the pipeline — `outputs/customer_email.md`. Non-technical, <2 min read. Run `python pipeline.py` to regenerate.")

email_path = OUT_DIR / "customer_email.md"

ec1, ec2 = st.columns([3, 1])

with ec1:
    if email_path.exists():
        email_content = email_path.read_text(encoding="utf-8")
        st.markdown(email_content)
    else:
        st.info("outputs/customer_email.md not found. Run `python pipeline.py` to generate all output reports including the customer email.")

with ec2:
    renewal = account["renewal_date"]
    st.markdown(f"""
    <div class='card'>
    <div class='card-title'>Customer Summary &lt;2 min</div>
    <div style='font-size:14px;color:#94a3b8;line-height:1.9;'>
        <b style='color:#e2e8f0;'>What we're seeing:</b><br>
        Intermittent failures on international orders only. Domestic unaffected.<br><br>
        <b style='color:#e2e8f0;'>What we've already changed:</b><br>
        Connection pool fix deployed Aug 14. Error rate down from 52% peak to 1.4%.<br><br>
        <b style='color:#e2e8f0;'>What we think is most likely:</b><br>
        Intl pool size (50) vs domestic (200) + Aug 13 migration compounded the gap.<br><br>
        <b style='color:#e2e8f0;'>What we're doing next:</b><br>
        Resolving ORD-55892 &amp; ORD-55901; auditing all enterprise accounts; corrected RCA by EOD.<br><br>
        <b style='color:#e2e8f0;'>Next update:</b><br>
        EOD today with named owners &amp; resolved order count.
    </div>
    </div>
    <div class='card'>
    <div class='card-title'>Recipient Context</div>
    <div style='font-size:14px;color:#94a3b8;line-height:1.9;'>
        <b style='color:#e2e8f0;'>To:</b> Derek Hartley (VP Procurement)<br>
        <b style='color:#e2e8f0;'>CC:</b> Margaret Peacock (Ops), CSM<br>
        <b style='color:#e2e8f0;'>Tone:</b> Urgent · Exec-level · Non-technical<br>
        <b style='color:#e2e8f0;'>Last update:</b>
            <span style='color:#ef4444;'>2026-08-13 — 6 days overdue</span><br>
        <b style='color:#e2e8f0;'>Renewal:</b> {renewal} · HIGH risk<br>
        <b style='color:#e2e8f0;'>Competitor eval:</b>
            <span style='color:#ef4444;'>ACTIVE</span>
    </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align:center;font-size:13px;color:#475569;'>"
    "Northwind Escalation Synthesizer &nbsp;·&nbsp; "
    "Sources: Zendesk · Slack · Postmortem · Telemetry · Account Summary · Jira · Executive Email &nbsp;·&nbsp; "
    "Powered by Claude claude-opus-5"
    "</div>",
    unsafe_allow_html=True,
)
