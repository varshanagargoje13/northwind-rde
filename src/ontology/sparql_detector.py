"""
SPARQL-based conflict detection over the RDF knowledge graph.

Each query maps to a semantic conflict class from the ontology.
Results are returned as plain dicts compatible with the Conflict dataclass
in conflict_detector.py so both paths are interchangeable in the pipeline.
"""

import json
from pathlib import Path

from rdflib import Graph

_PFX = (
    "PREFIX nw:   <http://northwind.io/escalation#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>\n"
)


def _q(g: Graph, sparql: str) -> list[dict]:
    rows = []
    for row in g.query(_PFX + sparql):
        rows.append({str(k): str(v) for k, v in zip(row.labels, row)})
    return rows


# ── 1. Resolution status conflict (OWL disjointWith: Open ⊥ Resolved) ─────────

def detect_status_conflict(g: Graph) -> list[dict]:
    rows = _q(g, """
        SELECT DISTINCT ?src1 ?src2 ?s1 ?s2 WHERE {
          ?a1 nw:sourceName ?src1 ; nw:claimsStatus ?s1 .
          ?a2 nw:sourceName ?src2 ; nw:claimsStatus ?s2 .
          FILTER(?a1 != ?a2 && ?s1 != ?s2)
          FILTER(
            (?s1 = nw:Resolved && (?s2 = nw:Open || ?s2 = nw:Degraded)) ||
            (?s2 = nw:Resolved && (?s1 = nw:Open || ?s1 = nw:Degraded))
          )
        } ORDER BY ?src1
    """)
    if not rows:
        return []
    pairs   = {(r["src1"], r["src2"]) for r in rows}
    sources = sorted({s for p in pairs for s in p})
    details = list(dict.fromkeys([
        f"  [{r['src1']}] → {r['s1'].split('#')[-1]}  |  "
        f"[{r['src2']}] → {r['s2'].split('#')[-1]}"
        for r in rows
    ]))
    return [{"category": "Resolution Status", "severity": "HIGH", "sources": sources,
             "description": (
                 f"SPARQL [OWL disjointWith violated]: {len(pairs)} pair(s) assert "
                 "contradictory Open/Resolved statuses for the same incident. "
                 "Ontology constraint: nw:Open owl:disjointWith nw:Resolved."
             ), "details": details}]


# ── 2. Order count mismatch ────────────────────────────────────────────────────

def detect_order_count_conflict(g: Graph) -> list[dict]:
    rows = _q(g, """
        SELECT ?src ?count WHERE {
          ?a nw:sourceName ?src ; nw:ordersAffectedClaim ?count .
        } ORDER BY ?count
    """)
    if len(rows) < 2:
        return []
    counts = [(r["src"], int(r["count"])) for r in rows]
    lo = min(counts, key=lambda x: x[1])
    hi = max(counts, key=lambda x: x[1])
    if hi[1] - lo[1] <= 5:
        return []
    return [{"category": "Impact — Orders Affected", "severity": "MEDIUM",
             "sources": [s for s, _ in counts],
             "description": (
                 f"SPARQL: {len(counts)} sources report different order counts — "
                 f"range {lo[1]}–{hi[1]} (spread: {hi[1]-lo[1]}). True count unresolved."
             ),
             "details": [f"  [{s}]: {c} orders" for s, c in sorted(counts, key=lambda x: x[1])]}]


# ── 3. Root cause mismatch ─────────────────────────────────────────────────────

def detect_root_cause_conflict(g: Graph) -> list[dict]:
    rows = _q(g, """
        SELECT ?src ?rcText WHERE {
          ?a  nw:sourceName      ?src .
          ?rc nw:rootCauseText   ?rcText .
          ?a  nw:claimsRootCause ?rc .
        } ORDER BY ?src
    """)
    if len(rows) < 2:
        return []
    distinct = {r["rcText"].lower()[:40] for r in rows}
    if len(distinct) < 2:
        return []
    return [{"category": "Root Cause", "severity": "HIGH",
             "sources": [r["src"] for r in rows],
             "description": (
                 f"SPARQL: {len(rows)} sources assert {len(distinct)} distinct root-cause "
                 "hypotheses — DB migration / API gateway connection leak / pool exhaustion."
             ),
             "details": [f"  [{r['src']}]: \"{r['rcText']}\"" for r in rows]}]


# ── 4. Timeline / incident start mismatch ─────────────────────────────────────

def detect_timeline_conflict(g: Graph) -> list[dict]:
    rows = _q(g, """
        SELECT ?src ?ts WHERE {
          ?a nw:sourceName ?src ; nw:startTimeClaim ?ts .
        } ORDER BY ?ts
    """)
    if len(rows) < 2:
        return []
    try:
        from datetime import datetime
        times = [(r["src"], datetime.fromisoformat(r["ts"])) for r in rows]
        span  = (times[-1][1] - times[0][1]).total_seconds() / 3600
    except Exception:
        return []
    if span < 4:
        return []
    return [{"category": "Timeline — Incident Start", "severity": "HIGH",
             "sources": [s for s, _ in times],
             "description": (
                 f"SPARQL: Incident start-time claims span {span:.1f}h — "
                 f"[{times[0][0]}] {times[0][1].strftime('%Y-%m-%d %H:%M UTC')} → "
                 f"[{times[-1][0]}] {times[-1][1].strftime('%Y-%m-%d %H:%M UTC')}."
             ),
             "details": [f"  [{s}]: {t.strftime('%Y-%m-%d %H:%M UTC')}" for s, t in times]}]


# ── 5. Revenue at risk mismatch ────────────────────────────────────────────────

def detect_revenue_conflict(g: Graph) -> list[dict]:
    rows = _q(g, """
        SELECT ?src ?rev WHERE {
          ?a nw:sourceName ?src ; nw:revenueAtRiskUSD ?rev .
        } ORDER BY ?rev
    """)
    if len(rows) < 2:
        return []
    vals = [(r["src"], float(r["rev"])) for r in rows]
    lo   = min(vals, key=lambda x: x[1])
    hi   = max(vals, key=lambda x: x[1])
    if hi[1] / max(lo[1], 1) <= 1.5:
        return []
    return [{"category": "Impact — Revenue at Risk", "severity": "MEDIUM",
             "sources": [s for s, _ in vals],
             "description": (
                 f"SPARQL: Revenue-at-risk estimates diverge — "
                 f"${lo[1]:,.0f} [{lo[0]}] vs ${hi[1]:,.0f} [{hi[0]}]."
             ),
             "details": [f"  [{s}]: ${v:,.0f}" for s, v in vals]}]


# ── 6. Renewal threat + SLA breach co-occurrence ──────────────────────────────

def detect_renewal_threat(g: Graph) -> list[dict]:
    cust_rows = _q(g, """
        SELECT ?cust WHERE {
          ?c nw:renewalThreat ?t ; rdfs:label ?cust .
          FILTER(str(?t) = "true")
        }
    """)
    sla_rows = _q(g, """
        SELECT ?src WHERE {
          ?a nw:sourceName ?src ; nw:slaBreached ?b .
          FILTER(str(?b) = "true")
        }
    """)
    if not cust_rows or not sla_rows:
        return []
    custs    = [r["cust"] for r in cust_rows]
    sla_srcs = [r["src"]  for r in sla_rows]
    return [{"category": "Account Risk — Renewal + SLA Breach", "severity": "HIGH",
             "sources": ["Executive Email", "Account Summary"] + sla_srcs,
             "description": (
                 f"SPARQL: {', '.join(custs)} has active renewal threat AND confirmed "
                 f"SLA breach(es) [{', '.join(sla_srcs)}] — renewal decision at risk."
             ),
             "details": [f"  Renewal threat: {', '.join(custs)}",
                         f"  SLA breach confirmed: {', '.join(sla_srcs)}"]}]


# ── Unified runner ─────────────────────────────────────────────────────────────

def detect_all(g: Graph) -> list[dict]:
    """Run all 6 SPARQL conflict queries and return sorted list."""
    results: list[dict] = []
    results.extend(detect_timeline_conflict(g))
    results.extend(detect_status_conflict(g))
    results.extend(detect_order_count_conflict(g))
    results.extend(detect_root_cause_conflict(g))
    results.extend(detect_revenue_conflict(g))
    results.extend(detect_renewal_threat(g))
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    results.sort(key=lambda c: order.get(c["severity"], 3))
    return results


def save_conflicts(conflicts: list[dict], out_dir: Path) -> Path:
    """Persist SPARQL conflicts to outputs/sparql_conflicts.json."""
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "sparql_conflicts.json"
    path.write_text(__import__("json").dumps(conflicts, indent=2), encoding="utf-8")
    return path


# ── Ontology fact extractor (for LLM context Layer 2) ─────────────────────────

def extract_facts(g: Graph) -> str:
    """
    Extract key RDF triples as compact structured text for LLM context Layer 2.
    Groups triples by semantic category for readability.
    """
    lines = ["## Ontology Knowledge Graph — RDF Triple Facts\n",
             "These facts are derived from the formal ontology graph (northwind_escalation.ttl).",
             "They represent cross-source claims as semantically typed triples.\n"]

    def _section(title: str, sparql: str, fmt_row):
        rows = list(g.query(_PFX + sparql))
        if not rows:
            return
        lines.append(f"### {title}")
        for r in rows:
            lines.append(fmt_row(r))
        lines.append("")

    _section("Resolution Status Claims",
        "SELECT ?src ?status WHERE { ?a nw:sourceName ?src ; nw:claimsStatus ?status . } ORDER BY ?src",
        lambda r: f"  [{str(r[0])}]  claimsStatus → {str(r[1]).split('#')[-1]}")

    _section("Orders Affected Claims",
        "SELECT ?src ?count WHERE { ?a nw:sourceName ?src ; nw:ordersAffectedClaim ?count . } ORDER BY ?count",
        lambda r: f"  [{str(r[0])}]  ordersAffectedClaim → {str(r[1])} orders")

    _section("Incident Start Time Claims",
        "SELECT ?src ?ts WHERE { ?a nw:sourceName ?src ; nw:startTimeClaim ?ts . } ORDER BY ?ts",
        lambda r: f"  [{str(r[0])}]  startTimeClaim → {str(r[1])}")

    _section("Root Cause Claims",
        "SELECT ?src ?rcText WHERE { ?a nw:sourceName ?src ; nw:claimsRootCause ?rc . ?rc nw:rootCauseText ?rcText . } ORDER BY ?src",
        lambda r: f"  [{str(r[0])}]  claimsRootCause → \"{str(r[1])}\"")

    _section("Revenue at Risk Claims",
        "SELECT ?src ?rev WHERE { ?a nw:sourceName ?src ; nw:revenueAtRiskUSD ?rev . } ORDER BY ?rev",
        lambda r: f"  [{str(r[0])}]  revenueAtRiskUSD → ${float(str(r[1])):,.0f}")

    _section("Customer Health (ontology-asserted)",
        "SELECT ?cust ?health ?nps ?threat WHERE { ?c a nw:Customer ; rdfs:label ?cust . OPTIONAL { ?c nw:healthScore ?health } OPTIONAL { ?c nw:npsScore ?nps } OPTIONAL { ?c nw:renewalThreat ?threat } }",
        lambda r: f"  [{str(r[0])}]  healthScore={str(r[1])}  npsScore={str(r[2])}  renewalThreat={str(r[3])}")

    _section("Stuck Orders (nw:affectsOrder triples)",
        "SELECT ?oid ?status WHERE { ?o a nw:Order ; nw:orderId ?oid ; nw:orderStatus ?status . } ORDER BY ?oid",
        lambda r: f"  {str(r[0])}  orderStatus={str(r[1])}")

    return "\n".join(lines)
