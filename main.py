import json
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import llm
from app.agents.orchestrator import Orchestrator
from app.config import FRONTEND_DIR, OLLAMA_MODEL
from app.database import AgentLog, Customer, Order, Ticket, get_db
from app.seed import seed

seed()
orchestrator = Orchestrator()

app = FastAPI(title="AI Customer Operations & Resolution Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TicketIn(BaseModel):
    message: str
    email: Optional[str] = None
    order_number: Optional[str] = None


class ReviewIn(BaseModel):
    reviewer: str = "Support Lead"
    note: Optional[str] = None


class ReplyIn(BaseModel):
    reply_draft: str


def ticket_dict(t, full=False):
    d = {
        "id": t.id,
        "ticket_number": t.ticket_number,
        "customer": t.customer.name if t.customer else "Unknown",
        "company": t.customer.company if t.customer else None,
        "tier": t.customer.tier if t.customer else None,
        "order_number": t.order.order_number if t.order else None,
        "message": t.message,
        "intent": t.intent,
        "confidence": t.intent_confidence,
        "priority": t.priority,
        "sentiment": t.sentiment,
        "status": t.status,
        "proposed_action": t.proposed_action,
        "action_amount": t.action_amount,
        "escalated_to": t.escalated_to,
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M"),
    }
    if full:
        d.update({
            "findings": json.loads(t.findings or "[]"),
            "resolution_steps": json.loads(t.resolution or "[]"),
            "escalation_reason": t.escalation_reason,
            "reply_draft": t.reply_draft,
            "logs": [
                {"agent": l.agent, "step": l.step, "detail": l.detail, "at": l.created_at.strftime("%H:%M:%S")}
                for l in t.logs
            ],
        })
    return d


@app.get("/api/health")
def health():
    return {"status": "ok", "llm": llm.llm_available(), "model": OLLAMA_MODEL if llm.llm_available() else "template-fallback"}


@app.post("/api/tickets")
def create_ticket(body: TicketIn, db: Session = Depends(get_db)):
    if not body.message.strip():
        raise HTTPException(400, "Message is required")
    ticket, trace = orchestrator.process(db, body.message.strip(), body.email, body.order_number)
    return {"ticket": ticket_dict(ticket, full=True), "trace": trace}


@app.get("/api/tickets")
def list_tickets(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Ticket).order_by(Ticket.id.desc())
    if status:
        q = q.filter(Ticket.status == status)
    return [ticket_dict(t) for t in q.limit(200).all()]


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    return ticket_dict(t, full=True)


@app.post("/api/tickets/{ticket_id}/approve")
def approve_ticket(ticket_id: int, body: ReviewIn, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t.status not in ("Awaiting Approval", "Escalated"):
        raise HTTPException(400, f"Ticket is '{t.status}', nothing to approve")
    orchestrator.approve(db, t, body.reviewer, body.note)
    return ticket_dict(t, full=True)


@app.post("/api/tickets/{ticket_id}/reject")
def reject_ticket(ticket_id: int, body: ReviewIn, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    orchestrator.reject(db, t, body.reviewer, body.note)
    return ticket_dict(t, full=True)


@app.put("/api/tickets/{ticket_id}/reply")
def update_reply(ticket_id: int, body: ReplyIn, db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    t.reply_draft = body.reply_draft
    db.add(AgentLog(ticket_id=t.id, agent="Human Reviewer", step="Edited reply", detail="Reply draft updated"))
    db.commit()
    return ticket_dict(t, full=True)


@app.get("/api/customers")
def customers(db: Session = Depends(get_db)):
    rows = db.query(Customer).all()
    return [
        {"id": c.id, "name": c.name, "email": c.email, "company": c.company, "tier": c.tier,
         "orders": [{"order_number": o.order_number, "product": o.product.name, "status": o.status, "amount": o.amount} for o in c.orders]}
        for c in rows
    ]


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()
    by_status = dict(db.query(Ticket.status, func.count()).group_by(Ticket.status).all())
    by_intent = dict(db.query(Ticket.intent, func.count()).group_by(Ticket.intent).all())
    auto = by_status.get("Resolved", 0)
    return {
        "total": total,
        "resolved": auto,
        "awaiting_approval": by_status.get("Awaiting Approval", 0),
        "escalated": by_status.get("Escalated", 0),
        "resolution_rate": round(auto / total * 100, 1) if total else 0,
        "by_intent": by_intent,
        "customers": db.query(Customer).count(),
        "orders": db.query(Order).count(),
    }


@app.post("/api/kb/reload")
def reload_kb():
    orchestrator.rag_agent.load()
    return {"chunks": len(orchestrator.rag_agent.chunks)}


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
