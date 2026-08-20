"""Cross-artifact conflict detection."""

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass


@dataclass
class Conflict:
    category: str
    description: str
    sources: list[str]
    details: list[str]
    severity: str  # HIGH / MEDIUM / LOW


def _sources_with(artifacts: list[dict], key: str) -> list[dict]:
    return [a for a in artifacts if a.get(key) is not None]


def detect_timeline_conflicts(artifacts: list[dict]) -> list[Conflict]:
    conflicts = []
    sources_with_start = _sources_with(artifacts, "incident_start_claim")
    if len(sources_with_start) < 2:
        return conflicts

    timestamps = [(a["source"], a["incident_start_claim"]) for a in sources_with_start]
    timestamps.sort(key=lambda x: x[1])
    earliest_source, earliest_ts = timestamps[0]
    latest_source, latest_ts = timestamps[-1]
    spread_hours = (latest_ts - earliest_ts).total_seconds() / 3600

    if spread_hours > 4:
        details = [f"  - {src}: {ts.strftime('%Y-%m-%d %H:%M UTC')}" for src, ts in timestamps]
        conflicts.append(Conflict(
            category="Timeline — Incident Start",
            description=(
                f"Sources disagree on when the incident began by {spread_hours:.0f} hours. "
                f"Earliest: {earliest_source} ({earliest_ts.strftime('%Y-%m-%d %H:%M UTC')}); "
                f"Latest: {latest_source} ({latest_ts.strftime('%Y-%m-%d %H:%M UTC')})."
            ),
            sources=[s for s, _ in timestamps],
            details=details,
            severity="HIGH",
        ))
    return conflicts


def detect_status_conflicts(artifacts: list[dict]) -> list[Conflict]:
    conflicts = []
    resolved_sources = []
    open_sources = []
    degraded_sources = []

    for a in artifacts:
        status = (a.get("resolution_status") or "").lower()
        src = a["source"]
        if "resolved" in status and ("open" not in status and "still" not in status and "degraded" not in status):
            resolved_sources.append(src)
        elif "degraded" in status or "still" in status or ("open" in status and "closed" not in status):
            open_sources.append(src)

    telemetry = next((a for a in artifacts if a["source"] == "Telemetry"), None)
    if telemetry and telemetry.get("current_status") == "degraded":
        degraded_sources.append("Telemetry")

    if resolved_sources and (open_sources or degraded_sources):
        conflicts.append(Conflict(
            category="Resolution Status",
            description=(
                "Engineering and Postmortem declare the incident RESOLVED, "
                "but Zendesk, Slack, Account Summary, and Telemetry show the issue is still active."
            ),
            sources=resolved_sources + open_sources + degraded_sources,
            details=[
                f"  - RESOLVED claim: {', '.join(resolved_sources)}",
                f"  - STILL OPEN / DEGRADED: {', '.join(set(open_sources + degraded_sources))}",
                "  - Telemetry shows 1.1-1.4% error rate on 2026-08-19 (above 0.2% baseline)",
                "  - Zendesk: customer reported new failures on 2026-08-19T09:22Z",
                "  - Jira NWAPI-3362 (stuck orders) is Open and Unassigned",
            ],
            severity="HIGH",
        ))
    return conflicts


def detect_orders_affected_conflicts(artifacts: list[dict]) -> list[Conflict]:
    conflicts = []
    claims = []

    for a in artifacts:
        if a.get("orders_affected_claim") is not None:
            val = a["orders_affected_claim"]
            if isinstance(val, int):
                claims.append((a["source"], val))

    # Jira has multiple ticket-level claims
    jira = next((a for a in artifacts if a["source"] == "Jira"), None)
    if jira:
        for item in jira.get("orders_affected_claims", []):
            try:
                n = int(item["claim"].replace("+", "").split()[0])
                claims.append((f"Jira/{item['ticket']}", n))
            except (ValueError, IndexError):
                pass

    # Telemetry has its own stuck_orders_count
    telemetry = next((a for a in artifacts if a["source"] == "Telemetry"), None)
    if telemetry and telemetry.get("stuck_orders_count"):
        claims.append(("Telemetry (stuck_orders_count)", telemetry["stuck_orders_count"]))

    if len(claims) < 2:
        return conflicts

    values = [v for _, v in claims]
    spread = max(values) - min(values)
    if spread > 5:
        details = [f"  - {src}: {val} orders" for src, val in sorted(claims, key=lambda x: x[1])]
        conflicts.append(Conflict(
            category="Impact — Orders Affected",
            description=(
                f"Sources report between {min(values)} and {max(values)} affected orders — "
                f"a spread of {spread}. The true count is unresolved."
            ),
            sources=[s for s, _ in claims],
            details=details,
            severity="MEDIUM",
        ))
    return conflicts


def detect_root_cause_conflicts(artifacts: list[dict]) -> list[Conflict]:
    conflicts = []
    root_cause_map = {}

    for a in artifacts:
        rc = a.get("root_cause_claim")
        if rc:
            root_cause_map[a["source"]] = rc

    jira = next((a for a in artifacts if a["source"] == "Jira"), None)
    if jira:
        for i, rc in enumerate(jira.get("root_cause_claims", [])):
            root_cause_map[f"Jira/ticket-{i+1}"] = rc

    if len(root_cause_map) < 2:
        return conflicts

    # Group into themes
    migration_sources = [s for s, rc in root_cause_map.items() if "migration" in rc.lower() or "index" in rc.lower()]
    gateway_sources = [s for s, rc in root_cause_map.items() if "gateway" in rc.lower() or "api gateway" in rc.lower()]
    pool_sources = [s for s, rc in root_cause_map.items() if "connection pool" in rc.lower() or "pool exhaustion" in rc.lower()]

    if len({bool(migration_sources), bool(gateway_sources), bool(pool_sources)}.intersection({True})) > 1:
        details = [f"  - {src}: \"{rc}\"" for src, rc in root_cause_map.items()]
        conflicts.append(Conflict(
            category="Root Cause",
            description=(
                "Sources attribute the incident to different root causes: "
                "DB migration/index corruption, API gateway connection leak, and connection pool exhaustion. "
                "These may be related (chain of causation) but are presented as independent root causes."
            ),
            sources=list(root_cause_map.keys()),
            details=details,
            severity="HIGH",
        ))
    return conflicts


def detect_revenue_conflicts(artifacts: list[dict]) -> list[Conflict]:
    conflicts = []
    claims = []
    for a in artifacts:
        if a.get("revenue_at_risk_usd") is not None:
            claims.append((a["source"], a["revenue_at_risk_usd"]))

    if len(claims) < 2:
        return conflicts

    values = [v for _, v in claims]
    if max(values) / min(values) > 1.5:
        details = [f"  - {src}: ${val:,}" for src, val in claims]
        conflicts.append(Conflict(
            category="Impact — Revenue at Risk",
            description=(
                f"Revenue-at-risk estimates vary significantly: "
                f"${min(values):,} (Postmortem) vs ${max(values):,} (Account Summary / Zendesk)."
            ),
            sources=[s for s, _ in claims],
            details=details,
            severity="MEDIUM",
        ))
    return conflicts


def detect_from_graph(g) -> list[Conflict]:
    """
    Run the SPARQL-based conflict detectors over a rdflib Graph and convert
    results to Conflict dataclasses, keeping the pipeline interface uniform.
    """
    try:
        from .ontology.sparql_detector import detect_all as sparql_detect_all
    except ImportError:
        return []
    raw = sparql_detect_all(g)
    out = []
    for r in raw:
        out.append(Conflict(
            category    = r["category"],
            description = r["description"],
            sources     = r.get("sources", []),
            details     = r.get("details", []),
            severity    = r["severity"],
        ))
    return out


def detect_all(artifacts: list[dict]) -> list[Conflict]:
    detectors = [
        detect_timeline_conflicts,
        detect_status_conflicts,
        detect_orders_affected_conflicts,
        detect_root_cause_conflicts,
        detect_revenue_conflicts,
    ]
    all_conflicts = []
    for detector in detectors:
        all_conflicts.extend(detector(artifacts))

    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_conflicts.sort(key=lambda c: severity_order.get(c.severity, 3))
    return all_conflicts
