"""
A LangGraph agent that pauses for human approval before high-impact actions.

Graph:

    START → plan → govern ─┬─(tier 1/2)────────────► execute → END
                           └─(tier 3: require_human)► human_review → execute → END

`human_review` calls `interrupt()`, which suspends the run and surfaces the
decision to the caller. The caller resumes with `Command(resume=<approval>)`.
The graph is checkpointed (MemorySaver), so the paused state survives between
the interrupt and the resume — exactly the durability you need in production.

No LLM / API key required: the `plan` node maps a task to a proposed action
deterministically so the governance + HITL machinery can be demonstrated on its
own. In a real agent, `plan` is where the model proposes tool calls.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from tiering import Action, Operation, classify


class AgentState(TypedDict, total=False):
    task: dict
    action: dict
    tier: int
    decision: str
    reason: str
    approved: Optional[bool]
    result: str
    audit: list[str]


def plan(state: AgentState) -> dict:
    """Turn a task into a proposed action. (In production: the LLM does this.)"""
    t = state["task"]
    action = Action(
        name=t["name"],
        operation=Operation(t.get("operation", "write")),
        domain=t.get("domain", "general"),
        reversible=t.get("reversible", True),
        monetary_amount=t.get("monetary_amount", 0.0),
    )
    return {"action": action.__dict__ | {"operation": action.operation.value},
            "audit": [f"planned: {action.name}"]}


def govern(state: AgentState) -> dict:
    """Classify the action; pre-decide everything except Tier 3."""
    a = state["action"]
    action = Action(
        name=a["name"], operation=Operation(a["operation"]), domain=a["domain"],
        reversible=a["reversible"], monetary_amount=a["monetary_amount"],
    )
    tier, decision, reason = classify(action)
    approved: Optional[bool]
    if decision == "allow":
        approved = True
    elif decision == "confirm":
        approved = True  # auto-confirm Tier 2 in this demo; Tier 3 never auto
    else:
        approved = None  # decided by human_review
    return {"tier": tier, "decision": decision, "reason": reason,
            "approved": approved,
            "audit": state["audit"] + [f"govern: T{tier} {decision} ({reason})"]}


def human_review(state: AgentState) -> dict:
    """Pause for a human. The caller resumes with Command(resume=<approval>)."""
    approval = interrupt({
        "action": state["action"]["name"],
        "tier": state["tier"],
        "reason": state["reason"],
        "question": "Approve this high-impact action?",
    })
    if isinstance(approval, bool):
        approved = approval
    else:
        approved = str(approval).strip().lower() in {"y", "yes", "approve", "true", "ok"}
    return {"approved": approved,
            "audit": state["audit"] + [f"human decision: {approved}"]}


def execute(state: AgentState) -> dict:
    """Run the action only if it was approved and not denied."""
    if state.get("approved") and state.get("decision") != "deny":
        result = f"EXECUTED · {state['action']['name']}"
    else:
        result = f"BLOCKED · {state['action']['name']}"
    return {"result": result, "audit": state["audit"] + [result]}


def _route(state: AgentState) -> str:
    return "human_review" if state["decision"] == "require_human" else "execute"


def build_agent():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("govern", govern)
    g.add_node("human_review", human_review)
    g.add_node("execute", execute)

    g.add_edge(START, "plan")
    g.add_edge("plan", "govern")
    g.add_conditional_edges("govern", _route, {"human_review": "human_review", "execute": "execute"})
    g.add_edge("human_review", "execute")
    g.add_edge("execute", END)

    return g.compile(checkpointer=MemorySaver())
