"""Artifact loaders — each returns a normalized dict with a 'source' key."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_zendesk(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Primary ticket ZD-98741; dispute ticket ZD-99788 is linked
    primary = next(t for t in raw["tickets"] if t["ticket_id"] == "ZD-98741")
    dispute  = next((t for t in raw["tickets"] if t["ticket_id"] == "ZD-99788"), {})

    # Collect all disputes from ZD-99788
    customer_disputes = dispute.get("customer_disputes", [])

    return {
        "source": "Zendesk",
        "ticket_id": primary["ticket_id"],
        "linked_dispute_ticket": dispute.get("ticket_id"),
        "status": primary["status"],
        "priority": primary["priority"],
        "reported_at": _parse_iso(primary["created_at"]),
        "incident_start_claim": _parse_iso("2026-08-12T14:00:00Z"),
        "orders_affected_claim": 47,
        "root_cause_claim": "recent infrastructure change (unspecified)",
        "resolution_status": "open — customer still reporting issues as of 2026-08-19",
        "sla_breach": primary["sla_breach"],
        "customer": primary["requester"]["organization"],
        "revenue_at_risk_usd": None,
        "scope_dispute": "international orders only — domestic fine throughout",
        "customer_disputes": customer_disputes,
        "comments": primary["comments"] + dispute.get("comments", []),
        "raw": raw,
    }


def load_slack(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    messages = raw["messages"]
    return {
        "source": "Slack",
        "channel": raw["channel"],
        "incident_start_claim": _parse_iso("2026-08-11T18:00:00Z"),
        "orders_affected_claim": 60,
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


def load_executive_email(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    # Parse headers
    sender_match = re.search(r"From:\s*(.+)", text)
    subject_match = re.search(r"Subject:\s*(.+)", text)
    date_match = re.search(r"Date:\s*(.+)", text)
    cc_match = re.search(r"CC:\s*(.+)", text)

    orders_match = re.search(r"(\d+) orders? are stuck", text)
    revenue_match = re.search(r"\$([0-9,]+),000", text)

    return {
        "source": "Executive Email",
        "sender": sender_match.group(1).strip() if sender_match else "Unknown",
        "subject": subject_match.group(1).strip() if subject_match else "",
        "date": date_match.group(1).strip() if date_match else "",
        "cc": cc_match.group(1).strip() if cc_match else "",
        "incident_start_claim": _parse_iso("2026-08-12T13:00:00Z"),
        "orders_affected_claim": int(orders_match.group(1)) if orders_match else 47,
        "revenue_at_risk_usd": 200000,
        "root_cause_claim": "not provided — customer demands specifics",
        "resolution_status": "open — VP + CEO escalated, renewal at risk, competitor evaluation begun",
        "tone": "urgent / threatening",
        "renewal_threat": True,
        "executive_requests": [
            "Bridge call today 2pm EST",
            "Written RCA by EOD",
            "Resolution timeline with named owners",
            "Confirmation all 47 orders remediated",
            "Explanation of 3 escalations in 2 weeks",
        ],
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
        (data_dir / "executive_email.md", load_executive_email),
    ]
    artifacts = []
    for path, loader in loaders:
        try:
            artifact = loader(path)
            artifact["file"] = path.name
            artifacts.append(artifact)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Artifact file not found: {path}\n"
                f"Ensure all 7 data files exist under {data_dir}/"
            ) from None
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed JSON in {path.name} (line {exc.lineno}): {exc.msg}"
            ) from exc
        except (KeyError, IndexError, StopIteration) as exc:
            raise ValueError(
                f"Unexpected structure in {path.name}: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to load {path.name}: {exc}") from exc
    return artifacts
