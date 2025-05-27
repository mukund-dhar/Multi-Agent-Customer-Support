import json
import uvicorn

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentAuthentication

# 1) Define A2A skills
skill_status = AgentSkill(
    id="get_order_status", name="Get Order Status",
    description="Returns status/customer_id for an order",
    tags=["order","status"],
    examples=['{"action":"get_order_status","parameters":{"order_id":"ORD001"}}']
)
skill_list = AgentSkill(
    id="get_customer_orders", name="Get Customer Orders",
    description="Lists all orders for a customer",
    tags=["order","list"],
    examples=['{"action":"get_customer_orders","parameters":{"customer_id":"C001"}}']
)
# New skills
skill_cancel = AgentSkill(
    id="cancel_service", name="Cancel Service",
    description="Cancels a customer subscription",
    tags=["subscription","cancel"],
    examples=['{"action":"cancel_service","parameters":{"subscription_id":"SUB001"}}']
)
skill_sub_status = AgentSkill(
    id="subscription_status", name="Subscription Status",
    description="Checks status of a subscription",
    tags=["subscription","status"],
    examples=['{"action":"subscription_status","parameters":{"subscription_id":"SUB001"}}']
)
skill_support = AgentSkill(
    id="support_request", name="Support Request",
    description="Logs a customer support request",
    tags=["support","ticket"],
    examples=['{"action":"support_request","parameters":{"customer_id":"C001"}}']
)

agent_card = AgentCard(
    name="DatabaseAgent", description="Bridges A2A→MCP tools",
    url="http://127.0.0.1:8000", version="1.0.0",
    defaultInputModes=["json"], defaultOutputModes=["json"],
    capabilities=AgentCapabilities(),
    skills=[skill_status, skill_list, skill_cancel, skill_sub_status, skill_support],
    authentication=AgentAuthentication(schemes=["public"])
)

class DatabaseAgentExecutor(AgentExecutor):
    def __init__(self):
        # how to launch the MCP server
        self.std_params = StdioServerParameters(
            command="python",
            args=["agents/db_tools_server.py"],
            env=None
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        raw = context.message.parts[0].root.text
        payload = json.loads(raw)
        action = payload.get("action")
        params = payload.get("parameters", {})

        if action in (
            "get_order_status",
            "get_customer_orders",
            "cancel_service",
            "subscription_status",
            "support_request"
        ):
            # call the MCP tool via stdio
            async with stdio_client(self.std_params) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    tool_resp = await session.call_tool(name=action, arguments=params)
                    result = tool_resp.content[0].text
        else:
            result = f"Unknown action: {action}"

        event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return

if __name__ == "__main__":
    handler = DefaultRequestHandler(
        agent_executor=DatabaseAgentExecutor(),
        task_store=InMemoryTaskStore()
    )
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler
    ).build()
    uvicorn.run(app, host="127.0.0.1", port=8000)
