"""
Run the agent on several tasks and drive the human-in-the-loop flow.

For Tier 3 tasks the graph pauses (surfacing `__interrupt__`); we then resume
with an approval decision via `Command(resume=...)`, just like a real approval
UI / Slack callback would.
"""
from __future__ import annotations

import uuid

from langgraph.types import Command

from agent import build_agent

agent = build_agent()


def run(task: dict, approval: bool | None = None) -> str:
    """Run one task. If it interrupts, resume with `approval`."""
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    state = agent.invoke({"task": task}, cfg)

    if "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        print(f"  ⏸  PAUSED for human → {payload['action']} "
              f"(T{payload['tier']}: {payload['reason']})")
        print(f"     human answers: {'APPROVE' if approval else 'DENY'}")
        state = agent.invoke(Command(resume=bool(approval)), cfg)

    return state["result"]


TASKS = [
    ({"name": "Read open invoices", "operation": "read", "domain": "finance"}, None),
    ({"name": "Update product label", "operation": "write", "domain": "catalog"}, None),
    ({"name": "Pay supplier €4,200", "operation": "execute", "domain": "finance",
      "monetary_amount": 4200.0, "reversible": False}, True),
    ({"name": "Delete customer account", "operation": "execute", "domain": "auth",
      "reversible": False}, False),
]

if __name__ == "__main__":
    print("=" * 64)
    for task, approval in TASKS:
        print(f"TASK: {task['name']}")
        print(f"  → {run(task, approval)}\n")
    print("=" * 64)
