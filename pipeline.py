"""
Northwind Escalation Synthesizer
Reads 7 artifacts, detects cross-source conflicts, and writes 3 output reports.
"""

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"

sys.path.insert(0, str(ROOT))

# Force UTF-8 output on Windows consoles
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

    # Step 1: Load artifacts
    section("Step 1 -- Loading 7 artifacts")
    artifacts = load_all(DATA_DIR)
    for a in artifacts:
        print(f"  [OK]  [{a['source']:16s}]  {a['file']}")

    # Step 2: Detect conflicts
    section("Step 2 -- Detecting cross-artifact conflicts")
    conflicts = detect_all(artifacts)
    print(f"\n  Found {len(conflicts)} conflicts:\n")
    for i, c in enumerate(conflicts, 1):
        col = SEVERITY_COLOR.get(c.severity, "")
        print(f"  {i}. {col}[{c.severity:6s}]{RESET}  {c.category}")
        wrapped = textwrap.fill(c.description, width=64, initial_indent="           ", subsequent_indent="           ")
        print(wrapped)
        for d in c.details:
            print(f"           {d.strip()}")
        print()

    # Step 3: Generate outputs
    section("Step 3 -- Generating 3 output reports")
    OUT_DIR.mkdir(exist_ok=True)

    outputs = [
        ("executive_summary.md", generate_executive_summary(artifacts, conflicts)),
        ("conflict_report.md", generate_conflict_report(artifacts, conflicts)),
        ("action_items.md", generate_action_items(artifacts, conflicts)),
    ]

    for filename, content in outputs:
        path = OUT_DIR / filename
        path.write_text(content, encoding="utf-8")
        lines = content.count("\n")
        print(f"  [DONE]  outputs/{filename}  ({lines} lines)")

    # Step 4: Quick summary
    banner("SYNTHESIS COMPLETE")

    account = next(a for a in artifacts if a["source"] == "Account Summary")
    telemetry = next(a for a in artifacts if a["source"] == "Telemetry")
    jira = next(a for a in artifacts if a["source"] == "Jira")

    high = sum(1 for c in conflicts if c.severity == "HIGH")
    med = sum(1 for c in conflicts if c.severity == "MEDIUM")

    print(f"  Customer  :  {account['customer']} ({account['tier']}) -- renewal risk: {account['renewal_risk']}")
    print(f"  Health    :  {account['health_score']}/100 (declining)  |  NPS: {account['nps_score']}/10")
    print(f"  Conflicts :  {SEVERITY_COLOR['HIGH']}{high} HIGH{RESET}  /  {SEVERITY_COLOR['MEDIUM']}{med} MEDIUM{RESET}")
    print(f"  Eng says  :  RESOLVED   |  Telemetry says: {telemetry['current_status'].upper()}")
    print(f"  Open Jira :  {', '.join(jira['critical_open_tickets']) or 'None'}")
    print(f"  Stuck ord :  {telemetry['stuck_orders_count']} (telemetry)  |  Known: {', '.join(jira['known_affected_orders'])}")
    print()
    print(f"  {BOLD}Key risk:{RESET} Engineering closed INC-2026-0812 but the customer is still")
    print(f"  impacted, telemetry shows degradation, and NWAPI-3362 is unassigned.")
    print()
    print(f"  Reports written to:  outputs/")
    print()


if __name__ == "__main__":
    run()
