# Customer Update Email — INC-2026-0812
**Generated:** 2026-08-19  
**Report type:** Customer-facing (non-technical, <2 min read)  

---

```
To:      Derek Hartley <d.hartley@contoso-ltd.com>
CC:      Margaret Peacock <m.peacock@contoso-ltd.com>; Laura Callahan (CSM)
From:    Laura Callahan — Northwind Enterprise Support
Date:    2026-08-19
Subject: [UPDATE] Order Processing — Contoso Ltd / INC-2026-0812
```

---

Hi Derek,

Thank you for your continued patience on the order processing issue affecting Contoso Ltd. Here is a concise update — we will keep it brief and jargon-free.

---

## What We Are Seeing

Intermittent failures on **international order submissions** since Aug 12. Domestic orders are unaffected throughout. Two specific orders (ORD-55892, ORD-55901) are still stuck and are our immediate priority. Our systems currently show a 1.4% error rate on international order routes (normal baseline is below 0.2%). [Telemetry] [Zendesk]

---

## What We Have Already Changed

- Deployed a connection fix on Aug 14 — this reduced the error rate from a peak of 52% down to 1.4% [Telemetry]
- Identified that **only international orders** are affected — domestic routing was never impacted [Zendesk] [Slack]
- Opened a dedicated engineering ticket (NWAPI-3362) to resolve the two remaining stuck orders [Jira]

---

## What We Think Is Most Likely

Two contributing factors:

1. **International routing used a smaller capacity setting** — our international order pool was configured at one-quarter of the capacity used for domestic orders. Under load, it exhausted first and caused timeouts. [Slack] [Telemetry]
2. **A maintenance script run on Aug 13** made the situation worse by introducing a data lookup slowdown affecting stuck orders. [Postmortem]

We also have a known configuration gap under review (ENG-3321) that may have allowed stale values to persist for international patterns. [Jira]

---

## What We Are Still Reconciling

We want to be transparent — we found discrepancies between our internal reports that we are resolving before sending you a final corrected RCA:

- **Timeline — Incident Start:** Sources disagree on when the incident began by 53 hours. Earliest: Slack (2026-08-11 18:00 UTC); Latest: Postmortem (202
- **Resolution Status:** Engineering and Postmortem declare the incident RESOLVED, but Zendesk, Slack, Account Summary, and Telemetry show the is

---

## What We Are Doing Next

| # | Action | Owner | By When |
|---|---|---|---|
| 1 | Resolve stuck orders ORD-55892, ORD-55901 | Being assigned today | Today |
| 2 | Audit all enterprise accounts for any other stuck orders | Eng Lead | Today |
| 3 | Send you a corrected RCA with accurate order count | Laura Callahan (CSM) | EOD 2026-08-19 |
| 4 | Increase international routing capacity to match domestic | Engineering | This week |

---

## Next Update

We will send a written confirmation by **EOD 2026-08-19** with:
- Named owner for stuck order resolution
- Confirmed count of all affected orders (correcting the 23 vs. 47 discrepancy)
- Updated timeline

We are also available for a **bridge call today** — please reply with a preferred time and we will arrange it immediately.

---

We sincerely apologise for the impact this has had on your supply chain operations and for the delay since our last update on 2026-08-13. Resolving this for Contoso Ltd is our top priority.

Warm regards,  
**Laura Callahan** (Customer Success Manager)  
**Robert King** (Technical Account Manager)  
Northwind Enterprise Support

---

*Synthesized from: Zendesk ZD-98741, ZD-99788 · Slack #incident-order-processing · Postmortem INC-2026-0812 · Telemetry · Account Summary ACC-00441 · Jira NWAPI-3362 · Executive Email (Derek Hartley, 2026-08-13).*