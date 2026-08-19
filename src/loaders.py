"""Artifact loaders — each returns a normalized dict with a 'source' key."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_zendesk(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "source": "Zendesk",
        "ticket_id": raw["ticket_id"],
        "status": raw["status"],
        "priority": raw["priority"],
        "reported_at": _parse_iso(raw["created_at"]),
        "incident_start_claim": _parse_iso("2026-08-12T14:00:00Z"),  # "since Tuesday Aug 12 at 2pm"
        "orders_affected_claim": 47,
        "root_cause_claim": "recent infrastructure change (unspecified)",
        "resolution_status": "open — customer still reporting issues as of 2026-08-19",
        "sla_breach": raw["sla_breach"],
        "customer": raw["requester"]["organization"],
        "revenue_at_risk_usd": None,
        "comments": raw["comments"],
        "raw": raw,
    }


def load_slack(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    messages = raw["messages"]
    return {
        "source": "Slack",
        "channel": raw["channel"],
        "incident_start_claim": _parse_iso("2026-08-11T18:00:00Z"),  # "first noticed 6pm Monday"
        "orders_affected_claim": 60,  # "60+ orders affected"
        "root_cause_claim": "API gateway v2.4.1 connection leak (per janet.leverling & steven.buchanan)",
        "resolution_status": "mitigated — but Contoso still reporting issues 2026-08-19",
        "key_contributors": list({m["user"] for m in messages}),
        "message_count": len(messages),
        "raw": raw,
    }


def load_postmortem(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    incident_start = _parse_iso("2026-08-13T23:00:00Z")
    orders_match = re.search(r"(\d+) orders? (?:stuck|impacted|directly)", text)
    orders_count = int(orders_match.group(1)) if orders_match else None
    revenue_match = re.search(r"\$([0-9,]+)", text)
    revenue = int(revenue_match.group(1).replace(",", "")) if revenue_match else None

    return {
        "source": "Postmortem",
        "status": "approved",
        "incident_start_claim": incident_start,
        "orders_affected_claim": orders_count,
        "root_cause_claim": "DB migration script migrate_orders_v12.sql caused index corruption on orders.status_idx",
        "resolution_status": "resolved — 2026-08-14T16:00:00Z",
        "resolution_time": _parse_iso("2026-08-14T16:00:00Z"),
        "revenue_at_risk_usd": revenue,
        "duration_hours": 17,
        "customers_affected": 3,
        "action_items": [
            "Add index validation step to migration checklist (Steven Buchanan, due Aug 23)",
            "Implement connection pool circuit breaker (Nancy Davolio, due Aug 30)",
            "Add pre-migration dry-run environment (Andrew Fuller, due Sep 6)",
        ],
        "raw_text": text,
    }


def load_telemetry(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = raw["metrics"]
    timeline = metrics["error_rate_timeline"]

    first_anomaly = _parse_iso(metrics["first_anomaly_detected"])
    peak_time = _parse_iso(metrics["peak_impact_time"])
    mitigation_time = _parse_iso(metrics["mitigation_time"])
    peak_error_rate = max(e["error_rate_pct"] for e in timeline)

    # Check if currently degraded
    recent = [e for e in timeline if _parse_iso(e["timestamp"]) >= _parse_iso("2026-08-19T00:00:00Z")]
    current_error_rate = recent[-1]["error_rate_pct"] if recent else None

    return {
        "source": "Telemetry",
        "incident_start_claim": first_anomaly,
        "peak_error_rate_pct": peak_error_rate,
        "peak_time": peak_time,
        "mitigation_time": mitigation_time,
        "stuck_orders_count": metrics["stuck_orders_count"],
        "connection_pool_max": metrics["db_connection_pool"]["max_connections"],
        "connection_wait_timeouts": metrics["db_connection_pool"]["connection_wait_timeouts"],
        "current_status": raw["metrics"]["current_status"],
        "current_error_rate_pct": current_error_rate,
        "resolution_status": "degraded — telemetry shows 1.1-1.4% error rate as of 2026-08-19",
        "total_api_errors": sum(e["error_count"] for e in metrics["affected_endpoints"]),
        "raw": raw,
    }


def load_account_summary(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    inc = raw["current_incident"]
    return {
        "source": "Account Summary",
        "customer": raw["company_name"],
        "tier": raw["tier"],
        "contract_value_usd": raw["contract_value_usd_annual"],
        "renewal_date": raw["renewal_date"],
        "renewal_risk": raw["renewal_risk"],
        "health_score": raw["health_score"],
        "orders_affected_claim": inc["orders_flagged_as_stuck"],
        "revenue_at_risk_usd": inc["estimated_revenue_at_risk_usd"],
        "executive_escalation": inc["executive_escalation"],
        "executive_contact": inc["executive_contacted"],
        "nps_score": raw["nps_score"],
        "sla_breaches_90d": raw["support_history_90d"]["sla_breaches"],
        "resolution_status": "open — executive escalation active",
        "raw": raw,
    }


def load_jira(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    tickets = raw["tickets"]

    open_tickets = [t for t in tickets if t["status"] not in ("Done",)]
    critical_open = [t for t in open_tickets if t["priority"] in ("Critical", "High")]

    root_causes = list({t["root_cause_hypothesis"] for t in tickets if t.get("root_cause_hypothesis")})

    impact_claims = []
    for t in tickets:
        if t.get("estimated_orders_impacted"):
            impact_claims.append({"ticket": t["id"], "claim": t["estimated_orders_impacted"]})

    return {
        "source": "Jira",
        "total_tickets": len(tickets),
        "open_tickets": len(open_tickets),
        "critical_open_tickets": [t["id"] for t in critical_open],
        "root_cause_claims": root_causes,
        "orders_affected_claims": impact_claims,
        "resolution_status": f"{len(open_tickets)} open tickets — NWAPI-3362 (stuck orders) unassigned",
        "known_affected_orders": ["ORD-55892", "ORD-55901"],
        "raw": raw,
    }


def load_eng_status(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {
        "source": "Eng Status",
        "declared_status": "RESOLVED",
        "resolution_time_claim": _parse_iso("2026-08-14T16:00:00Z"),
        "incident_start_claim": _parse_iso("2026-08-13T23:00:00Z"),
        "orders_affected_claim": 23,
        "root_cause_claim": "DB migration script caused invalid index; connection pool exhaustion",
        "resolution_status": "resolved — engineering has closed this incident",
        "preventive_actions": 4,
        "raw_text": text,
    }


def load_all(data_dir: Path) -> list[dict]:
    loaders = [
        (data_dir / "zendesk_ticket.json", load_zendesk),
        (data_dir / "slack_thread.json", load_slack),
        (data_dir / "postmortem.md", load_postmortem),
        (data_dir / "telemetry.json", load_telemetry),
        (data_dir / "account_summary.json", load_account_summary),
        (data_dir / "jira_tickets.json", load_jira),
        (data_dir / "eng_status.md", load_eng_status),
    ]
    artifacts = []
    for path, loader in loaders:
        artifact = loader(path)
        artifact["file"] = path.name
        artifacts.append(artifact)
    return artifacts
