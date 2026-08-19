# Northwind Escalation Synthesizer

A Python pipeline that ingests **7 heterogeneous escalation artifacts**, detects cross-source conflicts, and generates **3 audience-targeted output reports** with full source citations — turning hours of manual triage into seconds of automated synthesis.

---

## The Problem

When a strategic customer escalates, information about the same incident is scattered across Zendesk, Slack threads, engineering postmortems, telemetry dashboards, account summaries, Jira tickets, and eng-status emails. Each source tells a slightly different story. Teams waste hours reconciling them — or worse, act on the wrong version.

---

## What This Does

```
7 Artifacts  →  Conflict Detection  →  3 Synthesized Outputs
```

| Input Artifact | Contains |
|---|---|
| `zendesk_ticket.json` | Customer-reported symptoms, timeline, SLA status |
| `slack_thread.json` | Internal incident response thread |
| `postmortem.md` | Approved root cause analysis |
| `telemetry.json` | Error rates, latency, connection pool metrics |
| `account_summary.json` | Customer health, renewal risk, executive contacts |
| `jira_tickets.json` | Engineering bug tickets with impact estimates |
| `eng_status.md` | Engineering resolution declaration |

| Output Report | Audience |
|---|---|
| `executive_summary.md` | Leadership / Customer Success — full incident picture with citations |
| `conflict_report.md` | Ops / Engineering — every cross-source contradiction with severity |
| `action_items.md` | All teams — prioritized P0→P3 actions with source references |

---

## Conflicts Detected (Example Run)

| Severity | Category | Finding |
|---|---|---|
| HIGH | Timeline — Incident Start | 53-hour spread: Slack says Aug 11 18:00 UTC, Eng Status says Aug 13 23:00 UTC |
| HIGH | Resolution Status | Engineering declared RESOLVED; Zendesk/Telemetry/Jira show still active |
| MEDIUM | Orders Affected | Claims range 23→60+ across sources — unreconciled |
| MEDIUM | Revenue at Risk | $85K (Postmortem) vs $200K (Account Summary) — 2.4× gap |

---

## Project Structure

```
northwind-escalation-synthesizer/
├── data/                        # Mock artifact files (7 total)
│   ├── zendesk_ticket.json
│   ├── slack_thread.json
│   ├── postmortem.md
│   ├── telemetry.json
│   ├── account_summary.json
│   ├── jira_tickets.json
│   └── eng_status.md
├── src/
│   ├── loaders.py               # Artifact parsers — normalize each format to a dict
│   ├── conflict_detector.py     # 5 rule-based conflict detectors
│   └── synthesizer.py           # Report generators (executive, conflict, action items)
├── outputs/                     # Generated reports (created on run)
│   ├── executive_summary.md
│   ├── conflict_report.md
│   └── action_items.md
├── pipeline.py                  # Entry point
└── README.md
```

---

## Running It

Requires Python 3.10+ and no external dependencies.

```bash
python pipeline.py
```

The pipeline will:
1. Load and normalize all 7 artifacts
2. Run 5 conflict detectors across them
3. Write 3 markdown reports to `outputs/`
4. Print a summary with detected conflicts to the console

---

## How Conflict Detection Works

Each detector in `src/conflict_detector.py` targets a specific conflict category:

| Detector | Logic |
|---|---|
| `detect_timeline_conflicts` | Compares `incident_start_claim` across all sources; flags if spread > 4 hours |
| `detect_status_conflicts` | Finds sources claiming RESOLVED vs OPEN/DEGRADED simultaneously |
| `detect_orders_affected_conflicts` | Collects all numeric order-impact claims; flags if spread > 5 |
| `detect_root_cause_conflicts` | Categorizes root cause claims by theme (migration / gateway / pool); flags divergence |
| `detect_revenue_conflicts` | Flags if revenue estimates differ by more than 1.5× |

All conflicts are severity-ranked (HIGH / MEDIUM / LOW) and included as source-cited entries in all three output reports.

---

## Extending This

**Add a new artifact type:** implement a `load_<type>(path) -> dict` function in `src/loaders.py` following the existing pattern, add it to the `load_all()` list, and surface its fields in the relevant conflict detectors.

**Add a new conflict detector:** add a function `detect_<category>(artifacts) -> list[Conflict]` in `src/conflict_detector.py` and register it in `detect_all()`.

**Connect to real data:** replace the JSON/Markdown files in `data/` with API calls to your actual Zendesk, Jira, or Slack instances. The `load_all()` contract (normalized dicts) stays the same.

---

## Scenario

The mock data models a real-world escalation pattern: a Northwind order-processing outage where the customer (Contoso Ltd, $480K ARR, HIGH renewal risk) is still experiencing failures six days after engineering declared the incident closed — a situation that only becomes visible when all 7 sources are read together.

---

## Inspired By

The architecture follows the pattern described in the *Northwind Logistics Customer Escalation Case Study*: ingest messy, contradictory real-world signals, synthesize them with full auditability, and produce audience-specific outputs that drive action rather than just report facts.
