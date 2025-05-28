import asyncio
from agents.support_agent import SupportAgent

async def main():
    agent = SupportAgent()
    try:
        print("SupportAgent: Hello! This is your AI customer support agent. I can talk in full sentences. Please mention your order ID or any relevant ID in your message and I will be happy to assist you.")
        while True:
            text = input("Customer: ")
            if text.lower() in ("quit", "exit"):
                break
            reply = await agent.handle_query(text)
            print("SupportAgent:", reply)
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
