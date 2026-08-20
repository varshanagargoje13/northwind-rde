"""
Report generator — produces the 3 markdown output reports from
normalized artifacts and detected conflicts, with full source citations.
Renamed from synthesizer.py; rule-based fallback when AI is unavailable.
"""

from datetime import datetime
from .conflict_detector import Conflict

NOW = "2026-08-19"


def _cite(source: str) -> str:
    return f"[{source}]"


def _f(c, field: str, default=""):
    """Safely read a field from either a Conflict dataclass or a plain dict."""
    if isinstance(c, dict):
        return c.get(field, default)
    return getattr(c, field, default)


def generate_executive_summary(artifacts: list[dict], conflicts: list) -> str:
    zendesk  = next(a for a in artifacts if a["source"] == "Zendesk")
    account  = next(a for a in artifacts if a["source"] == "Account Summary")
    postmortem = next(a for a in artifacts if a["source"] == "Postmortem")
    telemetry  = next(a for a in artifacts if a["source"] == "Telemetry")
    email_art  = next((a for a in artifacts if a["source"] == "Executive Email"), {})
    jira       = next(a for a in artifacts if a["source"] == "Jira")

    open_jira = ", ".join(jira["critical_open_tickets"]) if jira["critical_open_tickets"] else "None"

    high_conflicts = [c for c in conflicts if _f(c, "severity") == "HIGH"]
    med_conflicts  = [c for c in conflicts if _f(c, "severity") == "MEDIUM"]

    lines = [
        "# Executive Escalation Summary — Northwind Order Processing Incident",
        f"**Generated:** {NOW}  ",
        f"**Incident:** INC-2026-0812  ",
        f"**Customer:** {account['customer']} ({account['tier']})  ",
        "**Status:** CONFLICTED — see Conflict Report",
        "",
        "---",
        "",
        "## Situation at a Glance",
        "",
        f"Northwind's order processing system experienced a major outage directly impacting "
        f"**{account['customer']}**, a ${account['contract_value_usd']:,}/year enterprise customer "
        f"renewing in {account['renewal_date']} with **{account['renewal_risk']} renewal risk** "
        f"{_cite('Account Summary')}. The customer's VP of Procurement and CEO have been escalated "
        f"with a formal renewal threat {_cite('Executive Email')}.",
        "",
        "Engineering declared the incident **RESOLVED** on 2026-08-14 "
        f"{_cite('Postmortem')}, but the customer is still reporting failures {_cite('Zendesk')}, "
        f"telemetry shows a degraded error rate of {telemetry['current_error_rate_pct']}% "
        f"(baseline 0.2%) {_cite('Telemetry')}, and Jira NWAPI-3362 is **Open and Unassigned** "
        f"{_cite('Jira')}.",
        "",
        "---",
        "",
        "## Incident Timeline (Best Estimate)",
        "",
        "| When | Event | Source |",
        "|---|---|---|",
        f"| 2026-08-11 18:00 UTC | First elevated error rates detected | {_cite('Slack')} {_cite('Telemetry')} |",
        f"| 2026-08-11 17:28 UTC | API Gateway v2.4.1 deployed | {_cite('Jira')} |",
        f"| 2026-08-12 14:00 UTC | SEV-1 declared; error rate hit 34% | {_cite('Slack')} {_cite('Telemetry')} |",
        f"| 2026-08-12 14:07 UTC | Zendesk ticket ZD-98741 opened by Contoso | {_cite('Zendesk')} |",
        f"| 2026-08-13 09:15 UTC | VP escalation email sent, CEO CC'd | {_cite('Executive Email')} |",
        f"| 2026-08-13 23:00 UTC | DB migration script ran in production | {_cite('Postmortem')} |",
        f"| 2026-08-14 16:00 UTC | Engineering declared resolution | {_cite('Postmortem')} |",
        f"| 2026-08-19 09:22 UTC | Customer still reporting failures on specific orders | {_cite('Zendesk')} |",
        "",
        "---",
        "",
        "## Impact",
        "",
        f"- **Customer health score:** {account['health_score']}/100 (declining) {_cite('Account Summary')}",
        f"- **NPS:** {account['nps_score']}/10 {_cite('Account Summary')}",
        f"- **Orders affected:** Claims range from {postmortem['orders_affected_claim']} to 60+ — unreconciled "
        f"{_cite('Postmortem')} {_cite('Slack')} {_cite('Zendesk')} {_cite('Executive Email')}",
        f"- **Revenue at risk:** ${account['revenue_at_risk_usd']:,} (customer) vs "
        f"${postmortem['revenue_at_risk_usd']:,} (Postmortem) {_cite('Account Summary')} {_cite('Postmortem')}",
        f"- **Total API errors logged:** {telemetry['total_api_errors']:,} {_cite('Telemetry')}",
        f"- **SLA breaches (90d):** {account['sla_breaches_90d']} {_cite('Account Summary')}",
        f"- **Renewal threatened:** YES — VP + CEO escalated, competitor eval underway {_cite('Executive Email')}",
        "",
        "---",
        "",
        "## Root Cause Summary",
        "",
        f"1. **API Gateway v2.4.1 connection leak** — connection pool exhausted under load "
        f"{_cite('Slack')} {_cite('Jira')}",
        f"2. **DB migration script** — caused invalid index on `orders.status_idx`, "
        f"driving query latency to 8,000ms+ {_cite('Postmortem')} {_cite('Jira')}",
        f"3. **Residual stuck orders** — cleanup job did not recover all affected orders "
        f"{_cite('Jira')} {_cite('Zendesk')}",
        "",
        "---",
        "",
        "## Data Conflicts Detected",
        "",
        f"**{len(high_conflicts)} HIGH** and **{len(med_conflicts)} MEDIUM** conflicts found. "
        "Key issues:",
        "",
    ]

    for c in conflicts[:3]:
        lines.append(f"- **{_f(c, 'severity')} — {_f(c, 'category')}:** {_f(c, 'description')}")

    lines += [
        "",
        "---",
        "",
        "## Open Items Requiring Immediate Attention",
        "",
        "| # | Item | Owner | Status |",
        "|---|---|---|---|",
        f"| 1 | Fix stuck orders ORD-55892, ORD-55901 | Unassigned | OPEN {_cite('Jira')} {_cite('Zendesk')} |",
        f"| 2 | Send executive update to VP Derek Hartley | Laura Callahan (CSM) | OVERDUE {_cite('Executive Email')} |",
        f"| 3 | Audit all customers for stuck orders | Eng Lead | NEEDED {_cite('Postmortem')} |",
        f"| 4 | Assign NWAPI-3362 to engineer | Eng Lead | UNASSIGNED {_cite('Jira')} |",
        f"| 5 | Add index validation to migration checklist | Steven Buchanan | Due Aug 23 {_cite('Postmortem')} |",
        f"| 6 | Implement DB connection pool circuit breaker | Nancy Davolio | Due Aug 30 {_cite('Postmortem')} |",
        "",
        "---",
        "",
        f"*Synthesized from 7 sources: Zendesk ZD-98741, Slack #incident-order-processing, "
        f"Postmortem INC-2026-0812, Production Telemetry, Account Summary ACC-00441, "
        f"Jira Sprint 47, Executive Email (Derek Hartley, 2026-08-13).*",
    ]
    return "\n".join(lines)


def generate_conflict_report(artifacts: list[dict], conflicts: list) -> str:
    lines = [
        "# Conflict Report — Cross-Artifact Analysis",
        f"**Generated:** {NOW}  ",
        f"**Incident:** INC-2026-0812  ",
        f"**Artifacts analyzed:** {len(artifacts)}  ",
        f"**Conflicts detected:** {len(conflicts)}",
        "",
        "---",
        "",
        "## Conflict Index",
        "",
    ]


    for i, c in enumerate(conflicts, 1):
        lines.append(f"{i}. [{_f(c, 'severity')}] {_f(c, 'category')}")

    lines += ["", "---", ""]

    for i, c in enumerate(conflicts, 1):
        sev  = _f(c, "severity")
        cat  = _f(c, "category")
        icon = {"HIGH": "[HIGH]", "MEDIUM": "[MED]", "LOW": "[LOW]"}.get(sev, "")
        lines += [
            f"## Conflict {i}: {icon} {sev} — {cat}",
            "",
            f"**Summary:** {_f(c, 'description')}",
            "",
            "**Source breakdown:**",
        ]
        for d in _f(c, "details", []):
            lines.append(f"  {d.strip()}" if d.strip() else "")
        lines += [
            "",
            f"**Involved sources:** {', '.join(_f(c, 'sources', []))}",
            "",
            f"**Why this matters:** {_f(c, 'implication') or 'Unresolved conflict may lead to incorrect decisions.'}",
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
        status = (a.get("resolution_status") or "—")[:65]
        lines.append(f"| {a['source']} | {start_str} | {orders} | {status} |")

    lines += ["", "---", "", "*Conflicts detected by comparing normalized fields across all 7 artifacts.*"]
    return "\n".join(lines)


def generate_customer_email(artifacts: list[dict], conflicts: list) -> str:
    """Non-technical customer-facing email — <2 min read, plain language, no jargon."""
    account   = next(a for a in artifacts if a["source"] == "Account Summary")
    zendesk   = next(a for a in artifacts if a["source"] == "Zendesk")
    telemetry = next(a for a in artifacts if a["source"] == "Telemetry")
    jira      = next(a for a in artifacts if a["source"] == "Jira")
    email_art = next((a for a in artifacts if a["source"] == "Executive Email"), {})

    csm       = account.get("csm", "Laura Callahan")
    tam       = account.get("tam", account.get("technical_account_manager", "Robert King"))
    company   = account["customer"]
    renewal   = account["renewal_date"]
    err_rate  = telemetry.get("current_error_rate_pct", "1.4")
    stuck_ord = ", ".join(jira.get("known_affected_orders", ["ORD-55892", "ORD-55901"]))

    high_conflicts = [c for c in conflicts if _f(c, "severity") == "HIGH"]

    lines = [
        "# Customer Update Email — INC-2026-0812",
        f"**Generated:** {NOW}  ",
        f"**Report type:** Customer-facing (non-technical, <2 min read)  ",
        "",
        "---",
        "",
        "```",
        f"To:      Derek Hartley <d.hartley@contoso-ltd.com>",
        f"CC:      Margaret Peacock <m.peacock@contoso-ltd.com>; {csm} (CSM)",
        f"From:    {csm} — Northwind Enterprise Support",
        f"Date:    {NOW}",
        f"Subject: [UPDATE] Order Processing — {company} / INC-2026-0812",
        "```",
        "",
        "---",
        "",
        f"Hi Derek,",
        "",
        f"Thank you for your continued patience on the order processing issue affecting {company}. "
        f"Here is a concise update — we will keep it brief and jargon-free.",
        "",
        "---",
        "",
        "## What We Are Seeing",
        "",
        f"Intermittent failures on **international order submissions** since Aug 12. "
        f"Domestic orders are unaffected throughout. "
        f"Two specific orders ({stuck_ord}) are still stuck and are our immediate priority. "
        f"Our systems currently show a {err_rate}% error rate on international order routes "
        f"(normal baseline is below 0.2%). {_cite('Telemetry')} {_cite('Zendesk')}",
        "",
        "---",
        "",
        "## What We Have Already Changed",
        "",
        "- Deployed a connection fix on Aug 14 — this reduced the error rate from a peak of 52% "
        f"down to {err_rate}% {_cite('Telemetry')}",
        "- Identified that **only international orders** are affected — domestic routing was never impacted "
        f"{_cite('Zendesk')} {_cite('Slack')}",
        f"- Opened a dedicated engineering ticket (NWAPI-3362) to resolve the two remaining stuck orders "
        f"{_cite('Jira')}",
        "",
        "---",
        "",
        "## What We Think Is Most Likely",
        "",
        "Two contributing factors:",
        "",
        "1. **International routing used a smaller capacity setting** — our international order pool was "
        "configured at one-quarter of the capacity used for domestic orders. Under load, it exhausted "
        f"first and caused timeouts. {_cite('Slack')} {_cite('Telemetry')}",
        "2. **A maintenance script run on Aug 13** made the situation worse by introducing a data "
        f"lookup slowdown affecting stuck orders. {_cite('Postmortem')}",
        "",
        "We also have a known configuration gap under review (ENG-3321) that may have allowed "
        f"stale values to persist for international patterns. {_cite('Jira')}",
        "",
    ]

    if high_conflicts:
        lines += [
            "---",
            "",
            "## What We Are Still Reconciling",
            "",
            "We want to be transparent — we found discrepancies between our internal reports "
            "that we are resolving before sending you a final corrected RCA:",
            "",
        ]
        for c in high_conflicts:
            lines.append(f"- **{_f(c, 'category')}:** {_f(c, 'description')[:120]}")
        lines.append("")

    lines += [
        "---",
        "",
        "## What We Are Doing Next",
        "",
        f"| # | Action | Owner | By When |",
        f"|---|---|---|---|",
        f"| 1 | Resolve stuck orders {stuck_ord} | Being assigned today | Today |",
        f"| 2 | Audit all enterprise accounts for any other stuck orders | Eng Lead | Today |",
        f"| 3 | Send you a corrected RCA with accurate order count | {csm} (CSM) | EOD {NOW} |",
        f"| 4 | Increase international routing capacity to match domestic | Engineering | This week |",
        "",
        "---",
        "",
        "## Next Update",
        "",
        f"We will send a written confirmation by **EOD {NOW}** with:",
        f"- Named owner for stuck order resolution",
        f"- Confirmed count of all affected orders (correcting the 23 vs. 47 discrepancy)",
        f"- Updated timeline",
        "",
        "We are also available for a **bridge call today** — please reply with a preferred time "
        "and we will arrange it immediately.",
        "",
        "---",
        "",
        "We sincerely apologise for the impact this has had on your supply chain operations "
        f"and for the delay since our last update on 2026-08-13. Resolving this for {company} "
        "is our top priority.",
        "",
        f"Warm regards,  ",
        f"**{csm}** (Customer Success Manager)  ",
        f"**{tam}** (Technical Account Manager)  ",
        "Northwind Enterprise Support",
        "",
        "---",
        "",
        f"*Synthesized from: Zendesk ZD-98741, ZD-99788 · Slack #incident-order-processing · "
        f"Postmortem INC-2026-0812 · Telemetry · Account Summary ACC-00441 · "
        f"Jira NWAPI-3362 · Executive Email (Derek Hartley, 2026-08-13).*",
    ]
    return "\n".join(lines)


def generate_action_items(artifacts: list[dict], conflicts: list) -> str:
    account = next(a for a in artifacts if a["source"] == "Account Summary")
    jira    = next(a for a in artifacts if a["source"] == "Jira")

    lines = [
        "# Prioritized Action Items — INC-2026-0812",
        f"**Generated:** {NOW}  ",
        f"**Customer:** {account['customer']} — {account['tier']} "
        f"(Renewal: {account['renewal_date']}, Risk: {account['renewal_risk']})",
        "",
        "---",
        "",
        "## P0 — Immediate (Today)",
        "",
        "### 1. Fix stuck orders ORD-55892 and ORD-55901",
        "- **Why:** Customer actively reporting these. Incident is NOT resolved from their perspective.",
        "- **Owner:** Unassigned — assign immediately",
        "- **Sources:** [Zendesk ZD-98741] [Jira NWAPI-3362] [Slack 2026-08-19]",
        "- **Action:** Assign NWAPI-3362. Run stuck-order cleanup job for all PROCESSING orders since 2026-08-11.",
        "",
        "### 2. Send executive update to Derek Hartley (VP Procurement, Contoso)",
        "- **Why:** Last update was 2026-08-13. VP email demands response by EOD. CEO is CC'd. Renewal at risk.",
        "- **Owner:** Laura Callahan (CSM)",
        "- **Sources:** [Executive Email] [Account Summary ACC-00441]",
        "- **Action:** Send RCA summary + remediation status. Offer goodwill credit discussion. Schedule bridge call.",
        "",
        "### 3. Audit ALL customers for stuck orders — not just Contoso",
        "- **Why:** Postmortem lists 3 enterprise accounts affected. Only Contoso has surfaced stuck orders.",
        "- **Owner:** Andrew Fuller (Eng Lead)",
        "- **Sources:** [Postmortem] [Slack] [Account Summary]",
        "- **Action:** Query all orders in intermediate state since 2026-08-11 across all accounts.",
        "",
        "---",
        "",
        "## P1 — This Week",
        "",
        "### 4. Reconcile true order impact count",
        "- **Why:** Claims range 23–60+. Accurate number needed for SLA credit and customer comms.",
        "- **Owner:** Eng Lead + CSM",
        "- **Sources:** [Postmortem] [Zendesk] [Slack] [Jira] [Telemetry] [Executive Email]",
        "",
        "### 5. Resolve root cause timeline discrepancy",
        "- **Why:** Slack/Telemetry say Aug 11; Postmortem says Aug 13. Wrong root cause = wrong fix.",
        "- **Owner:** Nancy Davolio + Steven Buchanan",
        "- **Sources:** [Slack] [Postmortem] [Jira] [Telemetry]",
        "- **Action:** Correlate telemetry with gateway deployment and migration timestamps. Update postmortem.",
        "",
        "### 6. Add index validation to migration pre-flight checklist",
        "- **Owner:** Steven Buchanan — Due: 2026-08-23",
        "- **Sources:** [Postmortem]",
        "",
        "### 7. Require manual approval gate for production DB migrations",
        "- **Owner:** Andrew Fuller — Due: 2026-08-23",
        "- **Sources:** [Postmortem]",
        "",
        "---",
        "",
        "## P2 — This Sprint",
        "",
        "### 8. Implement DB connection pool circuit breaker",
        "- **Owner:** Nancy Davolio — Due: 2026-08-30 — **Sources:** [Postmortem] [Jira NWAPI-3341]",
        "",
        "### 9. Add monitoring alert for invalid DB indexes",
        "- **Owner:** Janet Leverling — Due: 2026-08-28 — **Sources:** [Postmortem]",
        "",
        "### 10. Add pre-migration dry-run environment",
        "- **Owner:** Andrew Fuller — Due: 2026-09-06 — **Sources:** [Postmortem]",
        "",
        "---",
        "",
        "## P3 — Account Health",
        "",
        f"### 11. Schedule emergency QBR with Contoso",
        f"- **Why:** Health {account['health_score']}/100, NPS {account['nps_score']}/10, 2 SLA breaches, renewal Dec.",
        "- **Owner:** Laura Callahan (CSM) + Robert King (TAM)",
        "- **Sources:** [Account Summary ACC-00441] [Executive Email]",
        "",
        "### 12. Prioritize FR-2201 (bulk order status export) for Contoso",
        "- **Why:** Gives customer self-service visibility; reduces support burden and rebuilds trust.",
        "- **Owner:** Product + Eng — **Sources:** [Account Summary ACC-00441]",
        "",
        "---",
        "",
        "## Conflict-Driven Items",
        "",
        "These actions exist specifically because of cross-source conflicts:",
        "",
    ]

    for c in conflicts:
        if _f(c, "severity") in ("HIGH", "MEDIUM"):
            lines.append(f"- **{_f(c, 'category')}:** {_f(c, 'description')[:120]}...")

    lines += [
        "",
        "---",
        "",
        f"*Actions derived from: Zendesk ZD-98741, Slack #incident-order-processing, "
        f"Postmortem INC-2026-0812, Telemetry, Account Summary ACC-00441, "
        f"Jira Sprint 47, Executive Email (Derek Hartley 2026-08-13).*",
    ]
    return "\n".join(lines)
