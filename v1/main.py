import asyncio
from agents.support_agent import SupportAgent

async def main():
    agent = SupportAgent()
    try:
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
