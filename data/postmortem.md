# Incident Postmortem: Order Processing Outage
**Incident ID:** INC-2026-0812  
**Severity:** SEV-1  
**Date of Postmortem:** 2026-08-16  
**Author:** Nancy Davolio (On-Call Lead)  
**Reviewers:** Andrew Fuller, Steven Buchanan  
**Status:** APPROVED

---

## Summary

A database migration executed on Wednesday August 13 at 23:00 UTC caused index corruption on the `orders` table, leading to full order processing failure. The outage lasted approximately 26 hours before mitigation. An estimated 23 customer orders were directly impacted.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-08-13 23:00 | DB migration script `migrate_orders_v12.sql` executed by automated pipeline |
| 2026-08-13 23:47 | Index rebuild begins on `orders.status_idx` (unexpected — not in migration plan) |
| 2026-08-14 01:15 | Index rebuild completes; table locks released |
| 2026-08-14 06:30 | First customer complaints received via Zendesk |
| 2026-08-14 09:00 | SEV-1 declared by on-call |
| 2026-08-14 14:30 | Root cause identified: corrupted index causing full table scans, connection exhaustion |
| 2026-08-14 16:00 | Fix deployed (index rebuilt manually, connection pool reset) |
| 2026-08-14 16:45 | Error rate normalized |

---

## Root Cause

The migration script `migrate_orders_v12.sql` included an unexpected `REINDEX CONCURRENTLY` operation on the `orders` table. During this operation, a partial failure left the `status_idx` index in an invalid state. Subsequent queries performing lookups on `order.status` fell back to full table scans, causing query times to spike from ~2ms to 8,000ms+. This exhausted the DB connection pool (200 connections), causing cascading timeouts across all order-related API endpoints.

**Primary Root Cause:** DB migration script with unvalidated index operation  
**Contributing Factor:** Insufficient pre-migration review checklist  

---

## Impact

- **Duration:** ~17 hours (23:00 Aug 13 → 16:00 Aug 14 UTC)
- **Orders impacted:** 23 orders stuck in intermediate state
- **Revenue at risk:** ~$85,000
- **Customers affected:** 3 enterprise accounts (Contoso Ltd, Fabrikam Inc, Adventure Works)

---

## Action Items

| Owner | Item | Due |
|---|---|---|
| Steven Buchanan | Add index validation step to migration checklist | 2026-08-23 |
| Nancy Davolio | Implement connection pool circuit breaker | 2026-08-30 |
| Andrew Fuller | Add pre-migration dry-run environment | 2026-09-06 |

---

## What Went Well
- On-call response was fast once SEV-1 was declared
- Rollback plan was clear and executed cleanly

## What Went Poorly
- Migration ran without manual approval gate
- No alerting on index invalidity
- Customer communication was delayed by 4 hours after mitigation
