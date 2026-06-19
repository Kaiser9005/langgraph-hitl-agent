# langgraph-hitl-agent

**A runnable LangGraph agent that pauses for human approval before high-impact actions.**

Autonomous agents are fine until they *write*. This is the smallest honest example
of the production pattern: the agent plans an action, a governance node classifies
how dangerous it is, and anything Tier 3 (sensitive domain, over-threshold,
irreversible, or bulk) **suspends the graph** and waits for a human — using
LangGraph's native [`interrupt()`](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/) +
a checkpointer, so the paused run survives between the interrupt and the resume.

```
START → plan → govern ─┬─ (tier 1/2) ───────────────► execute → END
                       └─ (tier 3: require_human) ───► human_review → execute → END
```

No LLM or API key required to run the demo — the `plan` node maps a task to a
proposed action deterministically, so you can see the governance + HITL machinery
on its own. In a real agent, `plan` is where the model proposes tool calls.

## Files

| File | What it is |
|---|---|
| `tiering.py` | Pure, zero-dep danger-tier classifier (`Action` / `Operation` / `classify`). Shared core. |
| `agent.py`   | The LangGraph graph: `plan → govern → (human_review) → execute`, checkpointed with `MemorySaver`. |
| `demo.py`    | Drives the agent end-to-end; resumes a paused run via `Command(resume=...)`. |
| `server.py`  | Optional: the same guarded action exposed as a FastMCP tool. |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python tiering.py        # see the tier classification table (zero deps)
python demo.py           # run the agent: a Tier-2 write auto-proceeds, a Tier-3 payment pauses for you
```

`demo.py` walks two tasks through the graph:
- a **reversible catalog write** → Tier 2 → proceeds, and
- an **irreversible finance payment** → Tier 3 → the graph *interrupts*; you approve or deny at the prompt, and only an approval lets `execute` run.

## The tiers

| Tier | Meaning | Default |
|---|---|---|
| **1 — auto** | read-only / safe | runs immediately |
| **2 — confirm** | reversible low-impact write | lightweight confirmation (relaxable) |
| **3 — require_human** | sensitive domain (`finance`/`auth`/…), amount ≥ threshold, irreversible, or bulk ≥ threshold | **always** a human (never configurable away) |
| **3 — deny** | catastrophic destructive bulk (e.g. delete ≥ 1000) | hard-blocked |

Tune the thresholds via `Policy` in `tiering.py`. The one invariant: you can relax
Tier 2, but a Tier 3 human approval can never be configured away.

## Why it exists

Generalized from the governance layer of a production agentic ERP (an AI assistant
with 20+ governed write-actions). The companion repo
[`agent-guardrails`](../agent-guardrails) is the framework-agnostic version of the
same idea (a decorator + audit trail, zero deps); this repo shows it wired into a
real LangGraph control flow with `interrupt()`/checkpoint durability.

## License

MIT.
