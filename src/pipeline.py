"""
Northwind Escalation Synthesizer — core pipeline orchestration.

Steps:
  1. Load 7 artifacts
  2. Consolidate all sources → outputs/consolidated_state.json  (interim state)
  3. Guardrails — per-artifact fix templates → outputs/guardrail_report.json
  4. AI or rule-based conflict detection  (on guardrailed artifacts)
  5. Human-in-the-Loop (HITL) confidence review
  6. Write output reports
  7. Print before/after summary + timing
"""

import os
import sys
import textwrap
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .loaders import load_all
from .consolidator import consolidate, save as save_consolidated_state
from .guardrails import apply_all as apply_guardrails, save_report as save_guardrail_report
from .conflict_detector import detect_all
from .report_generator import (
    generate_executive_summary,
    generate_conflict_report,
    generate_action_items,
    generate_customer_email,
)
from .human_in_loop import build_confidence_signals, dri_review

ROOT    = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR  = ROOT / "outputs"

SEVERITY_COLOR = {"HIGH": "\033[91m", "MEDIUM": "\033[93m", "LOW": "\033[92m"}
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
DIM    = "\033[2m"
YELLOW = "\033[93m"


def _fmt_time(seconds: float) -> str:
    return f"{seconds * 1000:.0f}ms" if seconds < 1.0 else f"{seconds:.2f}s"


def _banner(text: str) -> None:
    width = 70
    print(f"\n{BOLD}{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * width}{RESET}\n")


def _section(text: str) -> None:
    print(f"\n{BOLD}  {text}{RESET}")
    print(f"  {'-' * 60}")


def run() -> None:
    _banner("NORTHWIND ESCALATION SYNTHESIZER  |  INC-2026-0812")
    t0 = time.perf_counter()

    # ── Step 1: Load artifacts ─────────────────────────────────────────────────
    _section("Step 1 -- Loading 7 artifacts")
    artifacts = load_all(DATA_DIR)
    t1 = time.perf_counter()
    for a in artifacts:
        print(f"  [OK]  [{a['source']:16s}]  {a['file']}")

    # ── Step 2: Consolidate — merge and persist interim state ──────────────────
    _section("Step 2 -- Consolidating 7 sources → interim state")
    state = consolidate(artifacts)
    state_path = save_consolidated_state(state, OUT_DIR)

    sigs = state["conflict_signals"]
    print(f"  [OK]  Consolidated state saved  →  outputs/consolidated_state.json")
    print(f"\n  Interim state summary:")
    print(f"    Sources merged      : {state['source_count']}")
    print(f"    Orders claims range : "
          f"{state['orders_impact']['min_claim']} – {state['orders_impact']['max_claim']} "
          f"(gap: {state['orders_impact']['gap']})")
    print(f"    Start-time span     : {sigs['start_time_span_hours']}h across sources")
    print(f"    Distinct root causes: {state['root_cause']['distinct_claim_count']}")
    print(f"    Conflict signals    : "
          + ("  ".join(
              f"{YELLOW if v else GREEN}{'✗' if v else '✓'} {k}{RESET}"
              for k, v in sigs.items() if isinstance(v, bool)
          )))
    t2 = time.perf_counter()

    # ── Step 3: Guardrails — per-artifact fix templates ───────────────────────
    _section("Step 3 -- Guardrails (per-artifact fix templates)")
    artifacts, gr_results = apply_guardrails(artifacts)
    gr_path = save_guardrail_report(gr_results, OUT_DIR)

    gr_passed  = sum(1 for r in gr_results if r.status == "PASSED")
    gr_fixed   = sum(1 for r in gr_results if r.status == "FIXED")
    gr_flagged = sum(1 for r in gr_results if r.status == "FLAGGED")

    for r in gr_results:
        icon  = f"{GREEN}✓ PASSED {RESET}" if r.status == "PASSED" \
                else f"{YELLOW}⚠ FIXED  {RESET}" if r.status == "FIXED" \
                else f"{RED}✗ FLAGGED{RESET}"
        fchk  = [c for c in r.checks if c.status == "FLAGGED"]
        extra = f"  {RED}→ {fchk[0].field}: {fchk[0].note}{RESET}" if fchk else ""
        print(f"  {icon}  [{r.source:<16s}]  "
              f"{r.n_passed} passed · {r.n_fixed} fixed · {r.n_flagged} flagged{extra}")

    print(f"\n  Summary: {GREEN}{gr_passed} PASSED{RESET} · "
          f"{YELLOW}{gr_fixed} FIXED{RESET} · {RED}{gr_flagged} FLAGGED{RESET}")
    print(f"  Report : outputs/guardrail_report.json")
    if gr_flagged:
        print(f"\n  {YELLOW}[WARN] {gr_flagged} artifact(s) flagged — "
              f"analysis will proceed on guardrailed data; flagged fields noted in report.{RESET}")
    else:
        print(f"\n  {GREEN}[OK] All artifacts passed/fixed — analysis proceeds on clean data.{RESET}")
    t3 = time.perf_counter()

    # ── Step 4: AI or rule-based analysis  (on guardrailed artifacts) ─────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    use_ai  = bool(api_key)

    if use_ai:
        _section("Step 4 -- AI Analysis  (claude-opus-5 + Tool Runner + Schema Validation)")
        print(f"  {CYAN}Mode: Claude AI (schema-aware agentic tool use + streaming){RESET}")
        print(f"  {DIM}Input: guardrailed artifacts ({gr_passed} passed · {gr_fixed} fixed · {gr_flagged} flagged){RESET}")
        print(f"  {DIM}Schemas: data/schema/ (7 JSON Schema Draft-07 files){RESET}\n")
        try:
            from .ai_synthesizer import synthesize
            ai_conflicts, ai_actions, exec_md, conflict_md, actions_md = synthesize(artifacts, DATA_DIR)
            t4 = time.perf_counter()
            rule_conflicts = detect_all(artifacts)
            print(f"\n  AI detected {len(ai_conflicts)} conflicts, {len(ai_actions)} actions")
            print(f"  Rule-based detected {len(rule_conflicts)} conflicts (cross-check)")
            conflicts = ai_conflicts
            actions   = ai_actions
            customer_email_md = generate_customer_email(artifacts, ai_conflicts)
            outputs   = [
                ("executive_summary.md", exec_md),
                ("conflict_report.md",   conflict_md),
                ("action_items.md",      actions_md),
                ("customer_email.md",    customer_email_md),
            ]
        except Exception as e:
            print(f"  {YELLOW}[WARN] AI synthesis failed: {e}{RESET}")
            print(f"  {YELLOW}Falling back to rule-based analysis.{RESET}")
            use_ai = False

    if not use_ai:
        _section("Step 4 -- Rule-based conflict detection")
        print(f"  {YELLOW}Mode: Rule-based (set ANTHROPIC_API_KEY to enable Claude AI){RESET}")
        print(f"  {DIM}Input: guardrailed artifacts ({gr_passed} passed · {gr_fixed} fixed · {gr_flagged} flagged){RESET}\n")
        conflicts = detect_all(artifacts)
        t4 = time.perf_counter()

        # Build simple action list for HITL scoring (rule-based fallback)
        actions = [
            {"priority": "P0", "title": "Fix stuck orders ORD-55892, ORD-55901",
             "sources": ["Zendesk", "Jira", "Slack"]},
            {"priority": "P0", "title": "Send executive update to Derek Hartley",
             "sources": ["Executive Email", "Account Summary"]},
            {"priority": "P0", "title": "Audit all customers for stuck orders",
             "sources": ["Postmortem", "Slack", "Account Summary"]},
            {"priority": "P1", "title": "Reconcile true order impact count",
             "sources": ["Postmortem", "Zendesk", "Slack", "Jira", "Telemetry"]},
            {"priority": "P1", "title": "Resolve root cause timeline discrepancy",
             "sources": ["Slack", "Postmortem", "Jira", "Telemetry"]},
            {"priority": "P2", "title": "Implement DB connection pool circuit breaker",
             "sources": ["Postmortem", "Jira"]},
            {"priority": "P3", "title": "Schedule emergency QBR with Contoso",
             "sources": ["Account Summary", "Executive Email"]},
        ]

        print(f"\n  Found {len(conflicts)} conflicts:\n")
        for i, c in enumerate(conflicts, 1):
            col = SEVERITY_COLOR.get(c.severity, "")
            print(f"  {i}. {col}[{c.severity:6s}]{RESET}  {c.category}")
            wrapped = textwrap.fill(
                c.description, width=64,
                initial_indent="           ", subsequent_indent="           "
            )
            print(wrapped)
            for d in c.details:
                print(f"           {d.strip()}")
            print()

        exec_md           = generate_executive_summary(artifacts, conflicts)
        conflict_md       = generate_conflict_report(artifacts, conflicts)
        actions_md        = generate_action_items(artifacts, conflicts)
        customer_email_md = generate_customer_email(artifacts, conflicts)
        outputs = [
            ("executive_summary.md", exec_md),
            ("conflict_report.md",   conflict_md),
            ("action_items.md",      actions_md),
            ("customer_email.md",    customer_email_md),
        ]

    # ── Step 5: HITL confidence review ────────────────────────────────────────
    _section("Step 5 -- Human-in-the-Loop (HITL) Review")

    conflict_dicts = [
        {"category": c.category, "severity": c.severity, "sources": c.sources,
         "description": c.description}
        if not isinstance(c, dict) else c
        for c in conflicts
    ]
    c_signals, a_signals = build_confidence_signals(conflict_dicts, actions)
    dri_result = dri_review(conflict_dicts, actions, c_signals, a_signals)

    t5 = time.perf_counter()

    # ── Step 6: Write output reports ───────────────────────────────────────────
    _section("Step 6 -- Writing 5 output reports")
    OUT_DIR.mkdir(exist_ok=True)
    for filename, content in outputs:
        path = OUT_DIR / filename
        path.write_text(content, encoding="utf-8")
        print(f"  [DONE]  outputs/{filename}  ({content.count(chr(10))} lines)")
    print(f"  [DONE]  outputs/guardrail_report.json  (written at step 3)")
    print(f"  [DONE]  outputs/consolidated_state.json  (written at step 2)")

    t6 = time.perf_counter()

    # ── Step 6: Summary ────────────────────────────────────────────────────────
    _banner("SYNTHESIS COMPLETE")

    account   = next(a for a in artifacts if a["source"] == "Account Summary")
    telemetry = next(a for a in artifacts if a["source"] == "Telemetry")
    jira      = next(a for a in artifacts if a["source"] == "Jira")
    email_art = next(a for a in artifacts if a["source"] == "Executive Email")

    if use_ai:
        high = sum(1 for c in conflicts if (c.get("severity") if isinstance(c, dict) else c.severity) == "HIGH")
        med  = sum(1 for c in conflicts if (c.get("severity") if isinstance(c, dict) else c.severity) == "MEDIUM")
        mode_label = f"{CYAN}Claude claude-opus-5 (AI){RESET}"
    else:
        high = sum(1 for c in conflicts if c.severity == "HIGH")
        med  = sum(1 for c in conflicts if c.severity == "MEDIUM")
        mode_label = f"{YELLOW}Rule-based (no API key){RESET}"

    load_e        = t1 - t0
    consolidate_e = t2 - t1
    guardrail_e   = t3 - t2
    analysis_e    = t4 - t3
    hitl_e        = t5 - t4
    gen_e         = t6 - t5
    total_e       = t6 - t0

    print(f"  Mode      :  {mode_label}")
    print(f"  Customer  :  {account['customer']} ({account['tier']}) -- renewal risk: {account['renewal_risk']}")
    print(f"  Health    :  {account['health_score']}/100 (declining)  |  NPS: {account['nps_score']}/10")
    print(f"  VP Email  :  \"{email_art.get('subject', '')[:55]}\"")
    renewal_str = f"{RED}THREATENED{RESET}" if email_art.get("renewal_threat") else "OK"
    print(f"  Renewal   :  {renewal_str}")
    print(f"  Conflicts :  {SEVERITY_COLOR['HIGH']}{high} HIGH{RESET}  /  {SEVERITY_COLOR['MEDIUM']}{med} MEDIUM{RESET}")
    print(f"  Telemetry :  {telemetry.get('current_error_rate_pct')}% error rate  |  "
          f"Status: {telemetry.get('current_status', '').upper()}")
    print(f"  Open Jira :  {', '.join(jira['critical_open_tickets']) or 'None'}")
    print(f"  Stuck ord :  {telemetry['stuck_orders_count']} (telemetry)  |  "
          f"Known: {', '.join(jira['known_affected_orders'])}")
    print(f"  HITL      :  {dri_result['approved']} approved  /  {dri_result['uncertain']} uncertain  "
          f"(audit: outputs/override_log.jsonl)")
    print()

    W = 56
    print(f"  {BOLD}{CYAN}-- Before vs After {'─' * (W - 18)}{RESET}")
    print()
    print(f"  {BOLD}{RED}BEFORE{RESET}{DIM} (manual triage -- 2 to 4 hours):{RESET}")
    print(f'  {DIM}"Customer reports order processing failures.')
    print(f'   Engineering says fixed. Need to investigate further."{RESET}')
    print(f"  {RED}x Vague   x No sources   x No conflicts   x No actions{RESET}")
    print()
    print(f"  {BOLD}{GREEN}AFTER{RESET}{GREEN} (this synthesizer -- {_fmt_time(total_e)} total):{RESET}")
    print(f'  {GREEN}"{account["customer"]} | {account["sla_breaches_90d"]} SLA breaches [Account Summary].')
    print(f'   Postmortem: RESOLVED. Customer: NOT RESOLVED [Zendesk/Executive Email].')
    print(f'   Error rate {telemetry["current_error_rate_pct"]}% vs 0.2% baseline [Telemetry].')
    print(f'   {len(jira.get("critical_open_tickets", []))} critical Jira tickets open. NWAPI-3362 unassigned.')
    print(f'   VP Derek Hartley threatening non-renewal + competitor evaluation.')
    print(f'   Recommended: assign NWAPI-3362, send exec update, run order cleanup."{RESET}')
    print(f"  {GREEN}+ Specific  + Cited  + Conflicts flagged  + HITL reviewed  + Actionable{RESET}")
    print()

    print(f"  {BOLD}{CYAN}-- Timing {'─' * (W - 9)}{RESET}")
    print(f"  {'Artifact load':<22}: {GREEN}{_fmt_time(load_e)}{RESET}")
    print(f"  {'Consolidation':<22}: {GREEN}{_fmt_time(consolidate_e)}{RESET}  → outputs/consolidated_state.json")
    print(f"  {'Guardrails':<22}: {GREEN}{_fmt_time(guardrail_e)}{RESET}"
          f"  {GREEN}{gr_passed}✓{RESET} {YELLOW}{gr_fixed}⚠{RESET} {RED}{gr_flagged}✗{RESET}"
          f"  → outputs/guardrail_report.json")
    if use_ai:
        print(f"  {'AI analysis':<22}: {GREEN}{_fmt_time(analysis_e)}{RESET}  (agentic, on guardrailed data)")
    else:
        print(f"  {'Rule analysis':<22}: {GREEN}{_fmt_time(analysis_e)}{RESET}  (on guardrailed data)")
    print(f"  {'HITL review':<22}: {GREEN}{_fmt_time(hitl_e)}{RESET}")
    if use_ai:
        print(f"  {'Report generation':<22}: {GREEN}{_fmt_time(gen_e)}{RESET}  (3x streaming)")
    else:
        print(f"  {'Report generation':<22}: {GREEN}{_fmt_time(gen_e)}{RESET}")
    print(f"  {BOLD}{'TOTAL':<22}: {GREEN}{_fmt_time(total_e)}{RESET}{BOLD}  vs 4-8 hours manual{RESET}")
    print()
    print(f"  Reports written to:  outputs/")
    print()
