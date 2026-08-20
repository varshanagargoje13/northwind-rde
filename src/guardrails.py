"""
Guardrails — per-artifact fix templates applied after the recommendation
(conflict-detection) stage and before HITL review.

Each template validates fields specific to that source, auto-fixes where
possible, and flags anything it cannot correct.  Results are persisted to
outputs/guardrail_report.json.

Status values
-------------
  PASSED  — field is present and valid; no action needed
  FIXED   — field was invalid but auto-corrected (value replaced in-place)
  FLAGGED — field is invalid and cannot be auto-corrected; needs human attention
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── data types ────────────────────────────────────────────────────────────────

@dataclass
class Check:
    field:     str
    status:    str          # PASSED | FIXED | FLAGGED
    original:  Any
    corrected: Any
    note:      str


@dataclass
class ArtifactResult:
    source:          str
    status:          str    # PASSED | FIXED | FLAGGED
    checks:          list[Check] = field(default_factory=list)
    fixed_artifact:  dict        = field(default_factory=dict)

    @property
    def n_passed(self):  return sum(1 for c in self.checks if c.status == "PASSED")
    @property
    def n_fixed(self):   return sum(1 for c in self.checks if c.status == "FIXED")
    @property
    def n_flagged(self): return sum(1 for c in self.checks if c.status == "FLAGGED")


# ── helper ────────────────────────────────────────────────────────────────────

def _overall(checks: list[Check]) -> str:
    if any(c.status == "FLAGGED" for c in checks):
        return "FLAGGED"
    if any(c.status == "FIXED" for c in checks):
        return "FIXED"
    return "PASSED"


def _is_dt(val) -> bool:
    return isinstance(val, datetime)


def _clamp(val, lo, hi, checks: list[Check], fname: str) -> Any:
    if isinstance(val, (int, float)):
        if lo <= val <= hi:
            checks.append(Check(fname, "PASSED", val, val, f"In valid range [{lo}, {hi}]"))
            return val
        fixed = max(lo, min(hi, val))
        checks.append(Check(fname, "FIXED", val, fixed, f"Clamped {val} → {fixed}"))
        return fixed
    checks.append(Check(fname, "FLAGGED", val, val, f"Expected number in [{lo}, {hi}]"))
    return val


def _positive_int(val, checks: list[Check], fname: str, label="") -> Any:
    if isinstance(val, int) and val > 0:
        checks.append(Check(fname, "PASSED", val, val, label or "Valid positive integer"))
        return val
    if isinstance(val, (int, float)) and val <= 0:
        checks.append(Check(fname, "FIXED", val, None, "Non-positive value nulled"))
        return None
    checks.append(Check(fname, "FLAGGED", val, val, "Expected positive integer"))
    return val


def _non_neg_int(val, checks: list[Check], fname: str) -> Any:
    if isinstance(val, int) and val >= 0:
        checks.append(Check(fname, "PASSED", val, val, "Valid non-negative integer"))
        return val
    if isinstance(val, int) and val < 0:
        checks.append(Check(fname, "FIXED", val, 0, "Negative value set to 0"))
        return 0
    checks.append(Check(fname, "FLAGGED", val, val, "Expected non-negative integer"))
    return val


def _bool_field(val, checks: list[Check], fname: str) -> bool:
    if isinstance(val, bool):
        checks.append(Check(fname, "PASSED", val, val, "Valid boolean"))
        return val
    fixed = bool(val)
    checks.append(Check(fname, "FIXED", val, fixed, f"Coerced {val!r} → {fixed}"))
    return fixed


def _nonempty_str(val, checks: list[Check], fname: str) -> Any:
    if val and isinstance(val, str):
        checks.append(Check(fname, "PASSED", val, val, "Non-empty string"))
        return val
    checks.append(Check(fname, "FLAGGED", val, val, "Missing or empty string"))
    return val


def _list_field(val, checks: list[Check], fname: str, label="") -> list:
    if isinstance(val, list):
        checks.append(Check(fname, "PASSED", f"[{len(val)} items]", f"[{len(val)} items]",
                            label or f"{len(val)} item(s) present"))
        return val
    fixed: list = []
    checks.append(Check(fname, "FIXED", val, fixed, "Non-list coerced to empty list"))
    return fixed


# ── per-artifact fix templates ────────────────────────────────────────────────

def _zendesk(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    _positive_int(a.get("orders_affected_claim"), chk, "orders_affected_claim",
                  "Customer order count claim")
    a["sla_breach"]   = _bool_field(a.get("sla_breach"), chk, "sla_breach")
    _nonempty_str(a.get("status"), chk, "status")

    isc = a.get("incident_start_claim")
    if _is_dt(isc):
        chk.append(Check("incident_start_claim", "PASSED", str(isc), str(isc), "Valid datetime"))
    else:
        chk.append(Check("incident_start_claim", "FLAGGED", isc, isc, "Expected datetime object"))

    _nonempty_str(a.get("resolution_status"), chk, "resolution_status")
    _list_field(a.get("comments", []), chk, "comments", "Support comments present")

    return ArtifactResult("Zendesk", _overall(chk), chk, a)


def _slack(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    mc = a.get("message_count", 0)
    if isinstance(mc, int) and mc > 0:
        chk.append(Check("message_count", "PASSED", mc, mc, f"{mc} messages in thread"))
    else:
        chk.append(Check("message_count", "FLAGGED", mc, mc,
                          "Expected positive integer — thread may be empty"))

    kc = a.get("key_contributors", [])
    if kc and isinstance(kc, list):
        chk.append(Check("key_contributors", "PASSED", kc, kc,
                          f"{len(kc)} contributor(s): {', '.join(kc[:3])}{'…' if len(kc)>3 else ''}"))
    else:
        chk.append(Check("key_contributors", "FLAGGED", kc, kc, "No contributors captured"))

    isc = a.get("incident_start_claim")
    if _is_dt(isc):
        chk.append(Check("incident_start_claim", "PASSED", str(isc), str(isc), "Valid datetime"))
    else:
        chk.append(Check("incident_start_claim", "FLAGGED", isc, isc, "Expected datetime object"))

    _nonempty_str(a.get("channel"), chk, "channel")
    _nonempty_str(a.get("root_cause_claim"), chk, "root_cause_claim")

    return ArtifactResult("Slack", _overall(chk), chk, a)


def _postmortem(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    _positive_int(a.get("orders_affected_claim"), chk, "orders_affected_claim")
    _nonempty_str(a.get("root_cause_claim"), chk, "root_cause_claim")

    rt  = a.get("resolution_time")
    isc = a.get("incident_start_claim")
    if _is_dt(rt) and _is_dt(isc):
        if rt > isc:
            chk.append(Check("resolution_time", "PASSED", str(rt), str(rt),
                             "Resolution is after incident start ✓"))
        else:
            chk.append(Check("resolution_time", "FLAGGED", str(rt), str(rt),
                             "Resolution time BEFORE incident start — impossible timestamp"))
    else:
        chk.append(Check("resolution_time", "FLAGGED", rt, rt, "Expected datetime object"))

    dh = a.get("duration_hours")
    if isinstance(dh, (int, float)) and dh > 0:
        chk.append(Check("duration_hours", "PASSED", dh, dh, "Positive duration"))
    elif isinstance(dh, (int, float)):
        a["duration_hours"] = None
        chk.append(Check("duration_hours", "FIXED", dh, None, "Non-positive duration nulled"))
    else:
        chk.append(Check("duration_hours", "FLAGGED", dh, dh, "Expected positive number"))

    ai = a.get("action_items", [])
    if ai and isinstance(ai, list):
        chk.append(Check("action_items", "PASSED", f"[{len(ai)} items]", f"[{len(ai)} items]",
                         f"{len(ai)} post-incident action item(s) present"))
    else:
        chk.append(Check("action_items", "FLAGGED", ai, ai,
                         "No action items — postmortem may be incomplete"))

    _nonempty_str(a.get("status"), chk, "status")

    return ArtifactResult("Postmortem", _overall(chk), chk, a)


def _telemetry(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    cer = _clamp(a.get("current_error_rate_pct"), 0, 100, chk, "current_error_rate_pct")
    a["current_error_rate_pct"] = cer

    per = a.get("peak_error_rate_pct")
    if isinstance(per, (int, float)) and isinstance(cer, (int, float)):
        if per >= cer:
            chk.append(Check("peak_error_rate_pct", "PASSED", per, per,
                             f"Peak {per}% ≥ current {cer}% ✓"))
        else:
            chk.append(Check("peak_error_rate_pct", "FLAGGED", per, per,
                             f"Peak {per}% < current {cer}% — unexpected ordering"))
    else:
        chk.append(Check("peak_error_rate_pct", "FLAGGED", per, per, "Expected number"))

    soc = a.get("stuck_orders_count")
    fixed_soc = _non_neg_int(soc, chk, "stuck_orders_count")
    a["stuck_orders_count"] = fixed_soc

    cpm = a.get("connection_pool_max")
    if isinstance(cpm, int) and cpm > 0:
        chk.append(Check("connection_pool_max", "PASSED", cpm, cpm, "Valid pool size"))
    else:
        chk.append(Check("connection_pool_max", "FLAGGED", cpm, cpm,
                         "Expected positive integer for pool size"))

    isc = a.get("incident_start_claim")
    if _is_dt(isc):
        chk.append(Check("incident_start_claim", "PASSED", str(isc), str(isc), "Valid datetime"))
    else:
        chk.append(Check("incident_start_claim", "FLAGGED", isc, isc, "Expected datetime"))

    _nonempty_str(a.get("current_status"), chk, "current_status")

    return ArtifactResult("Telemetry", _overall(chk), chk, a)


def _account_summary(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    hs = _clamp(a.get("health_score"), 0, 100, chk, "health_score")
    a["health_score"] = hs

    nps = _clamp(a.get("nps_score"), 0, 10, chk, "nps_score")
    a["nps_score"] = nps

    VALID_RISKS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    rr = a.get("renewal_risk", "")
    if rr and str(rr).upper() in VALID_RISKS:
        a["renewal_risk"] = str(rr).upper()
        chk.append(Check("renewal_risk", "PASSED", rr, a["renewal_risk"], "Valid enum value"))
    else:
        chk.append(Check("renewal_risk", "FLAGGED", rr, rr,
                         f"Expected one of {sorted(VALID_RISKS)}, got {rr!r}"))

    cv = a.get("contract_value_usd")
    if isinstance(cv, (int, float)) and cv > 0:
        chk.append(Check("contract_value_usd", "PASSED", cv, cv, "Valid positive value"))
    else:
        chk.append(Check("contract_value_usd", "FLAGGED", cv, cv,
                         "Expected positive contract value"))

    sb = a.get("sla_breaches_90d")
    fixed_sb = _non_neg_int(sb, chk, "sla_breaches_90d")
    a["sla_breaches_90d"] = fixed_sb

    _nonempty_str(a.get("customer"), chk, "customer")
    _nonempty_str(a.get("renewal_date"), chk, "renewal_date")

    return ArtifactResult("Account Summary", _overall(chk), chk, a)


def _jira(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    tt = a.get("total_tickets", 0)
    ot = a.get("open_tickets", 0)
    if isinstance(tt, int) and isinstance(ot, int):
        if tt >= ot:
            chk.append(Check("total_vs_open_tickets", "PASSED", f"{tt}/{ot}",
                             f"{tt}/{ot}", "Total ≥ open tickets ✓"))
        else:
            chk.append(Check("total_vs_open_tickets", "FLAGGED", f"{tt}/{ot}",
                             f"{tt}/{ot}", "Open tickets exceed total — data inconsistency"))
    else:
        chk.append(Check("total_vs_open_tickets", "FLAGGED", f"{tt}/{ot}",
                         f"{tt}/{ot}", "Expected integer ticket counts"))

    cot = a.get("critical_open_tickets")
    a["critical_open_tickets"] = _list_field(cot, chk, "critical_open_tickets",
                                              f"{len(cot) if isinstance(cot,list) else 0} critical open ticket(s)")

    kao = a.get("known_affected_orders")
    a["known_affected_orders"] = _list_field(kao, chk, "known_affected_orders",
                                              f"{len(kao) if isinstance(kao,list) else 0} known order(s)")

    # NWAPI-3362 must be assigned — critical stuck-orders ticket
    raw_tickets = a.get("raw", {}).get("tickets", [])
    nw3362 = next((t for t in raw_tickets if t.get("id") == "NWAPI-3362"), None)
    if nw3362:
        assignee = nw3362.get("assignee", "")
        if assignee and assignee.lower() not in ("unassigned", "none", ""):
            chk.append(Check("NWAPI-3362.assignee", "PASSED", assignee, assignee,
                             "Stuck-orders ticket NWAPI-3362 is assigned"))
        else:
            chk.append(Check("NWAPI-3362.assignee", "FLAGGED", "Unassigned", "Unassigned",
                             "CRITICAL: NWAPI-3362 (stuck orders) is UNASSIGNED — requires immediate action"))
    else:
        chk.append(Check("NWAPI-3362.assignee", "FLAGGED", None, None,
                         "NWAPI-3362 not found in Jira tickets — may have been removed"))

    # ENG-3321 (cache invalidation) should be reprioritised
    eng3321 = next((t for t in raw_tickets if t.get("id") == "ENG-3321"), None)
    if eng3321:
        status = eng3321.get("status", "")
        if status == "Backlog":
            chk.append(Check("ENG-3321.status", "FLAGGED", "Backlog", "Backlog",
                             "ENG-3321 (cache invalidation) is in Backlog — known contributing factor, needs reprioritisation"))
        else:
            chk.append(Check("ENG-3321.status", "PASSED", status, status,
                             f"ENG-3321 status: {status}"))

    return ArtifactResult("Jira", _overall(chk), chk, a)


def _executive_email(a: dict) -> ArtifactResult:
    a = dict(a)
    chk: list[Check] = []

    a["renewal_threat"] = _bool_field(a.get("renewal_threat"), chk, "renewal_threat")
    _positive_int(a.get("orders_affected_claim"), chk, "orders_affected_claim",
                  "VP-claimed order count")
    _nonempty_str(a.get("sender"), chk, "sender")
    _nonempty_str(a.get("subject"), chk, "subject")

    er = a.get("executive_requests", [])
    if er and isinstance(er, list):
        chk.append(Check("executive_requests", "PASSED", f"[{len(er)} items]",
                         f"[{len(er)} items]",
                         f"{len(er)} executive request(s) captured"))
    else:
        chk.append(Check("executive_requests", "FLAGGED", er, er,
                         "No executive requests extracted — check email parser"))

    rv = a.get("revenue_at_risk_usd")
    if isinstance(rv, (int, float)) and rv > 0:
        chk.append(Check("revenue_at_risk_usd", "PASSED", rv, rv,
                         f"${rv:,.0f} at risk — documented"))
    else:
        chk.append(Check("revenue_at_risk_usd", "FLAGGED", rv, rv,
                         "Missing or non-positive revenue at risk"))

    isc = a.get("incident_start_claim")
    if _is_dt(isc):
        chk.append(Check("incident_start_claim", "PASSED", str(isc), str(isc), "Valid datetime"))
    else:
        chk.append(Check("incident_start_claim", "FLAGGED", isc, isc, "Expected datetime"))

    return ArtifactResult("Executive Email", _overall(chk), chk, a)


# ── registry ──────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, Any] = {
    "Zendesk":         _zendesk,
    "Slack":           _slack,
    "Postmortem":      _postmortem,
    "Telemetry":       _telemetry,
    "Account Summary": _account_summary,
    "Jira":            _jira,
    "Executive Email": _executive_email,
}


# ── public API ────────────────────────────────────────────────────────────────

def apply_all(artifacts: list[dict]) -> tuple[list[dict], list[ArtifactResult]]:
    """
    Apply per-artifact fix templates to all loaded artifacts.

    Returns
    -------
    guardrailed_artifacts : list[dict]
        Same order as input; each artifact has auto-fixes applied in-place.
    results : list[ArtifactResult]
        One result per artifact, containing per-field check details.
    """
    guardrailed: list[dict]          = []
    results:     list[ArtifactResult] = []

    for artifact in artifacts:
        source   = artifact.get("source", "")
        template = _TEMPLATES.get(source)
        if template:
            result = template(artifact)
            guardrailed.append(result.fixed_artifact)
            results.append(result)
        else:
            guardrailed.append(artifact)

    return guardrailed, results


def save_report(results: list[ArtifactResult], out_dir: Path) -> Path:
    """Persist the guardrail check results to outputs/guardrail_report.json."""

    def _serial(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, list):
            return [_serial(i) for i in v]
        return str(v)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total":   len(results),
            "passed":  sum(1 for r in results if r.status == "PASSED"),
            "fixed":   sum(1 for r in results if r.status == "FIXED"),
            "flagged": sum(1 for r in results if r.status == "FLAGGED"),
        },
        "artifacts": [
            {
                "source":  r.source,
                "status":  r.status,
                "passed":  r.n_passed,
                "fixed":   r.n_fixed,
                "flagged": r.n_flagged,
                "checks": [
                    {
                        "field":     c.field,
                        "status":    c.status,
                        "original":  _serial(c.original),
                        "corrected": _serial(c.corrected),
                        "note":      c.note,
                    }
                    for c in r.checks
                ],
            }
            for r in results
        ],
    }

    out_dir.mkdir(exist_ok=True)
    path = out_dir / "guardrail_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
