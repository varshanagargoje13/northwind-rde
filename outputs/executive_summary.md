# Executive Escalation Summary — Northwind Order Processing Incident
**Generated:** 2026-08-19  
**Incident:** INC-2026-0812  
**Customer:** Contoso Ltd (Enterprise)  
**Status:** ⚠️  CONFLICTED — see conflict report

---

## Situation at a Glance

Northwind's order processing system experienced a major outage that directly impacted **Contoso Ltd**, a $480,000/year enterprise customer renewing in 2026-12-01 with a **HIGH renewal risk** [Account Summary]. The customer's executive sponsor (Derek Hartley (VP Procurement)) has been engaged [Account Summary].

Engineering declared the incident **RESOLVED** on 2026-08-14 at 16:00 UTC [Executive Email] [Postmortem], but the customer is still actively reporting failures as of today [Zendesk], live telemetry shows a degraded error rate of 1.4% against a 0.2% baseline [Telemetry], and Jira ticket NWAPI-3362 for stuck orders is **Open and Unassigned** [Jira].

---

## Incident Timeline (Best Estimate)

| When | Event | Source |
|---|---|---|
| 2026-08-11 18:00 UTC | First elevated error rates detected | [Slack] [Telemetry] |
| 2026-08-11 17:28 UTC | API Gateway v2.4.1 deployed | [Jira] |
| 2026-08-12 14:00 UTC | SEV-1 declared; error rate hit 34% | [Slack] [Telemetry] |
| 2026-08-12 14:07 UTC | Zendesk ticket ZD-98741 opened by Contoso | [Zendesk] |
| 2026-08-13 23:00 UTC | DB migration script ran in production | [Postmortem] [Executive Email] |
| 2026-08-14 01:00 UTC | Error rate spiked to 41-52% (second wave) | [Telemetry] |
| 2026-08-14 16:00 UTC | Engineering declared resolution | [Executive Email] |
| 2026-08-19 09:22 UTC | Customer still reporting failures on specific orders | [Zendesk] |

---

## Impact

- **Customer health score:** 42/100 (declining) [Account Summary]
- **Orders affected:** Claims range from 23 to 60+ across sources — not yet reconciled [Postmortem] [Slack] [Zendesk]
- **Revenue at risk:** $200,000 (customer estimate) vs $85,000 (Postmortem) [Account Summary] [Postmortem]
- **Total API errors logged:** 12,725 [Telemetry]
- **SLA breaches in past 90 days:** 2 (including this incident) [Account Summary]
- **NPS score:** 6/10 [Account Summary]

---

## Root Cause Summary

Three overlapping root causes have been identified across sources (see Conflict Report for discrepancies):

1. **API Gateway v2.4.1 connection leak** — connection pool exhausted under load [Slack] [Jira/NWAPI-3341]
2. **DB migration script (migrate_orders_v12.sql)** — caused invalid index on `orders.status_idx`, driving query latency to 8,000ms+ [Postmortem] [Executive Email] [Jira/NWAPI-3350]
3. **Residual stuck orders** — cleanup job did not recover all affected orders after mitigation [Jira/NWAPI-3362] [Zendesk]

---

## Data Conflicts Detected

**2 HIGH** and **2 MEDIUM** conflicts found across the 7 artifacts. See the full Conflict Report for details. Key issues:

- **HIGH — Timeline — Incident Start:** Sources disagree on when the incident began by 53 hours. Earliest: Slack (2026-08-11 18:00 UTC); Latest: Postmortem (2026-08-13 23:00 UTC).
- **HIGH — Resolution Status:** Engineering and Postmortem declare the incident RESOLVED, but Zendesk, Slack, Account Summary, and Telemetry show the issue is still active.
- **MEDIUM — Impact — Orders Affected:** Sources report between 23 and 60 affected orders — a spread of 37. The true count is unresolved.

---

## Open Items Requiring Immediate Attention

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Investigate and remediate stuck orders ORD-55892, ORD-55901 | Unassigned | 🔴 Open [Jira] [Zendesk] |
| 2 | Reconcile true count of affected orders across all customers | Eng Lead | 🔴 Needed [Postmortem] [Slack] |
| 3 | Issue updated executive communication to Contoso (Derek Hartley) | Laura Callahan | 🔴 Overdue [Account Summary] |
| 4 | Assign NWAPI-3362 to an engineer | Eng Lead | 🔴 Unassigned [Jira] |
| 5 | Add index validation to migration checklist | Steven Buchanan | 🟡 Due Aug 23 [Postmortem] |
| 6 | Implement DB connection pool circuit breaker | Nancy Davolio | 🟡 Due Aug 30 [Postmortem] |

---

*This summary was synthesized from 7 sources: Zendesk ZD-98741, Slack #incident-order-processing, Postmortem INC-2026-0812, Production Telemetry, Account Summary ACC-00441, Jira NWAPI sprint 47, and Executive Email Update (2026-08-14).*