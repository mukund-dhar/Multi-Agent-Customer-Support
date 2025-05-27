# support_agent.py

import json
import requests
import asyncio
import httpx
import re
from uuid import uuid4

from a2a.client import A2AClient
from a2a.client.errors import A2AClientHTTPError
from a2a.types import SendMessageRequest, MessageSendParams

class helper:
    """Simple in-process key/value store."""
    def __init__(self):
        self._store = {}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def set(self, key, value):
        self._store[key] = value

class SupportAgent:
    def __init__(
        self,
        a2a_url: str = "http://127.0.0.1:8000",
        llm_url: str = "http://localhost:11434/api/generate"
    ):
        # A2A endpoint URL
        self.a2a_url = a2a_url
        self.a2a_client: A2AClient | None = None

        # LLaMA-3 HTTP endpoint
        self.llm_url = llm_url

        # HTTP client for A2A with extended timeouts
        # timeout = httpx.Timeout(60.0, connect=10.0, read=60.0)
        self.httpx = httpx.AsyncClient()

        # in-memory context store
        self.context = helper()

    async def init_a2a(self):
        """Lazily initialize A2AClient from the agent card URL."""
        if self.a2a_client is None:
            self.a2a_client = await A2AClient.get_client_from_agent_card_url(
                self.httpx,
                self.a2a_url
            )

    def ask_llama3(self, prompt: str) -> str:
        """POST to your local Ollama HTTP server for LLaMA-3."""
        resp = requests.post(self.llm_url, json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    async def handle_query(self, user_text: str) -> str:
        # 1) Ensure A2A client is ready
        try:
            await self.init_a2a()
        except A2AClientHTTPError as e:
            return f"Failed to connect to DatabaseAgent: {e}"

        # 2) Use LLaMA-3 to parse intent + parameters
        parse_prompt = (
            "You are an intent parser for a customer support system. "
            "Given a customer message, extract the intent and any relevant IDs. "
            "Available intents: get_order_status, get_customer_orders, cancel_service, subscription_status, support_request. "
            "Parameters should be `order_id`, `customer_id`, or `subscription_id`"
            "Reply ONLY with a JSON object with keys 'action' and 'parameters'. Do NOT add anything else, just reply with the JSON."
            f"Message: \"{user_text}\""
        )
        parsed_text = self.ask_llama3(parse_prompt)
        try:
            parsed = json.loads(parsed_text)
            action = parsed.get("action")
            params = parsed.get("parameters", {}) or {}
        except json.JSONDecodeError:
            action = None
            params = {}

        allowed = {
            "get_order_status",
            "get_customer_orders",
            "cancel_service",
            "subscription_status",
            "support_request"
        }

        if not action or action not in allowed: 
            return f"Hello Customer! This is an AI agent. We could not parse your message: {user_text}. You can start by checking your order status in full sentences and providing us with your order ID."
        
        if action in {"get_customer_orders","support_request"}:
            cid = self.context.get("customer_id")
            if not cid:
                    return "I don’t know your customer ID yet—ask about a specific order first."
            params = {"customer_id": cid}

        # # 3) Fallback detection if parse fails or yields unknown action
        # allowed = {
        #     "get_order_status",
        #     "get_customer_orders",
        #     "cancel_service",
        #     "subscription_status",
        #     "support_request"
        # }
        # tl = user_text.lower()
        # if not action or action not in allowed:
        #     if "cancel" in tl and "sub" in tl:
        #         action = "cancel_service"
        #         m = re.search(r"\bSUB\d+\b", user_text.upper())
        #         if m:
        #             params = {"subscription_id": m.group(0)}
        #         else:
        #             return "Sorry, I couldn't find a subscription ID."
        #     elif any(w in tl for w in ("renew", "expire", "subscription status")):
        #         action = "subscription_status"
        #         m = re.search(r"\bSUB\d+\b", user_text.upper())
        #         if m:
        #             params = {"subscription_id": m.group(0)}
        #         else:
        #             return "Sorry, I couldn't find a subscription ID."
        #     elif any(w in tl for w in ("support", "help")):
        #         action = "support_request"
        #         cid = self.context.get("customer_id")
        #         if not cid:
        #             return "I don’t know your customer ID yet—ask about a specific order first."
        #         params = {"customer_id": cid}
        #     elif "order" in tl:
        #         action = "get_order_status"
        #         m = re.search(r"\bORD\d+\b", user_text.upper())
        #         if m:
        #             params = {"order_id": m.group(0)}
        #         else:
        #             return "Sorry, I couldn’t find an order ID."
        #     elif "my orders" in tl:
        #         action = "get_customer_orders"
        #         cid = self.context.get("customer_id")
        #         if not cid:
        #             return "I don’t know your customer ID yet—ask about a specific order first."
        #         params = {"customer_id": cid}
        #     else:
        #         return "Sorry, I didn’t understand that. Could you rephrase?"

        # 5) Build A2A message payload
        payload = {"action": action, "parameters": params}
        msg = SendMessageRequest(
            params=MessageSendParams(
                message={
                    "role": "user",
                    "parts": [{"type": "text", "text": json.dumps(payload)}],
                    "messageId": uuid4().hex
                }
            )
        )

        # 6) Send via A2AClient
        try:
            resp = await self.a2a_client.send_message(msg)
        except A2AClientHTTPError as e:
            return f"Error executing tool {action}: {e}"

        text = resp.model_dump(mode="json", exclude_none=True)["result"]["parts"][0]["text"]

        # 7) Parse and return
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text

        if data.get("message"):
            if data.get("customer_id"):
                self.context.set("customer_id", data.get("customer_id"))
            return data["message"]
        if action == "get_order_status":
            if data.get("customer_id"):
                self.context.set("customer_id", data.get("customer_id"))
            return f"Order {params.get('order_id')} is '{data.get('status')}'."
        if action == "get_customer_orders":
            orders = data.get("orders", [])
            if not orders:
                return "You have no orders."
            # Format each order with its status
            lines = [f"{o['id']}: {o['status']}" for o in orders]
            return "Your orders:\n" + "\n".join(lines)
        if action == "support_request":
            return f"Thank you for raising a support request. You have {data.get("support_ticket_count")} support requests with us. An agent will be with you shortly."
        return text

    async def close(self):
        await self.httpx.aclose()

# Standalone demo
if __name__ == "__main__":
    async def demo():
        agent = SupportAgent()
        for msg in [
            "What's the status of order ORD004?",
            "Cancel subscription SUB002",
            "I need support with my account",
        ]:
            resp = await agent.handle_query(msg)
            print("Customer:", msg)
            print("SupportAgent:", resp)
        await agent.close()

    asyncio.run(demo())
