"""
mcp-server-starter — a small but real MCP server (FastMCP).

Exposes a tiny inventory domain as MCP tools an agent can call. It demonstrates
the pattern that matters in production: reads and low-impact writes run freely,
but a destructive action is *guarded* — the server refuses unless a confirmation
token is supplied, forcing the agent to surface the decision to a human.

Run it:
    pip install -r requirements.txt
    python server.py            # stdio transport (for Claude Desktop / Cursor)

Or inspect it with the MCP Inspector:
    npx @modelcontextprotocol/inspector python server.py
"""
from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("inventory-starter")

# In-memory store. Swap for Postgres/Supabase in a real deployment.
_ITEMS: dict[str, dict] = {}


@mcp.tool()
def list_items() -> list[dict]:
    """List all inventory items."""
    return list(_ITEMS.values())


@mcp.tool()
def get_item(item_id: str) -> dict:
    """Get a single inventory item by id."""
    item = _ITEMS.get(item_id)
    if item is None:
        raise ValueError(f"No item with id {item_id!r}")
    return item


@mcp.tool()
def add_item(name: str, quantity: int = 0) -> dict:
    """Add a new inventory item. Returns the created item."""
    if quantity < 0:
        raise ValueError("quantity must be >= 0")
    item = {"id": uuid.uuid4().hex[:8], "name": name, "quantity": quantity}
    _ITEMS[item["id"]] = item
    return item


@mcp.tool()
def adjust_quantity(item_id: str, delta: int) -> dict:
    """Adjust an item's quantity by `delta` (can be negative)."""
    item = get_item(item_id)
    new_qty = item["quantity"] + delta
    if new_qty < 0:
        raise ValueError("resulting quantity would be negative")
    item["quantity"] = new_qty
    return item


@mcp.tool()
def delete_all_items(confirm_token: str = "") -> dict:
    """
    Delete the entire inventory. GUARDED: destructive.

    Call once with no token to receive a one-time confirmation token, surface it
    to a human, then call again with that token to actually delete. This keeps an
    irreversible action behind an explicit human decision instead of letting the
    agent wipe data on its own.
    """
    expected = f"CONFIRM-{len(_ITEMS)}"
    if confirm_token != expected:
        return {
            "status": "confirmation_required",
            "message": f"This will delete {len(_ITEMS)} items and cannot be undone.",
            "confirm_token": expected,
            "how_to_proceed": "Get human approval, then call again with this confirm_token.",
        }
    count = len(_ITEMS)
    _ITEMS.clear()
    return {"status": "deleted", "items_removed": count}


@mcp.resource("inventory://summary")
def inventory_summary() -> str:
    """A human-readable summary of current inventory."""
    if not _ITEMS:
        return "Inventory is empty."
    lines = [f"- {i['name']}: {i['quantity']}" for i in _ITEMS.values()]
    return f"{len(_ITEMS)} item(s):\n" + "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
