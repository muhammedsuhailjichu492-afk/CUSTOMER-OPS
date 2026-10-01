# AI Customer Operations & Resolution Agent

A multi-agent customer service system for industrial product support. Unlike a basic chatbot, it reads customer records (CRM/SQL), searches a knowledge base (RAG), investigates the case, proposes a resolution, and either auto-resolves, sends it for human approval, or escalates to the right team.

## Agent Pipeline

```
Customer Message
      │
      ▼
1. Intent Detection Agent   → TF-IDF + Logistic Regression intent, entities (order no, email, error code), sentiment, priority
2. Customer Data Agent      → SQL lookup of customer, orders, ticket history, warranty status
3. Knowledge RAG Agent      → TF-IDF retrieval over policy & troubleshooting docs
4. Investigation Agent      → Policy checks (return window, warranty, SLA, error codes) → root cause + recommended action
5. Resolution Agent         → Resolution steps + reply draft (local Ollama LLM, template fallback)
6. Escalation Agent         → Low confidence / complaint / critical / high-value / repeat contact → routes to team
      │
      ▼
Resolved  |  Awaiting Approval (human-in-the-loop)  |  Escalated
```

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **NLP / ML:** scikit-learn (TF-IDF, Logistic Regression, cosine similarity)
- **LLM:** Ollama (local, free) with automatic template fallback
- **Frontend:** HTML, CSS, JavaScript dashboard

## Project Structure

```
customer-ops-agent/
├── app/
│   ├── agents/
│   │   ├── intent_agent.py
│   │   ├── customer_data_agent.py
│   │   ├── rag_agent.py
│   │   ├── investigation_agent.py
│   │   ├── resolution_agent.py
│   │   ├── escalation_agent.py
│   │   └── orchestrator.py
│   ├── config.py
│   ├── database.py
│   ├── llm.py
│   ├── main.py
│   └── seed.py
├── data/knowledge_base/*.md
├── frontend/ (index.html, style.css, app.js)
├── requirements.txt
└── run.py
```

## Setup (Windows / VS Code / PowerShell)

```powershell
cd customer-ops-agent
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**

The SQLite database (`data/customer_ops.db`) is created and seeded automatically on first run. Delete it to reset.

## Optional: Local LLM Replies

```powershell
ollama pull llama3.2
ollama serve
```

The badge in the top-right shows whether Ollama is connected. Without it, replies use templates. Change the model with `$env:OLLAMA_MODEL="mistral"` before `python run.py`, or disable with `$env:USE_LLM="false"`.

## Business Rules

| Rule | Value |
|---|---|
| Auto-approved refunds | ≤ ₹5,000 |
| Refunds needing approval | > ₹5,000 |
| Refunds escalated to Finance | > ₹50,000 |
| Return window | 30 days from delivery |
| Dispatch SLA | 7 days |
| Escalation confidence threshold | 0.45 |

Edit these in `app/config.py` and `app/agents/escalation_agent.py`.

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/tickets` | Run the agent pipeline on a message |
| GET | `/api/tickets` | List tickets (`?status=Escalated`) |
| GET | `/api/tickets/{id}` | Ticket detail with audit log |
| POST | `/api/tickets/{id}/approve` | Approve & execute action |
| POST | `/api/tickets/{id}/reject` | Reject & escalate |
| PUT | `/api/tickets/{id}/reply` | Edit reply draft |
| GET | `/api/customers` | CRM customers & orders |
| GET | `/api/stats` | Dashboard metrics |
| POST | `/api/kb/reload` | Reload knowledge base after editing docs |

Interactive docs: **http://127.0.0.1:8000/docs**

## Adding Knowledge

Drop any `.md` file into `data/knowledge_base/` using `## Section` headings, then call `POST /api/kb/reload` or restart.
