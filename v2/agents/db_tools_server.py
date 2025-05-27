# db_tools_server.py
import os
import json
import sqlite3
from uuid import uuid4
from datetime import datetime, date
from types import SimpleNamespace
from mcp.server.fastmcp import FastMCP, Context

# --- Load process-flow definitions
FLOW_PATH = os.path.join(os.path.dirname(__file__), "process_flow.json")
with open(FLOW_PATH) as f:
    PROCESS_FLOW = json.load(f)["scenarios"]

# --- Helpers for matching and rendering scenarios

def match_condition(conds, ctx):
    for key, exp in conds.items():
        parts = key.split('.')
        val = ctx
        for p in parts:
            val = val.get(p) if isinstance(val, dict) else None
            if val is None:
                return False
        if isinstance(exp, list):
            if val not in exp:
                return False
        elif isinstance(exp, dict):
            if 'gte' in exp and not (val >= exp['gte']): return False
            if 'gt'  in exp and not (val >  exp['gt']):  return False
            if 'within_days' in exp:
                dt = datetime.strptime(val, "%Y-%m-%d").date()
                if not (0 <= (dt - date.today()).days <= exp['within_days']):
                    return False
            if 'is_today' in exp:
                dt = datetime.strptime(val, "%Y-%m-%d").date()
                if dt != date.today():
                    return False
        else:
            if val != exp:
                return False
    return True


def dict_to_ns(d: dict) -> SimpleNamespace:
    ns = SimpleNamespace()
    for k, v in d.items():
        if isinstance(v, dict):
            setattr(ns, k, dict_to_ns(v))
        else:
            setattr(ns, k, v)
    return ns


def render_template(tpl: str, ctx: dict) -> str:
    ns = dict_to_ns(ctx)
    return tpl.format(**vars(ns))


def apply_process_flow(action: str, context: dict) -> str | None:
    for scen in PROCESS_FLOW:
        if scen['conditions'].get('action') in (action, 'any'):
            conds = {k: v for k, v in scen['conditions'].items() if k != 'action'}
            if match_condition(conds, context):
                return render_template(scen['response_template'], context)
    return None

# --- SQLite helper
def get_conn() -> sqlite3.Connection:
    db_path = os.path.join("db", "real_agent_demo.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- MCP server & tools
mcp = FastMCP(name="DatabaseAgent")

@mcp.tool()
def get_order_status(order_id: str, ctx: Context) -> str:
    db = get_conn()
    cur = db.cursor()
    cur.execute(
        """
        SELECT o.id, o.status, o.eta_date, o.total_amount,
               c.id AS cust_id, c.name, c.loyalty_tier, c.birth_date, c.support_ticket_count
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE o.id = ?
        """,
        (order_id,)
    )
    row = cur.fetchone()
    if not row:
        return json.dumps({"error": "Order not found"})

    order = {
        "id":           row["id"],
        "status":       row["status"],
        "eta_date":     row["eta_date"],
        "total_amount": row["total_amount"]
    }
    customer = {
        "id":                   row["cust_id"],
        "name":                 row["name"],
        "loyalty_tier":         row["loyalty_tier"],
        "birth_date":           row["birth_date"],
        "support_ticket_count": row["support_ticket_count"]
    }
    cur.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?", (customer["id"],))
    customer["total_orders"] = cur.fetchone()[0]

    context = {"order": order, "customer": customer}
    try:
        if (msg := apply_process_flow("get_order_status", context)):
            return json.dumps({"message": msg, "customer_id": customer["id"]})
    except Exception as e:
        return json.dumps({"error": "process_flow_error", "detail": str(e), "trace": traceback.format_exc()})

    return json.dumps({
        "order_id":    order["id"],
        "status":      order["status"],
        "customer_id": customer["id"]
    })

@mcp.tool()
def get_customer_orders(customer_id: str, ctx: Context) -> str:
    db = get_conn()
    cur = db.cursor()
    cur.execute(
        "SELECT id, status FROM orders WHERE customer_id = ?",
        (customer_id,)
    )
    rows = cur.fetchall()
    orders = [{"id": row["id"], "status": row["status"]} for row in rows]
    return json.dumps({"orders": orders})

@mcp.tool()
def cancel_service(subscription_id: str, ctx: Context) -> str:
    db = get_conn()
    cur = db.cursor()
    cur.execute(
        """
        SELECT s.id, s.plan, s.status, s.renewal_date,
               c.id AS cust_id, c.name, c.loyalty_tier, c.birth_date, c.support_ticket_count
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
        """,
        (subscription_id,)
    )
    row = cur.fetchone()
    if not row:
        return json.dumps({"error": "Subscription not found"})

    req_id = f"CR{uuid4().hex[:6]}"
    today = date.today().isoformat()
    cur.execute(
        "INSERT INTO cancellation_requests(id,customer_id,service_id,request_date,status) VALUES(?,?,?,?,?)",
        (req_id, row["cust_id"], subscription_id, today, "Pending")
    )
    db.commit()

    subscription = {
        "id":           row["id"],
        "plan":         row["plan"],
        "status":       row["status"],
        "renewal_date": row["renewal_date"]
    }
    customer = {
        "id":                   row["cust_id"],
        "name":                 row["name"],
        "loyalty_tier":         row["loyalty_tier"],
        "birth_date":           row["birth_date"],
        "support_ticket_count": row["support_ticket_count"]
    }
    context = {"customer": customer, "subscription": subscription}
    try:
        if (msg := apply_process_flow("cancel_service", context)):
            return json.dumps({"message": msg})
    except Exception as e:
        return json.dumps({"error": "process_flow_error", "detail": str(e)})

    return json.dumps({"subscription_id": subscription_id, "status": "cancelled"})

@mcp.tool()
def subscription_status(subscription_id: str, ctx: Context) -> str:
    db = get_conn()
    cur = db.cursor()
    cur.execute(
        """
        SELECT s.id, s.plan, s.status, s.renewal_date,
               c.id AS cust_id, c.name, c.loyalty_tier, c.birth_date, c.support_ticket_count
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
        """,
        (subscription_id,)
    )
    row = cur.fetchone()
    if not row:
        return json.dumps({"error": "Subscription not found"})

    subscription = {
        "id":           row["id"],
        "plan":         row["plan"],
        "status":       row["status"],
        "renewal_date": row["renewal_date"]
    }
    customer = {
        "id":                   row["cust_id"],
        "name":                 row["name"],
        "loyalty_tier":         row["loyalty_tier"],
        "birth_date":           row["birth_date"],
        "support_ticket_count": row["support_ticket_count"]
    }
    context = {"customer": customer, "subscription": subscription}
    try:
        if (msg := apply_process_flow("subscription_status", context)):
            return json.dumps({"message": msg})
    except Exception as e:
        return json.dumps({"error": "process_flow_error", "detail": str(e)})

    return json.dumps({
        "subscription_id": subscription_id,
        "status":          subscription["status"],
        "renewal_date":    subscription["renewal_date"]
    })

@mcp.tool()
def support_request(customer_id: str, ctx: Context) -> str:
    db = get_conn()
    cur = db.cursor()
    cur.execute(
        "SELECT name, loyalty_tier, birth_date, support_ticket_count FROM customers WHERE id = ?",
        (customer_id,)
    )
    row = cur.fetchone()
    if not row:
        return json.dumps({"error": "Customer not found"})

    new_count = row["support_ticket_count"] + 1
    cur.execute(
        "UPDATE customers SET support_ticket_count = ? WHERE id = ?",
        (new_count, customer_id)
    )
    db.commit()

    customer = {
        "id":                   customer_id,
        "name":                 row["name"],
        "loyalty_tier":         row["loyalty_tier"],
        "birth_date":           row["birth_date"],
        "support_ticket_count": new_count
    }
    context = {"customer": customer}
    try:
        if (msg := apply_process_flow("support_request", context)):
            return json.dumps({"message": msg})
    except Exception as e:
        return json.dumps({"error": "process_flow_error", "detail": str(e)})

    return json.dumps({"support_ticket_count": new_count})

if __name__ == "__main__":
    mcp.run()
