"""
Northwind Escalation Synthesizer
Reads 7 artifacts, runs Claude claude-opus-5 agentic analysis, and writes 3 output reports.
Falls back to rule-based analysis when ANTHROPIC_API_KEY is not configured.
"""

import os
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"

sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.loaders import load_all
from src.conflict_detector import detect_all
from src.synthesizer import (
    generate_executive_summary,
    generate_conflict_report,
    generate_action_items,
)

SEVERITY_COLOR = {"HIGH": "\033[91m", "MEDIUM": "\033[93m", "LOW": "\033[92m"}
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
YELLOW = "\033[93m"


def fmt_time(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def banner(text: str) -> None:
    width = 70
    print(f"\n{BOLD}{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * width}{RESET}\n")


def section(text: str) -> None:
    print(f"\n{BOLD}  {text}{RESET}")
    print(f"  {'-' * 60}")


def run() -> None:
    banner("NORTHWIND ESCALATION SYNTHESIZER  |  INC-2026-0812")

    t0 = time.perf_counter()

    # ── Step 1: Load artifacts ─────────────────────────────────────────────────
    section("Step 1 -- Loading 7 artifacts")
    artifacts = load_all(DATA_DIR)
    t1 = time.perf_counter()
    for a in artifacts:
        print(f"  [OK]  [{a['source']:16s}]  {a['file']}")

    # ── Step 2: AI or rule-based analysis ─────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    use_ai = bool(api_key)

    if use_ai:
        section("Step 2 -- AI Analysis  (claude-opus-5 + Tool Runner)")
        print(f"  {CYAN}Mode: Claude AI (agentic tool use + streaming){RESET}\n")
        try:
            import anthropic
            from src.ai_synthesizer import synthesize

            ai_conflicts, ai_actions, exec_md, conflict_md, actions_md = synthesize(artifacts)
            t2 = time.perf_counter()

            # Also run rule-based for comparison
            rule_conflicts = detect_all(artifacts)

            print(f"\n  AI detected {len(ai_conflicts)} conflicts, {len(ai_actions)} actions")
            print(f"  Rule-based detected {len(rule_conflicts)} conflicts (for cross-check)")

            conflicts = ai_conflicts  # AI is primary
            outputs = [
                ("executive_summary.md", exec_md),
                ("conflict_report.md", conflict_md),
                ("action_items.md", actions_md),
            ]

        except Exception as e:
            print(f"  {YELLOW}[WARN] AI synthesis failed: {e}{RESET}")
            print(f"  {YELLOW}Falling back to rule-based analysis.{RESET}")
            use_ai = False

    if not use_ai:
        section("Step 2 -- Rule-based conflict detection")
        print(f"  {YELLOW}Mode: Rule-based (set ANTHROPIC_API_KEY to enable Claude AI){RESET}\n")
        conflicts = detect_all(artifacts)
        t2 = time.perf_counter()
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

        # Generate rule-based reports
        exec_md = generate_executive_summary(artifacts, conflicts)
        conflict_md = generate_conflict_report(artifacts, conflicts)
        actions_md = generate_action_items(artifacts, conflicts)
        outputs = [
            ("executive_summary.md", exec_md),
            ("conflict_report.md", conflict_md),
            ("action_items.md", actions_md),
        ]

    # ── Step 3: Write output reports ───────────────────────────────────────────
    section("Step 3 -- Writing 3 output reports")
    OUT_DIR.mkdir(exist_ok=True)

    for filename, content in outputs:
        path = OUT_DIR / filename
        path.write_text(content, encoding="utf-8")
        lines = content.count("\n")
        print(f"  [DONE]  outputs/{filename}  ({lines} lines)")

    t3 = time.perf_counter()

    load_elapsed = t1 - t0
    analysis_elapsed = t2 - t1
    gen_elapsed = t3 - t2
    total_elapsed = t3 - t0

    # ── Step 4: Summary ────────────────────────────────────────────────────────
    banner("SYNTHESIS COMPLETE")

    account = next(a for a in artifacts if a["source"] == "Account Summary")
    telemetry = next(a for a in artifacts if a["source"] == "Telemetry")
    jira = next(a for a in artifacts if a["source"] == "Jira")
    email_art = next(a for a in artifacts if a["source"] == "Executive Email")

    if use_ai:
        high = sum(1 for c in conflicts if c.get("severity") == "HIGH")
        med = sum(1 for c in conflicts if c.get("severity") == "MEDIUM")
        mode_label = f"{CYAN}Claude claude-opus-5 (AI){RESET}"
    else:
        high = sum(1 for c in conflicts if c.severity == "HIGH")
        med = sum(1 for c in conflicts if c.severity == "MEDIUM")
        mode_label = f"{YELLOW}Rule-based (no API key){RESET}"

    print(f"  Mode      :  {mode_label}")
    print(f"  Customer  :  {account['customer']} ({account['tier']}) -- renewal risk: {account['renewal_risk']}")
    print(f"  Health    :  {account['health_score']}/100 (declining)  |  NPS: {account['nps_score']}/10")
    print(f"  VP Email  :  \"{email_art.get('subject', '')[:55]}\"")
    print(f"  Renewal   :  {email_art.get('renewal_threat') and RED + 'THREATENED' + RESET or 'OK'}")
    print(f"  Conflicts :  {SEVERITY_COLOR['HIGH']}{high} HIGH{RESET}  /  {SEVERITY_COLOR['MEDIUM']}{med} MEDIUM{RESET}")
    print(f"  Telemetry :  {telemetry.get('current_error_rate_pct')}% error rate  |  Status: {telemetry.get('current_status', '').upper()}")
    print(f"  Open Jira :  {', '.join(jira['critical_open_tickets']) or 'None'}")
    print(f"  Stuck ord :  {telemetry['stuck_orders_count']} (telemetry)  |  Known: {', '.join(jira['known_affected_orders'])}")
    print()

    W = 56
    print(f"  {BOLD}{CYAN}-- Before vs After {'─' * (W - 18)}{RESET}")
    print()
    print(f"  {BOLD}{RED}BEFORE{RESET}{DIM} (manual triage -- 2 to 4 hours):{RESET}")
    print(f'  {DIM}"Customer reports order processing failures.')
    print(f'   Engineering says fixed. Need to investigate further."{RESET}')
    print(f"  {RED}x Vague   x No sources   x No conflicts   x No actions{RESET}")
    print()
    print(f"  {BOLD}{GREEN}AFTER{RESET}{GREEN} (this synthesizer -- {fmt_time(total_elapsed)} total):{RESET}")
    print(f'  {GREEN}"{account["customer"]} | {account["sla_breaches_90d"]} SLA breaches [Account Summary].')
    print(f'   Postmortem: RESOLVED [Postmortem]. Customer: NOT RESOLVED [Zendesk/Executive Email].')
    print(f'   Error rate {telemetry["current_error_rate_pct"]}% vs 0.2% baseline [Telemetry].')
    print(f'   {len(jira.get("critical_open_tickets", []))} critical Jira tickets open. NWAPI-3362 unassigned.')
    print(f'   VP Derek Hartley threatening non-renewal + competitor evaluation [Executive Email].')
    print(f'   Recommended: assign NWAPI-3362, send exec update, run order cleanup."{RESET}')
    print(f"  {GREEN}+ Specific  + Cited  + Conflicts flagged  + Actionable{RESET}")
    print()

    print(f"  {BOLD}{CYAN}-- Timing {'─' * (W - 9)}{RESET}")
    print(f"  {'Artifact load':<20}: {GREEN}{fmt_time(load_elapsed)}{RESET}")
    print(f"  {'AI analysis':<20}: {GREEN}{fmt_time(analysis_elapsed)}{RESET}  (agentic tool calls)" if use_ai else
          f"  {'Rule analysis':<20}: {GREEN}{fmt_time(analysis_elapsed)}{RESET}")
    print(f"  {'Report generation':<20}: {GREEN}{fmt_time(gen_elapsed)}{RESET}  (3x streaming)" if use_ai else
          f"  {'Report generation':<20}: {GREEN}{fmt_time(gen_elapsed)}{RESET}")
    print(f"  {BOLD}{'TOTAL':<20}: {GREEN}{fmt_time(total_elapsed)}{RESET}{BOLD}  vs 4-8 hours manual{RESET}")
    print()
    print(f"  Reports written to:  outputs/")
    print()


if __name__ == "__main__":
    run()
