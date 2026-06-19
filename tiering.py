"""
tiering.py — danger-tier classification for agent write-actions.

Pure, dependency-free core shared by `agent.py` (the LangGraph HITL demo) and
the `agent-guardrails` wrapper. Classifies a proposed action into a tier and a
decision so the calling graph knows whether to auto-run, confirm, or pause for a
human.

Reconstructed to the contract `agent.py` calls:
    Action(name, operation, domain, reversible, monetary_amount)
    Operation("read" | "write" | "execute" | "delete")
    classify(action) -> (tier: int, decision: str, reason: str)
        decision ∈ {"allow", "confirm", "require_human", "deny"}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Operation(str, Enum):
    """What the action does to the world. `str` mixin → `Operation("write")` works."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"


@dataclass
class Action:
    """A single action an agent proposes to take."""
    name: str
    operation: Operation = Operation.WRITE
    domain: str = "general"
    reversible: bool = True
    monetary_amount: float = 0.0
    bulk_count: int = 0  # number of rows/records affected (for bulk detection)


@dataclass(frozen=True)
class Policy:
    """Tunable thresholds. The one rule you cannot relax: Tier 3 → human, always."""
    always_human_domains: frozenset[str] = field(
        default_factory=lambda: frozenset({"finance", "auth", "billing", "legal"})
    )
    monetary_threshold: float = 100.0      # amount at/above which a write needs a human
    bulk_threshold: int = 25               # row count at/above which a write needs a human
    hard_deny_bulk_delete: int | None = 1000  # bulk DELETE at/above this is blocked outright; None disables
    auto_operations: frozenset[Operation] = field(
        default_factory=lambda: frozenset({Operation.READ})
    )


DEFAULT_POLICY = Policy()


def classify(action: Action, policy: Policy = DEFAULT_POLICY) -> tuple[int, str, str]:
    """
    Return (tier, decision, reason).

    Tier 1 → "allow"          : read-only / safe, runs immediately
    Tier 2 → "confirm"        : reversible low-impact write, lightweight confirmation
    Tier 3 → "require_human"  : sensitive domain / over-threshold / irreversible / bulk → HITL
    Tier 3 → "deny"           : catastrophic destructive bulk → hard-blocked
    """
    op = action.operation
    dom = (action.domain or "general").lower()

    # --- hard deny: catastrophic destructive bulk ---
    if (
        policy.hard_deny_bulk_delete is not None
        and op == Operation.DELETE
        and action.bulk_count >= policy.hard_deny_bulk_delete
    ):
        return 3, "deny", (
            f"bulk delete of {action.bulk_count} ≥ hard-deny limit "
            f"{policy.hard_deny_bulk_delete}"
        )

    # --- Tier 1: configured-safe operations run immediately ---
    if op in policy.auto_operations:
        return 1, "allow", f"{op.value} is an auto-operation"

    # --- Tier 3: the four ways a write reaches a human (NEVER configurable away) ---
    if dom in policy.always_human_domains:
        return 3, "require_human", f"domain '{dom}' always requires human approval"
    if action.monetary_amount >= policy.monetary_threshold:
        return 3, "require_human", (
            f"amount {action.monetary_amount:g} ≥ threshold {policy.monetary_threshold:g}"
        )
    if not action.reversible:
        return 3, "require_human", "action is irreversible"
    if action.bulk_count >= policy.bulk_threshold:
        return 3, "require_human", (
            f"bulk operation on {action.bulk_count} ≥ threshold {policy.bulk_threshold}"
        )

    # --- Tier 2: everything else (reversible, low-impact write) ---
    return 2, "confirm", "reversible low-impact write"


if __name__ == "__main__":
    # Mirror the demo table the agent-guardrails README advertises.
    samples = [
        Action("List inventory items", Operation.READ, "inventory"),
        Action("Update product description", Operation.WRITE, "catalog"),
        Action("Issue supplier payment", Operation.EXECUTE, "finance",
               reversible=False, monetary_amount=4200.0),
        Action("Recompute payroll lines", Operation.WRITE, "payroll", bulk_count=312),
        Action("Purge archived records", Operation.DELETE, "ops", bulk_count=5000),
    ]
    for a in samples:
        tier, decision, reason = classify(a)
        print(f"{a.name:32s} | T{tier} {decision:13s} | {reason}")
