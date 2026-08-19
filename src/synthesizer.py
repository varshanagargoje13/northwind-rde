"""Generate the three output reports from artifacts and detected conflicts."""

from datetime import datetime, timezone
from pathlib import Path

from .conflict_detector import Conflict

NOW = "2026-08-19"


def _cite(source: str) -> str:
    return f"[{source}]"


def generate_executive_summary(artifacts: list[dict], conflicts: list[Conflict]) -> str:
    zendesk = next(a for a in artifacts if a["source"] == "Zendesk")
    account = next(a for a in artifacts if a["source"] == "Account Summary")
    postmortem = next(a for a in artifacts if a["source"] == "Postmortem")
    telemetry = next(a for a in artifacts if a["source"] == "Telemetry")
    eng = next(a for a in artifacts if a["source"] == "Eng Status")
    jira = next(a for a in artifacts if a["source"] == "Jira")
    slack = next(a for a in artifacts if a["source"] == "Slack")

    open_jira = ", ".join(jira["critical_open_tickets"]) if jira["critical_open_tickets"] else "None"
    high_conflicts = [c for c in conflicts if c.severity == "HIGH"]
    med_conflicts = [c for c in conflicts if c.severity == "MEDIUM"]

    lines = [
        f"# Executive Escalation Summary — Northwind Order Processing Incident",
        f"**Generated:** {NOW}  ",
        f"**Incident:** INC-2026-0812  ",
        f"**Customer:** {account['customer']} ({account['tier']})  ",
        f"**Status:** ⚠️  CONFLICTED — see conflict report",
        "",
        "---",
        "",
        "## Situation at a Glance",
        "",
        f"Northwind's order processing system experienced a major outage that directly impacted "
        f"**{account['customer']}**, a ${account['contract_value_usd']:,}/year enterprise customer "
        f"renewing in {account['renewal_date']} with a **{account['renewal_risk']} renewal risk** "
        f"{_cite('Account Summary')}. The customer's executive sponsor ({account['executive_contact']}) "
        f"has been engaged {_cite('Account Summary')}.",
        "",
        "Engineering declared the incident **RESOLVED** on 2026-08-14 at 16:00 UTC "
        f"{_cite('Eng Status')} {_cite('Postmortem')}, but the customer is still actively "
        f"reporting failures as of today {_cite('Zendesk')}, live telemetry shows a degraded "
        f"error rate of {telemetry['current_error_rate_pct']}% against a 0.2% baseline "
        f"{_cite('Telemetry')}, and Jira ticket NWAPI-3362 for stuck orders is **Open and Unassigned** "
        f"{_cite('Jira')}.",
        "",
        "---",
        "",
        "## Incident Timeline (Best Estimate)",
        "",
        f"| When | Event | Source |",
        f"|---|---|---|",
        f"| 2026-08-11 18:00 UTC | First elevated error rates detected | {_cite('Slack')} {_cite('Telemetry')} |",
        f"| 2026-08-11 17:28 UTC | API Gateway v2.4.1 deployed | {_cite('Jira')} |",
        f"| 2026-08-12 14:00 UTC | SEV-1 declared; error rate hit 34% | {_cite('Slack')} {_cite('Telemetry')} |",
        f"| 2026-08-12 14:07 UTC | Zendesk ticket ZD-98741 opened by Contoso | {_cite('Zendesk')} |",
        f"| 2026-08-13 23:00 UTC | DB migration script ran in production | {_cite('Postmortem')} {_cite('Eng Status')} |",
        f"| 2026-08-14 01:00 UTC | Error rate spiked to 41-52% (second wave) | {_cite('Telemetry')} |",
        f"| 2026-08-14 16:00 UTC | Engineering declared resolution | {_cite('Eng Status')} |",
        f"| 2026-08-19 09:22 UTC | Customer still reporting failures on specific orders | {_cite('Zendesk')} |",
        "",
        "---",
        "",
        "## Impact",
        "",
        f"- **Customer health score:** {account['health_score']}/100 (declining) {_cite('Account Summary')}",
        f"- **Orders affected:** Claims range from {postmortem['orders_affected_claim']} to 60+ "
        f"across sources — not yet reconciled {_cite('Postmortem')} {_cite('Slack')} {_cite('Zendesk')}",
        f"- **Revenue at risk:** ${account['revenue_at_risk_usd']:,} (customer estimate) "
        f"vs ${postmortem['revenue_at_risk_usd']:,} (Postmortem) {_cite('Account Summary')} {_cite('Postmortem')}",
        f"- **Total API errors logged:** {telemetry['total_api_errors']:,} {_cite('Telemetry')}",
        f"- **SLA breaches in past 90 days:** {account['sla_breaches_90d']} (including this incident) {_cite('Account Summary')}",
        f"- **NPS score:** {account['nps_score']}/10 {_cite('Account Summary')}",
        "",
        "---",
        "",
        "## Root Cause Summary",
        "",
        "Three overlapping root causes have been identified across sources (see Conflict Report for discrepancies):",
        "",
        f"1. **API Gateway v2.4.1 connection leak** — connection pool exhausted under load "
        f"{_cite('Slack')} {_cite('Jira/NWAPI-3341')}",
        f"2. **DB migration script (migrate_orders_v12.sql)** — caused invalid index on `orders.status_idx`, "
        f"driving query latency to 8,000ms+ {_cite('Postmortem')} {_cite('Eng Status')} {_cite('Jira/NWAPI-3350')}",
        f"3. **Residual stuck orders** — cleanup job did not recover all affected orders after mitigation "
        f"{_cite('Jira/NWAPI-3362')} {_cite('Zendesk')}",
        "",
        "---",
        "",
        "## Data Conflicts Detected",
        "",
        f"**{len(high_conflicts)} HIGH** and **{len(med_conflicts)} MEDIUM** conflicts found across the 7 artifacts. "
        "See the full Conflict Report for details. Key issues:",
        "",
    ]

    for c in conflicts[:3]:
        lines.append(f"- **{c.severity} — {c.category}:** {c.description}")

    lines += [
        "",
        "---",
        "",
        "## Open Items Requiring Immediate Attention",
        "",
        f"| # | Item | Owner | Status |",
        f"|---|---|---|---|",
        f"| 1 | Investigate and remediate stuck orders ORD-55892, ORD-55901 | Unassigned | 🔴 Open {_cite('Jira')} {_cite('Zendesk')} |",
        f"| 2 | Reconcile true count of affected orders across all customers | Eng Lead | 🔴 Needed {_cite('Postmortem')} {_cite('Slack')} |",
        f"| 3 | Issue updated executive communication to Contoso (Derek Hartley) | Laura Callahan | 🔴 Overdue {_cite('Account Summary')} |",
        f"| 4 | Assign NWAPI-3362 to an engineer | Eng Lead | 🔴 Unassigned {_cite('Jira')} |",
        f"| 5 | Add index validation to migration checklist | Steven Buchanan | 🟡 Due Aug 23 {_cite('Postmortem')} |",
        f"| 6 | Implement DB connection pool circuit breaker | Nancy Davolio | 🟡 Due Aug 30 {_cite('Postmortem')} |",
        "",
        "---",
        "",
        f"*This summary was synthesized from 7 sources: Zendesk ZD-98741, Slack #incident-order-processing, "
        f"Postmortem INC-2026-0812, Production Telemetry, Account Summary ACC-00441, Jira NWAPI sprint 47, "
        f"and Eng Status Update (2026-08-14).*",
    ]

    return "\n".join(lines)


def generate_conflict_report(artifacts: list[dict], conflicts: list[Conflict]) -> str:
    lines = [
        "# Conflict Report — Cross-Artifact Analysis",
        f"**Generated:** {NOW}  ",
        f"**Incident:** INC-2026-0812  ",
        f"**Artifacts analyzed:** {len(artifacts)}  ",
        f"**Conflicts detected:** {len(conflicts)} ({sum(1 for c in conflicts if c.severity=='HIGH')} HIGH, "
        f"{sum(1 for c in conflicts if c.severity=='MEDIUM')} MEDIUM, "
        f"{sum(1 for c in conflicts if c.severity=='LOW')} LOW)",
        "",
        "---",
        "",
        "## Conflict Index",
        "",
    ]

    for i, c in enumerate(conflicts, 1):
        lines.append(f"{i}. [{c.severity}] {c.category}")

    lines += ["", "---", ""]

    for i, c in enumerate(conflicts, 1):
        severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(c.severity, "⚪")
        lines += [
            f"## Conflict {i}: {severity_icon} {c.severity} — {c.category}",
            "",
            f"**Summary:** {c.description}",
            "",
            "**Source breakdown:**",
        ]
        for d in c.details:
            lines.append(d)
        lines += [
            "",
            f"**Involved sources:** {', '.join(c.sources)}",
            "",
            "**Why this matters:** " + _conflict_implication(c),
            "",
            "---",
            "",
        ]

    lines += [
        "## Artifact Summary Table",
        "",
        "| Source | Incident Start Claim | Orders Affected | Resolution Status |",
        "|---|---|---|---|",
    ]

    for a in artifacts:
        start = a.get("incident_start_claim")
        start_str = start.strftime("%Y-%m-%d %H:%M UTC") if isinstance(start, datetime) else "—"
        orders = a.get("orders_affected_claim", "—")
        status = (a.get("resolution_status") or "—")[:60]
        lines.append(f"| {a['source']} | {start_str} | {orders} | {status} |")

    lines += [
        "",
        "---",
        "",
        "*Conflicts were detected by comparing normalized fields across all 7 artifact sources.*",
    ]

    return "\n".join(lines)


def generate_action_items(artifacts: list[dict], conflicts: list[Conflict]) -> str:
    account = next(a for a in artifacts if a["source"] == "Account Summary")
    jira = next(a for a in artifacts if a["source"] == "Jira")

    lines = [
        "# Prioritized Action Items — INC-2026-0812",
        f"**Generated:** {NOW}  ",
        f"**Customer:** {account['customer']} — {account['tier']} (Renewal: {account['renewal_date']}, Risk: {account['renewal_risk']})",
        "",
        "---",
        "",
        "## P0 — Immediate (Today)",
        "",
        f"### 1. Fix stuck orders ORD-55892 and ORD-55901",
        f"- **Why:** Customer is actively reporting these as broken. Incident is NOT resolved from their perspective.",
        f"- **Owner:** Unassigned (assign immediately)",
        f"- **Sources:** {_cite('Zendesk ZD-98741')} {_cite('Jira NWAPI-3362')} {_cite('Slack 2026-08-19')}",
        f"- **Action:** Assign NWAPI-3362. Run stuck-order cleanup job against all orders in PROCESSING state since 2026-08-11.",
        "",
        f"### 2. Send executive update to Derek Hartley (Contoso VP Procurement)",
        f"- **Why:** Last executive update was 2026-08-13. It has been 6 days with no communication. Renewal is HIGH risk.",
        f"- **Owner:** Laura Callahan (CSM)",
        f"- **Sources:** {_cite('Account Summary ACC-00441')} {_cite('Zendesk ZD-98741')}",
        f"- **Action:** Send RCA summary + remediation status. Offer goodwill credit discussion.",
        "",
        f"### 3. Audit all customers for stuck orders — not just Contoso",
        f"- **Why:** Postmortem says 3 enterprise customers affected. Only Contoso has reported stuck orders so far.",
        f"- **Owner:** Eng Lead (Andrew Fuller)",
        f"- **Sources:** {_cite('Postmortem')} {_cite('Slack')} {_cite('Account Summary')}",
        f"- **Action:** Query all orders in terminal/intermediate state since 2026-08-11 across all accounts.",
        "",
        "---",
        "",
        "## P1 — This Week",
        "",
        f"### 4. Reconcile true order impact count across all sources",
        f"- **Why:** Claims range from 23 to 60+. The real number is needed for accurate customer communication and SLA credit.",
        f"- **Owner:** Eng Lead + CSM",
        f"- **Sources:** {_cite('Postmortem')} {_cite('Zendesk')} {_cite('Slack')} {_cite('Jira')} {_cite('Telemetry')}",
        "",
        f"### 5. Resolve root cause timeline discrepancy",
        f"- **Why:** Sources disagree on whether the API gateway (Aug 11) or DB migration (Aug 13) was the primary trigger.",
        f"- **Owner:** Nancy Davolio + Steven Buchanan",
        f"- **Sources:** {_cite('Slack')} {_cite('Postmortem')} {_cite('Jira')} {_cite('Telemetry')}",
        f"- **Action:** Correlate telemetry timeline with gateway deployment and migration timestamps. Update postmortem.",
        "",
        f"### 6. Add index validation to migration pre-flight checklist",
        f"- **Owner:** Steven Buchanan — Due: 2026-08-23",
        f"- **Sources:** {_cite('Postmortem')} {_cite('Eng Status')}",
        "",
        f"### 7. Require manual approval gate for production DB migrations",
        f"- **Owner:** Andrew Fuller — Due: 2026-08-23",
        f"- **Sources:** {_cite('Postmortem')}",
        "",
        "---",
        "",
        "## P2 — This Sprint",
        "",
        f"### 8. Implement DB connection pool circuit breaker",
        f"- **Owner:** Nancy Davolio — Due: 2026-08-30",
        f"- **Sources:** {_cite('Postmortem')} {_cite('Jira NWAPI-3341')}",
        "",
        f"### 9. Add monitoring alert for invalid DB indexes",
        f"- **Owner:** Janet Leverling — Due: 2026-08-28",
        f"- **Sources:** {_cite('Postmortem')} {_cite('Eng Status')}",
        "",
        f"### 10. Add pre-migration dry-run environment",
        f"- **Owner:** Andrew Fuller — Due: 2026-09-06",
        f"- **Sources:** {_cite('Postmortem')}",
        "",
        "---",
        "",
        "## P3 — Account Health",
        "",
        f"### 11. Schedule emergency QBR with Contoso",
        f"- **Why:** Health score is {account['health_score']}/100 (declining). NPS is {account['nps_score']}/10. Two SLA breaches in 90 days. Renewal in Dec.",
        f"- **Owner:** Laura Callahan (CSM) + Robert King (TAM)",
        f"- **Sources:** {_cite('Account Summary ACC-00441')}",
        "",
        f"### 12. Prioritize FR-2201 (bulk order status export) for Contoso",
        f"- **Why:** Giving the customer tools to monitor their own order state would reduce support burden and improve trust.",
        f"- **Owner:** Product + Eng",
        f"- **Sources:** {_cite('Account Summary ACC-00441')}",
        "",
        "---",
        "",
        "## Conflict-Driven Items",
        "",
        "The following items were generated specifically because of cross-artifact conflicts:",
        "",
    ]

    for c in conflicts:
        if c.severity in ("HIGH", "MEDIUM"):
            lines.append(f"- **{c.category}** conflict: {c.description[:120]}...")

    lines += [
        "",
        "---",
        "",
        f"*Actions derived from: Zendesk ZD-98741, Slack #incident-order-processing, "
        f"Postmortem INC-2026-0812, Telemetry, Account Summary ACC-00441, Jira Sprint 47, Eng Status 2026-08-14.*",
    ]

    return "\n".join(lines)


def _conflict_implication(c: Conflict) -> str:
    implications = {
        "Timeline — Incident Start": (
            "Disagreement on start time affects SLA calculations, blame attribution, and "
            "whether the API gateway rollout (Aug 11) should be listed as a root cause. "
            "If the incident started Aug 11, the postmortem timeline is wrong."
        ),
        "Resolution Status": (
            "Engineering closing an incident while the customer still experiences failures "
            "is the most dangerous gap. It erodes trust, delays actual fixes, and "
            "risks the Contoso renewal."
        ),
        "Impact — Orders Affected": (
            "Accurate order counts are needed for SLA credit calculations, customer "
            "communication, and determining whether the cleanup job ran completely."
        ),
        "Root Cause": (
            "If the postmortem blames only the DB migration but the gateway rollout "
            "was the original trigger, the preventive actions will miss the actual "
            "root cause and the incident could recur."
        ),
        "Impact — Revenue at Risk": (
            "Revenue figures affect prioritization, escalation decisions, and "
            "any goodwill credits offered. A 2.4x variance between sources is material."
        ),
    }
    return implications.get(c.category, "Unresolved conflict may lead to incorrect decisions.")
