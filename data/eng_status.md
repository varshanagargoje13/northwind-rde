# Engineering Status Update — Order Processing Incident
**Date:** 2026-08-14  
**Author:** Andrew Fuller (Eng Lead)  
**Distribution:** Leadership, Customer Success, Support  
**Incident:** INC-2026-0812

---

## Current Status: ✅ RESOLVED

The order processing incident has been **fully resolved** as of 16:00 UTC on August 14, 2026.

---

## What Happened

On Wednesday August 13 at 23:00 UTC, a scheduled database migration ran against the production `orders` table. The migration script inadvertently triggered an index rebuild operation that partially failed, leaving the `orders.status_idx` index in an invalid state. This caused all order status queries to perform full table scans, driving query latency from ~2ms to 8,000ms+. The resulting load exhausted the database connection pool (200 connections), causing cascading timeouts across all order management API endpoints.

## Resolution

Engineering identified and rebuilt the corrupted database index at 14:30 UTC on August 14. The connection pool was reset at 15:45 UTC. Service fully normalized by 16:00 UTC.

## Orders Affected

Approximately **23 orders** were affected during the outage window. All affected orders have been identified and manually remediated. Customers will see their orders in the correct state.

## Preventive Actions

| Action | Owner | Target Date |
|---|---|---|
| Add index validation to migration pre-flight checklist | Steven Buchanan | Aug 23 |
| Implement DB connection pool circuit breaker | Nancy Davolio | Aug 30 |
| Require manual approval gate for production migrations | Andrew Fuller | Aug 23 |
| Add monitoring for index invalidity | Janet Leverling | Aug 28 |

## Customer Communication

All impacted enterprise customers have been notified via their Customer Success Manager. A formal Root Cause Analysis document will be shared within 5 business days.

---

*This incident is closed. No further engineering updates will be issued unless new issues are discovered.*
