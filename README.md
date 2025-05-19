# Customer-Support-Agent

# Multi-Agent Customer Support Demo

**Agents**  
- `db_tools_server.py`: MCP tool host (SQLite access)  
- `database_agent.py`: A2A façade bridging A2A → MCP tools  
- `support_agent.py`: Client using LLaMA-3 + A2AClient 


**Getting Started**

python -m venv .venv
source .venv/bin/activate   # or `.\venv\Scripts\activate` on Windows
pip install -r requirements.txt

# A2A
git clone https://github.com/google/a2a-python.git -b main --depth 1
cd a2a-python
pip install -e '.[dev]'

# MCP
pip install "mcp[cli]"

# Initialize the database
Get-Content db\setup.sql | sqlite3 db\real_agent_demo.db
or
sqlite3 db/real_agent_demo.db < setup.sql

# run A2A agent inside the venv
python -m agents.database_agent

# launch LLaMA 3 in a second terminal
ollama pull llama3       # (if you haven’t already)
ollama run llama3

# finally run the client
python main.py
