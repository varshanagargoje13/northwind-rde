"""
Consolidates 7 loaded artifact dicts into a single normalized state dict
and persists it to outputs/consolidated_state.json before analysis runs.

This is step 2 of the pipeline: load → consolidate → analyse → review → report.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────────

def _iso(val) -> str:
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else ""


def _find(artifacts: list[dict], source: str) -> dict:
    return next((a for a in artifacts if a["source"] == source), {})


# ── main consolidation ─────────────────────────────────────────────────────────

def consolidate(artifacts: list[dict]) -> dict:
    """
    Merge 7 artifact dicts into one unified state.

    The state captures:
    - Per-source claims on incident start time, order counts, root cause,
      resolution status, and revenue at risk
    - Pre-computed conflict_signals (boolean flags) that highlight
      cross-source disagreements for fast downstream analysis
    - A unified chronological timeline built from all sources
    - Normalised customer, engineering, and communications sections

    Returns a plain dict — JSON-serialisable (datetimes converted to ISO strings).
    """
    acc   = _find(artifacts, "Account Summary")
    tele  = _find(artifacts, "Telemetry")
    jira  = _find(artifacts, "Jira")
    zd    = _find(artifacts, "Zendesk")
    slack = _find(artifacts, "Slack")
    pm    = _find(artifacts, "Postmortem")
    email = _find(artifacts, "Executive Email")

    # ── per-source start-time claims ───────────────────────────────────────
    start_claims: dict[str, str] = {}
    for a in artifacts:
        sc = a.get("incident_start_claim")
        if sc:
            start_claims[a["source"]] = _iso(sc)

    sorted_starts = sorted(start_claims.values())
    start_span_hours: float = 0.0
    if len(sorted_starts) >= 2:
        try:
            t0 = datetime.fromisoformat(sorted_starts[0])
            t1 = datetime.fromisoformat(sorted_starts[-1])
            start_span_hours = round((t1 - t0).total_seconds() / 3600, 1)
        except Exception:
            pass

    # ── per-source orders-affected claims ──────────────────────────────────
    order_claims: dict[str, object] = {}
    for a in artifacts:
        oc = a.get("orders_affected_claim")
        if oc is not None:
            order_claims[a["source"]] = oc

    numeric_orders = [v for v in order_claims.values() if isinstance(v, (int, float))]

    pm_orders       = pm.get("orders_affected_claim") or 0
    customer_orders = zd.get("orders_affected_claim") or 0
    order_gap       = abs(customer_orders - pm_orders)

    # ── per-source root-cause claims ───────────────────────────────────────
    rc_claims: dict[str, str] = {}
    for a in artifacts:
        rc = a.get("root_cause_claim")
        if rc:
            rc_claims[a["source"]] = rc

    jira_rc       = jira.get("root_cause_claims", [])
    all_rc        = list(rc_claims.values()) + jira_rc
    distinct_rc   = len({s.lower()[:35] for s in all_rc})

    # ── per-source resolution status ───────────────────────────────────────
    resolution_by_source: dict[str, str] = {}
    for a in artifacts:
        rs = a.get("resolution_status")
        if rs:
            resolution_by_source[a["source"]] = rs

    # ── per-source revenue at risk ─────────────────────────────────────────
    revenue_claims: dict[str, object] = {}
    for a in artifacts:
        rv = a.get("revenue_at_risk_usd")
        if rv is not None:
            revenue_claims[a["source"]] = rv

    # ── conflict signal flags ──────────────────────────────────────────────
    pm_resolved = "resolved" in pm.get("resolution_status", "").lower()
    any_open    = any(
        "open" in a.get("resolution_status", "").lower()
        for a in artifacts if a["source"] != "Postmortem"
    )

    conflict_signals = {
        "status_mismatch":           pm_resolved and any_open,
        "order_count_mismatch":      len(set(numeric_orders)) > 1,
        "root_cause_mismatch":       distinct_rc > 2,
        "start_time_span_hours":     start_span_hours,
        "order_count_gap":           order_gap,
        "postmortem_vs_customer_gap": order_gap,
        "unassigned_critical_ticket": "NWAPI-3362" in jira.get("critical_open_tickets", []),
        "renewal_threat_active":      email.get("renewal_threat", False),
        "sla_breached":               bool(zd.get("sla_breach")),
    }

    # ── unified chronological timeline ─────────────────────────────────────
    events: list[dict] = []

    _ev = lambda ts, src, evt: events.append({"ts": _iso(ts), "source": src, "event": evt})

    if tele.get("incident_start_claim"):
        _ev(tele["incident_start_claim"], "Telemetry",  "First anomaly detected")
    if slack.get("incident_start_claim"):
        _ev(slack["incident_start_claim"], "Slack",     "Connection pool exhaustion begins (gateway v2.4.1)")
    if pm.get("incident_start_claim"):
        _ev(pm["incident_start_claim"],   "Postmortem", "DB migration index corruption window opens")
    if tele.get("peak_time"):
        _ev(tele["peak_time"], "Telemetry",
            f"Peak error rate reached: {tele.get('peak_error_rate_pct', '?')}%")
    if tele.get("mitigation_time"):
        _ev(tele["mitigation_time"], "Telemetry",       "Initial mitigation applied (pool size bump)")
    if pm.get("resolution_time"):
        _ev(pm["resolution_time"], "Postmortem",        "Postmortem declares incident RESOLVED")

    events.sort(key=lambda e: e["ts"])

    # ── assembled state ────────────────────────────────────────────────────
    return {
        "consolidated_at": datetime.now(timezone.utc).isoformat(),
        "source_count":    len(artifacts),
        "sources_loaded":  [a["source"] for a in artifacts],

        "incident": {
            "start_claims_by_source":       start_claims,
            "start_time_span_hours":        start_span_hours,
            "resolution_status_by_source":  resolution_by_source,
            "current_status":               tele.get("current_status"),
            "current_error_rate_pct":       tele.get("current_error_rate_pct"),
            "peak_error_rate_pct":          tele.get("peak_error_rate_pct"),
            "duration_hours":               pm.get("duration_hours"),
            "customers_affected_postmortem":pm.get("customers_affected"),
            "mitigation_time":              _iso(tele.get("mitigation_time", "")),
            "resolution_time_postmortem":   _iso(pm.get("resolution_time", "")),
        },

        "orders_impact": {
            "claims_by_source":     order_claims,
            "min_claim":            min(numeric_orders) if numeric_orders else None,
            "max_claim":            max(numeric_orders) if numeric_orders else None,
            "stuck_orders_telemetry": tele.get("stuck_orders_count"),
            "known_stuck_order_ids": jira.get("known_affected_orders", []),
            "postmortem_count":     pm_orders,
            "customer_claimed_count": customer_orders,
            "gap":                  order_gap,
        },

        "root_cause": {
            "claims_by_source":  rc_claims,
            "jira_hypotheses":   jira_rc,
            "distinct_claim_count": distinct_rc,
        },

        "revenue_at_risk": {
            "claims_by_source": revenue_claims,
            "max_usd":          max((v for v in revenue_claims.values()
                                     if isinstance(v, (int, float))), default=None),
        },

        "customer": {
            "name":                acc.get("customer"),
            "tier":                acc.get("tier"),
            "contract_value_usd":  acc.get("contract_value_usd"),
            "renewal_date":        acc.get("renewal_date"),
            "renewal_risk":        acc.get("renewal_risk"),
            "health_score":        acc.get("health_score"),
            "nps_score":           acc.get("nps_score"),
            "sla_breaches_90d":    acc.get("sla_breaches_90d"),
            "revenue_at_risk_usd": acc.get("revenue_at_risk_usd"),
            "executive_escalation":acc.get("executive_escalation"),
            "executive_contact":   acc.get("executive_contact"),
            "renewal_threat_stated": email.get("renewal_threat", False),
            "executive_requests":  email.get("executive_requests", []),
            "email_tone":          email.get("tone"),
        },

        "engineering": {
            "open_jira_count":           jira.get("open_tickets"),
            "critical_open_ticket_ids":  jira.get("critical_open_tickets", []),
            "known_affected_orders":     jira.get("known_affected_orders", []),
            "total_api_errors":          tele.get("total_api_errors"),
            "connection_pool_max":       tele.get("connection_pool_max"),
            "connection_wait_timeouts":  tele.get("connection_wait_timeouts"),
            "postmortem_action_items":   pm.get("action_items", []),
        },

        "communications": {
            "executive_email_subject":   email.get("subject"),
            "executive_email_sender":    email.get("sender"),
            "executive_email_cc":        email.get("cc"),
            "slack_channel":             slack.get("channel"),
            "slack_contributors":        slack.get("key_contributors", []),
            "slack_message_count":       slack.get("message_count"),
            "zendesk_primary_ticket":    zd.get("ticket_id"),
            "zendesk_sla_breach":        zd.get("sla_breach"),
        },

        "conflict_signals": conflict_signals,
        "timeline":         events,
    }


def save(state: dict, out_dir: Path) -> Path:
    """Write consolidated state to outputs/consolidated_state.json."""
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "consolidated_state.json"
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    return path
