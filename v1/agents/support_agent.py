import json
import requests
import asyncio
import httpx
from uuid import uuid4

from a2a.client import A2AClient
from a2a.types import (
    SendMessageRequest,
    MessageSendParams
)

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
        self.a2a_url   = a2a_url
        self.llm_url   = llm_url
        self.a2a_client: A2AClient | None = None
        self.httpx     = httpx.AsyncClient()
        self.context   = helper()

    async def init_a2a(self):
        if self.a2a_client is None:
            self.a2a_client = await A2AClient.get_client_from_agent_card_url(
                self.httpx, self.a2a_url
            )

    def ask_llama3(self, prompt: str) -> str:
        r = requests.post(self.llm_url, json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })
        r.raise_for_status()
        return r.json()["response"].strip()

    async def handle_query(self, user_text: str) -> str:
        await self.init_a2a()

        # Follow-up: “my orders”
        if "my orders" in user_text.lower():
            cid = self.context.get("customer_id")
            if not cid:
                return "I don’t know your customer ID yet—ask about a specific order first."
            payload = {
                "action": "get_customer_orders",
                "parameters": {"customer_id": cid}
            }
        else:
            # 1) Extract order ID
            prompt = (
            f"Extract the order ID from this message:\n\"{user_text}\"\n"
            "Reply only with the ID."
            )
            order_id = self.ask_llama3(prompt)
            if not order_id:
                return "Sorry, I couldn’t find an order ID."
            payload = {
                "action": "get_order_status",
                "parameters": {"order_id": order_id}
            }

        # 2) Build A2A request
        msg = SendMessageRequest(
            params=MessageSendParams(
                message={
                    "role": "user",
                    "parts": [{"type": "text", "text": json.dumps(payload)}],
                    "messageId": uuid4().hex
                }
            )
        )

        # 3) Send via A2AClient
        resp = await self.a2a_client.send_message(msg)
        text = resp.model_dump(mode="json", exclude_none=True)["result"]["parts"][0]["text"]

        # 4) Parse & update context
        if payload["action"] == "get_order_status":
            data = json.loads(text)
            self.context.set("customer_id", data.get("customer_id"))
            return f"Order {payload['parameters']['order_id']} is '{data.get('status')}'."
        else:
            return text

    async def close(self):
        await self.httpx.aclose()
