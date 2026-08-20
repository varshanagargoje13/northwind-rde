"""
OWL-RL reasoning over the RDF knowledge graph using owlrl.

Applies semantic closure so axioms defined in the ontology (e.g., owl:disjointWith
between nw:Open and nw:Resolved) generate inferred triples. After closure, SPARQL
queries can detect violations that would be invisible without reasoning.
"""

from rdflib import Graph


def apply_reasoning(g: Graph) -> tuple[Graph, int]:
    """
    Apply OWL-RL semantic closure to the graph in place.

    Returns (graph, inferred_triple_count).
    If owlrl is not installed, returns the graph unchanged with count=0.
    """
    before = len(g)
    try:
        import owlrl
        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
        inferred = len(g) - before
    except ImportError:
        import warnings
        warnings.warn(
            "owlrl not installed — OWL-RL reasoning skipped. "
            "Run: pip install owlrl",
            stacklevel=2,
        )
        inferred = 0
    return g, inferred
