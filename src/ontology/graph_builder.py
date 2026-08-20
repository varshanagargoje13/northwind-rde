"""
Builds an RDF knowledge graph from the 7 guardrailed artifact dicts.
Loads the northwind_escalation.ttl domain ontology, maps artifact fields
to formal RDF triples, and persists the graph to outputs/knowledge_graph.ttl.
"""

from datetime import datetime
from pathlib import Path

from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD

NW = Namespace("http://northwind.io/escalation#")


def _uri(label: str) -> URIRef:
    safe = label.replace(" ", "_").replace("/", "_").replace("-", "_")
    return NW[safe]


def _iso(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _infer_status(resolution_status: str) -> URIRef | None:
    """Map free-text resolution_status to an ontology status URI."""
    text = (resolution_status or "").lower()
    if "resolved" in text and "not" not in text and "still" not in text:
        return NW.Resolved
    if "degraded" in text:
        return NW.Degraded
    if "mitigated" in text:
        return NW.Mitigated
    if "open" in text or "still" in text or "active" in text:
        return NW.Open
    return None


def build(artifacts: list[dict], ontology_path: Path) -> Graph:
    """
    Build an RDF knowledge graph from 7 guardrailed artifact dicts.

    Asserts triples for:
      - Incident node linked to all artifact nodes via nw:hasArtifact
      - Per-artifact: sourceName, ordersAffectedClaim, startTimeClaim,
        revenueAtRiskUSD, slaBreached, errorRatePct, claimsStatus, claimsRootCause
      - Customer node: healthScore, npsScore, renewalThreat
      - Order nodes: orderId, orderStatus (known stuck orders from Jira)
    """
    g = Graph()
    g.bind("nw",   NW)
    g.bind("xsd",  XSD)
    g.bind("rdfs", RDFS)

    if ontology_path.exists():
        g.parse(str(ontology_path), format="turtle")

    # ── Incident node ─────────────────────────────────────────────────────────
    inc_uri = NW["INC_2026_0812"]
    g.add((inc_uri, RDF.type,      NW.Incident))
    g.add((inc_uri, NW.incidentId, Literal("INC-2026-0812")))

    # ── Artifact nodes ─────────────────────────────────────────────────────────
    for a in artifacts:
        src   = a["source"]
        a_uri = _uri(f"artifact_{src}")

        g.add((a_uri,   RDF.type,       NW.Artifact))
        g.add((a_uri,   NW.sourceName,  Literal(src)))
        g.add((inc_uri, NW.hasArtifact, a_uri))

        oc = a.get("orders_affected_claim")
        if isinstance(oc, int):
            g.add((a_uri, NW.ordersAffectedClaim, Literal(oc, datatype=XSD.integer)))

        ts = _iso(a.get("incident_start_claim"))
        if ts:
            g.add((a_uri, NW.startTimeClaim, Literal(ts, datatype=XSD.dateTime)))

        rv = a.get("revenue_at_risk_usd")
        if rv is not None:
            g.add((a_uri, NW.revenueAtRiskUSD, Literal(float(rv), datatype=XSD.decimal)))

        sla = a.get("sla_breach")
        if sla is not None:
            g.add((a_uri, NW.slaBreached, Literal(bool(sla), datatype=XSD.boolean)))

        er = a.get("current_error_rate_pct")
        if er is not None:
            g.add((a_uri, NW.errorRatePct, Literal(float(er), datatype=XSD.decimal)))

        status_uri = _infer_status(a.get("resolution_status", ""))
        if status_uri:
            g.add((a_uri, NW.claimsStatus, status_uri))

        rc = a.get("root_cause_claim")
        if rc:
            rc_uri = _uri(f"rootcause_{src}")
            g.add((rc_uri, RDF.type,           NW.RootCause))
            g.add((rc_uri, NW.rootCauseText,   Literal(rc)))
            g.add((a_uri,  NW.claimsRootCause, rc_uri))

    # ── Customer node ─────────────────────────────────────────────────────────
    acc = next((a for a in artifacts if a["source"] == "Account Summary"), {})
    if acc:
        c_uri = _uri(f"customer_{acc.get('customer', 'unknown')}")
        g.add((c_uri, RDF.type,   NW.Customer))
        g.add((c_uri, RDFS.label, Literal(acc.get("customer", ""))))
        if acc.get("health_score") is not None:
            g.add((c_uri, NW.healthScore, Literal(acc["health_score"], datatype=XSD.integer)))
        if acc.get("nps_score") is not None:
            g.add((c_uri, NW.npsScore, Literal(float(acc["nps_score"]), datatype=XSD.decimal)))
        acc_art = _uri("artifact_Account Summary")
        g.add((acc_art, NW.reportedBy, c_uri))

    email = next((a for a in artifacts if a["source"] == "Executive Email"), {})
    if email.get("renewal_threat") and acc:
        c_uri = _uri(f"customer_{acc.get('customer', 'unknown')}")
        g.add((c_uri, NW.renewalThreat, Literal(True, datatype=XSD.boolean)))

    # ── Stuck order nodes ─────────────────────────────────────────────────────
    jira = next((a for a in artifacts if a["source"] == "Jira"), {})
    for oid in jira.get("known_affected_orders", []):
        o_uri = _uri(f"order_{oid}")
        g.add((o_uri,   RDF.type,        NW.Order))
        g.add((o_uri,   NW.orderId,      Literal(oid)))
        g.add((o_uri,   NW.orderStatus,  Literal("PROCESSING")))
        g.add((inc_uri, NW.affectsOrder, o_uri))

    return g


def save(g: Graph, out_dir: Path) -> Path:
    """Serialize the knowledge graph to outputs/knowledge_graph.ttl."""
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "knowledge_graph.ttl"
    g.serialize(destination=str(path), format="turtle")
    return path


def summary(g: Graph) -> dict:
    """Return graph stats for pipeline display."""
    return {
        "total_triples":    len(g),
        "artifact_nodes":   len(list(g.subjects(RDF.type, NW.Artifact))),
        "order_nodes":      len(list(g.subjects(RDF.type, NW.Order))),
        "root_cause_nodes": len(list(g.subjects(RDF.type, NW.RootCause))),
        "customer_nodes":   len(list(g.subjects(RDF.type, NW.Customer))),
    }
