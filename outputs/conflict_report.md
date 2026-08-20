# Conflict Report — Cross-Artifact Analysis
**Generated:** 2026-08-19  
**Incident:** INC-2026-0812  
**Artifacts analyzed:** 7  
**Conflicts detected:** 4

---

## Conflict Index

1. [HIGH] Timeline — Incident Start
2. [HIGH] Resolution Status
3. [MEDIUM] Impact — Orders Affected
4. [MEDIUM] Impact — Revenue at Risk

---

## Conflict 1: [HIGH] HIGH — Timeline — Incident Start

**Summary:** Sources disagree on when the incident began by 53 hours. Earliest: Slack (2026-08-11 18:00 UTC); Latest: Postmortem (2026-08-13 23:00 UTC).

**Source breakdown:**
  - Slack: 2026-08-11 18:00 UTC
  - Telemetry: 2026-08-11 18:00 UTC
  - Executive Email: 2026-08-12 13:00 UTC
  - Zendesk: 2026-08-12 14:00 UTC
  - Postmortem: 2026-08-13 23:00 UTC

**Involved sources:** Slack, Telemetry, Executive Email, Zendesk, Postmortem

**Why this matters:** Unresolved conflict may lead to incorrect decisions.

---

## Conflict 2: [HIGH] HIGH — Resolution Status

**Summary:** Engineering and Postmortem declare the incident RESOLVED, but Zendesk, Slack, Account Summary, and Telemetry show the issue is still active.

**Source breakdown:**
  - RESOLVED claim: Postmortem
  - STILL OPEN / DEGRADED: Slack, Telemetry, Account Summary, Zendesk, Executive Email, Jira
  - Telemetry shows 1.1-1.4% error rate on 2026-08-19 (above 0.2% baseline)
  - Zendesk: customer reported new failures on 2026-08-19T09:22Z
  - Jira NWAPI-3362 (stuck orders) is Open and Unassigned

**Involved sources:** Postmortem, Zendesk, Slack, Telemetry, Account Summary, Jira, Executive Email, Telemetry

**Why this matters:** Unresolved conflict may lead to incorrect decisions.

---

## Conflict 3: [MED] MEDIUM — Impact — Orders Affected

**Summary:** Sources report between 23 and 60 affected orders — a spread of 37. The true count is unresolved.

**Source breakdown:**
  - Postmortem: 23 orders
  - Account Summary: 23 orders
  - Jira/NWAPI-3350: 23 orders
  - Telemetry (stuck_orders_count): 31 orders
  - Zendesk: 47 orders
  - Executive Email: 47 orders
  - Slack: 60 orders
  - Jira/NWAPI-3341: 60 orders

**Involved sources:** Zendesk, Slack, Postmortem, Account Summary, Executive Email, Jira/NWAPI-3341, Jira/NWAPI-3350, Telemetry (stuck_orders_count)

**Why this matters:** Unresolved conflict may lead to incorrect decisions.

---

## Conflict 4: [MED] MEDIUM — Impact — Revenue at Risk

**Summary:** Revenue-at-risk estimates vary significantly: $85,000 (Postmortem) vs $200,000 (Account Summary / Zendesk).

**Source breakdown:**
  - Postmortem: $85,000
  - Account Summary: $200,000
  - Executive Email: $200,000

**Involved sources:** Postmortem, Account Summary, Executive Email

**Why this matters:** Unresolved conflict may lead to incorrect decisions.

---

## Artifact Summary Table

| Source | Incident Start Claim | Orders Affected | Resolution Status |
|---|---|---|---|
| Zendesk | 2026-08-12 14:00 UTC | 47 | open — customer still reporting issues as of 2026-08-19 |
| Slack | 2026-08-11 18:00 UTC | 60 | mitigated — but Contoso still reporting issues 2026-08-19 |
| Postmortem | 2026-08-13 23:00 UTC | 23 | resolved — 2026-08-14T16:00:00Z |
| Telemetry | 2026-08-11 18:00 UTC | — | degraded — telemetry shows 1.1-1.4% error rate as of 2026-08-19 |
| Account Summary | — | 23 | open — executive escalation active |
| Jira | — | — | 3 open tickets — NWAPI-3362 (stuck orders) unassigned |
| Executive Email | 2026-08-12 13:00 UTC | 47 | open — VP + CEO escalated, renewal at risk, competitor evaluation |

---

*Conflicts detected by comparing normalized fields across all 7 artifacts.*