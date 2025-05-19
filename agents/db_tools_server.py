import os
import sqlite3
import json

from mcp.server.fastmcp import FastMCP, Context

# 1) Define the FastMCP server and tools
mcp = FastMCP(name="DatabaseAgent")

@mcp.tool()
def get_order_status(order_id: str, ctx: Context) -> str:
    ctx.info(f"Looking up order {order_id}")
    db = os.path.join("db", "real_agent_demo.db")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT status, customer_id FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return json.dumps({"status": None, "customer_id": None})
    status, cid = row
    return json.dumps({"status": status, "customer_id": cid})

@mcp.tool()
def get_customer_orders(customer_id: str, ctx: Context) -> str:
    ctx.info(f"Listing orders for customer {customer_id}")
    db = os.path.join("db", "real_agent_demo.db")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM orders WHERE customer_id=?", (customer_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No orders found."
    return "Your orders:\n" + "\n".join(f"{oid}: {st}" for oid,st in rows)

if __name__ == "__main__":
    # Serve MCP tools over stdio
    mcp.run()
