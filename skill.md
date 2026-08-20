# Northwind Escalation Synthesizer — Claude API Skill Reference

This file documents every Claude API pattern applied in this project and explains why each was chosen.

---

## Skill: `claude-api`

**Invoked via:** `Skill(claude-api)` in `.claude/settings.local.json`  
**Language:** Python  
**SDK:** `anthropic` (official Anthropic Python SDK, no third-party frameworks)

---

## Model

```python
MODEL = "claude-opus-5"
```

`claude-opus-5` is used for both phases. It supports adaptive thinking and the Tool Runner beta, which are required by this pipeline.

---

## Phase 1 — Agentic Analysis (Tool Runner)

**File:** `src/ai_synthesizer.py`

### Tool Runner

```python
from anthropic import beta_tool

@beta_tool
def flag_schema_violation(source, field, expected, actual, severity) -> str: ...

@beta_tool
def flag_conflict(category, severity, sources, description, implication) -> str: ...

@beta_tool
def add_action_item(priority, title, owner, sources, description) -> str: ...

runner = client.beta.messages.tool_runner(
    model=MODEL,
    max_tokens=16000,
    thinking={"type": "adaptive"},
    tools=[flag_schema_violation, flag_conflict, add_action_item],
    system=cached_system,
    messages=cached_messages,
)
for _ in runner:
    pass  # SDK drives the agentic loop
```

**Why Tool Runner (not manual loop):** The `@beta_tool` decorator + `tool_runner` eliminates the `while stop_reason == "tool_use"` boilerplate. The SDK handles tool dispatch, result injection, and loop termination.

**Why `thinking: adaptive`:** `budget_tokens` is rejected on Opus 5 with a 400 error. `adaptive` lets the model decide reasoning depth per turn.

### Prompt Caching — Phase 1

```python
cached_system = [
    {"type": "text", "text": ANALYSIS_SYSTEM, "cache_control": {"type": "ephemeral"}}
]
cached_messages = [
    {"role": "user", "content": [
        {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}}
    ]}
]
```

The system prompt and the large 6-layer artifact context are both cached. Multi-turn tool loop iterations reuse the cached prefix instead of re-tokenising ~60K chars on every tool call.

---

## Phase 2 — Streaming Reports (3 calls)

**File:** `src/ai_synthesizer.py` → `generate_reports()`

```python
with client.messages.stream(
    model=MODEL,
    max_tokens=8000,
    thinking={"type": "adaptive"},
    system=_CACHED_REPORT_SYSTEM,
    messages=[{"role": "user", "content": [
        cached_ctx_block,      # shared context — cached, free on calls 2 & 3
        {"type": "text", "text": report_prompt},  # unique per report
    ]}],
) as stream:
    for text in stream.text_stream:
        full_text += text
```

**Why streaming:** Report generation produces 1,000–3,000+ word documents. Streaming prevents request timeouts and lets the UI display progress.

**Why prompt caching across 3 calls:** The shared context block (customer data + conflicts + actions) is identical in all three calls. Caching it means calls 2 and 3 are billed at ~10% input token cost.

---

## 6-Layer Context Engineering

**Files:** `src/context/assembler.py`, `src/context/compressor.py`, `src/context/router.py`

| Layer | Content | Trimmed if over budget? |
|-------|---------|------------------------|
| Layer 1 | System role + ontology vocabulary | Never |
| Layer 2 | RDF ontology facts (SPARQL-extracted) | Never |
| Layer 3 | JSON Schema constraints per artifact | Never |
| Layer 4 | Guardrailed artifact data | **Yes — trimmed first** |
| Layer 5 | SPARQL-detected conflict seeds | Never |
| Layer 6 | Task instruction | Never |

Token budget: 120,000 chars. Layer 4 is trimmed last-resort to fit.

---

## Ontology Integration

**Files:** `src/ontology/graph_builder.py`, `src/ontology/sparql_detector.py`, `src/ontology/reasoner.py`  
**Ontology:** `data/ontology/northwind_escalation.ttl` (OWL/Turtle)

```
Key OWL constraint:
  nw:Open owl:disjointWith nw:Resolved

After OWL-RL reasoning (owlrl), any artifact asserting both statuses
triggers an inferred conflict — detected by SPARQL before Claude runs.
```

SPARQL conflicts feed into Layer 5 of the context as **seed conflicts** — Claude confirms, extends, and adds any the queries missed.

---

## Pipeline Steps

| Step | What happens | Output file |
|------|-------------|-------------|
| 1 | Load 7 artifacts | — |
| 2 | Consolidate → interim state | `outputs/consolidated_state.json` |
| 3 | Guardrails (fix templates) | `outputs/guardrail_report.json` |
| 4 | Build RDF graph + OWL-RL reasoning | `outputs/knowledge_graph.ttl` |
| 5 | SPARQL conflict detection + context assembly | `outputs/sparql_conflicts.json`, `outputs/context_manifest.json` |
| 6 | Claude AI analysis (Tool Runner, 6-layer context) | — |
| 7 | HITL confidence review | `outputs/override_log.jsonl` |
| 8 | Streaming report generation (3 calls) | `outputs/executive_summary.md`, `outputs/conflict_report.md`, `outputs/action_items.md`, `outputs/customer_email.md` |

---

## Run

```bash
python -m streamlit run dashboard.py
```

Or pipeline only (no UI):

```bash
python -m src.pipeline
```

Requires `ANTHROPIC_API_KEY` environment variable. Falls back to rule-based analysis if not set.

---

## Dependencies

```
anthropic>=0.116.0   # Claude API SDK + Tool Runner + streaming
rdflib>=7.0.0        # RDF graph builder + SPARQL queries
owlrl>=6.0.2         # OWL-RL semantic reasoning
jinja2>=3.1.0        # Prompt template rendering
streamlit>=1.35.0    # Dashboard UI
plotly>=5.22.0       # Charts
```
