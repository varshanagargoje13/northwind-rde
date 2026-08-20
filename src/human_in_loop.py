"""
Human-in-the-Loop (HITL) module.

Implements the "human decision-making" layer from the architecture:
  - Confidence scoring for every conflict and action item
  - "I'm not sure" signals for low-confidence outputs
  - DRI (Directly Responsible Individual) review interface
  - Override logging — full audit trail in outputs/override_log.jsonl
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OVERRIDE_LOG = Path("outputs/override_log.jsonl")

BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
DIM    = "\033[2m"


@dataclass
class ConfidenceSignal:
    item_type: str    # "conflict" | "action"
    item_id: str
    confidence: str   # "HIGH" | "MEDIUM" | "LOW"
    score: float      # 0.0–1.0
    uncertain: bool   # True → system says "I'm not sure"
    reason: str


def _score_conflict(conflict: dict, total_artifacts: int = 7) -> ConfidenceSignal:
    sources = conflict.get("sources", [])
    severity = conflict.get("severity", "LOW")

    source_ratio   = len(sources) / total_artifacts
    severity_boost = {"HIGH": 0.25, "MEDIUM": 0.10, "LOW": 0.0}.get(severity, 0.0)
    score = min(1.0, source_ratio + severity_boost)

    if score >= 0.65:
        confidence, uncertain = "HIGH",   False
    elif score >= 0.40:
        confidence, uncertain = "MEDIUM", False
    else:
        confidence, uncertain = "LOW",    True

    return ConfidenceSignal(
        item_type="conflict",
        item_id=conflict.get("category", "unknown"),
        confidence=confidence,
        score=round(score, 2),
        uncertain=uncertain,
        reason=f"{len(sources)}/{total_artifacts} sources involved; severity={severity}",
    )


def _score_action(action: dict) -> ConfidenceSignal:
    priority = action.get("priority", "P3")
    sources  = action.get("sources", [])

    p_score  = {"P0": 1.0, "P1": 0.80, "P2": 0.60, "P3": 0.40}.get(priority, 0.40)
    src_score = min(1.0, len(sources) / 3)
    score    = round((p_score + src_score) / 2, 2)

    if score >= 0.65:
        confidence, uncertain = "HIGH",   False
    elif score >= 0.45:
        confidence, uncertain = "MEDIUM", False
    else:
        confidence, uncertain = "LOW",    True

    return ConfidenceSignal(
        item_type="action",
        item_id=action.get("title", "unknown")[:50],
        confidence=confidence,
        score=score,
        uncertain=uncertain,
        reason=f"priority={priority}; {len(sources)} sources cited",
    )


def build_confidence_signals(
    conflicts: list[dict],
    actions: list[dict],
) -> tuple[list[ConfidenceSignal], list[ConfidenceSignal]]:
    """Score every conflict and action item. Returns (conflict_signals, action_signals)."""
    return (
        [_score_conflict(c) for c in conflicts],
        [_score_action(a) for a in actions],
    )


def _log_override(item_type: str, item_id: str, original: str, override: str, dri: str) -> None:
    OVERRIDE_LOG.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dri": dri,
        "item_type": item_type,
        "item_id": item_id,
        "original": original,
        "override": override,
    }
    with open(OVERRIDE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def dri_review(
    conflicts: list[dict],
    actions: list[dict],
    conflict_signals: list[ConfidenceSignal],
    action_signals: list[ConfidenceSignal],
) -> dict:
    """
    Print the DRI review panel and return a result dict.

    Thin-slice implementation: runs non-interactively, auto-approves
    HIGH/MEDIUM confidence items, flags LOW-confidence items in the
    audit log with dri=SYSTEM and override=auto-approved-uncertain.
    In production this would pause for human approval.
    """
    print(f"\n  {BOLD}{CYAN}-- Human-in-the-Loop (HITL) Review {'─' * 25}{RESET}\n")
    print(f"  {DIM}DRI reviews synthesized output before comms are sent.{RESET}\n")

    uncertain_items: list[dict] = []
    approved_count  = 0

    # ── Conflict confidence signals ────────────────────────────────────────────
    print(f"  {BOLD}Conflict confidence signals:{RESET}")
    for conflict, sig in zip(conflicts, conflict_signals):
        cat = conflict.get("category", "")
        col = RED if sig.uncertain else GREEN
        flag = f"  {YELLOW}** I'M NOT SURE — DRI review required{RESET}" if sig.uncertain else ""
        print(f"    {col}[{'?' if sig.uncertain else '+'}] [{sig.confidence} {sig.score:.2f}]{RESET}  "
              f"{cat}  {DIM}({sig.reason}){RESET}{flag}")
        if sig.uncertain:
            uncertain_items.append({"type": "conflict", "id": sig.item_id, "signal": sig})
        else:
            approved_count += 1

    # ── Action confidence signals ──────────────────────────────────────────────
    print(f"\n  {BOLD}Action item confidence signals:{RESET}")
    for action, sig in zip(actions, action_signals):
        title = action.get("title", "")
        prio  = action.get("priority", "")
        col   = RED if sig.uncertain else GREEN
        flag  = f"  {YELLOW}** I'M NOT SURE — DRI review required{RESET}" if sig.uncertain else ""
        print(f"    {col}[{'?' if sig.uncertain else '+'}] [{sig.confidence} {sig.score:.2f}]{RESET}  "
              f"[{prio}] {title[:55]}  {DIM}({sig.reason}){RESET}{flag}")
        if sig.uncertain:
            uncertain_items.append({"type": "action", "id": sig.item_id, "signal": sig})
        else:
            approved_count += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    total = approved_count + len(uncertain_items)
    print(f"\n  {BOLD}Review summary:{RESET}")
    print(f"    Auto-approved (HIGH/MEDIUM confidence) : {GREEN}{approved_count}/{total}{RESET}")
    unc_col = YELLOW if uncertain_items else GREEN
    print(f"    Flagged uncertain (LOW confidence)     : {unc_col}{len(uncertain_items)}/{total}{RESET}")

    if uncertain_items:
        print(f"\n  {YELLOW}[HITL] {len(uncertain_items)} item(s) flagged as uncertain.{RESET}")
        print(f"  {YELLOW}        Production: DRI approves/rejects each before comms send.{RESET}")
        print(f"  {YELLOW}        Thin slice: auto-approving; logged to override_log.jsonl.{RESET}")
        for item in uncertain_items:
            _log_override(
                item_type=item["type"],
                item_id=item["id"],
                original=f"confidence={item['signal'].confidence}, score={item['signal'].score}",
                override="auto-approved-uncertain",
                dri="SYSTEM",
            )
    else:
        print(f"\n  {GREEN}[HITL] All items at HIGH/MEDIUM confidence — no DRI flags.{RESET}")

    print(f"  {GREEN}[HITL] Output approved. Audit trail: outputs/override_log.jsonl{RESET}")

    return {
        "approved": approved_count,
        "uncertain": len(uncertain_items),
        "total": total,
        "all_approved": True,
        "uncertain_items": uncertain_items,
    }
