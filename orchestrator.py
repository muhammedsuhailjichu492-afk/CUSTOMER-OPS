import json
import uuid

from app.agents.customer_data_agent import CustomerDataAgent
from app.agents.escalation_agent import EscalationAgent
from app.agents.intent_agent import IntentAgent
from app.agents.investigation_agent import InvestigationAgent
from app.agents.rag_agent import RAGAgent
from app.agents.resolution_agent import ResolutionAgent
from app.database import AgentLog, Order, Ticket


class Orchestrator:
    def __init__(self):
        self.intent_agent = IntentAgent()
        self.data_agent = CustomerDataAgent()
        self.rag_agent = RAGAgent()
        self.investigation_agent = InvestigationAgent()
        self.resolution_agent = ResolutionAgent()
        self.escalation_agent = EscalationAgent()

    def log(self, db, ticket, agent, step, detail):
        if not isinstance(detail, str):
            detail = json.dumps(detail, default=str, ensure_ascii=False)
        db.add(AgentLog(ticket_id=ticket.id, agent=agent, step=step, detail=detail))

    def process(self, db, message, email=None, order_number=None):
        ticket = Ticket(ticket_number=f"TCK-{uuid.uuid4().hex[:8].upper()}", message=message, status="Investigating")
        db.add(ticket)
        db.flush()
        trace = []

        intent = self.intent_agent.run(message)
        entities = intent["entities"]
        email = email or entities.get("email")
        order_number = order_number or entities.get("order_number")
        self.log(db, ticket, IntentAgent.name, "Classified intent", intent)
        trace.append({"agent": IntentAgent.name, "output": intent})

        data = self.data_agent.run(db, email=email, order_number=order_number, message=message)
        order_obj = data.pop("_order_obj", None)
        cust_obj = data.pop("_customer_obj", None)
        self.log(db, ticket, CustomerDataAgent.name, "Fetched CRM records",
                 {"found": data["found"], "customer": data["customer"], "order": data["order"]})
        trace.append({"agent": CustomerDataAgent.name, "output": data})

        tier = data["customer"]["tier"] if data["found"] else "Standard"
        priority = self.intent_agent.priority(message, intent["intent"], intent["sentiment"], tier)

        extra = [data["order"]["product"] if data.get("order") else None, entities.get("error_code")]
        kb = self.rag_agent.run(message, intent["intent"], extra)
        self.log(db, ticket, RAGAgent.name, "Retrieved knowledge", [{"source": k["source"], "section": k["section"], "score": k["score"]} for k in kb])
        trace.append({"agent": RAGAgent.name, "output": kb})

        inv = self.investigation_agent.run(intent, data, kb)
        self.log(db, ticket, InvestigationAgent.name, "Investigated case", inv)
        trace.append({"agent": InvestigationAgent.name, "output": inv})

        res = self.resolution_agent.run(message, intent, data, inv, kb)
        self.log(db, ticket, ResolutionAgent.name, "Proposed resolution",
                 {k: v for k, v in res.items() if k != "reply_draft"})
        trace.append({"agent": ResolutionAgent.name, "output": res})

        esc = self.escalation_agent.run(intent, data, inv, res, priority)
        self.log(db, ticket, EscalationAgent.name, "Escalation decision", esc)
        trace.append({"agent": EscalationAgent.name, "output": esc})

        ticket.customer_id = cust_obj.id if cust_obj else None
        ticket.order_id = order_obj.id if order_obj else None
        ticket.intent = intent["intent"]
        ticket.intent_confidence = intent["confidence"]
        ticket.sentiment = intent["sentiment"]
        ticket.priority = priority
        ticket.findings = json.dumps(inv["findings"], ensure_ascii=False)
        ticket.resolution = json.dumps(res["steps"], ensure_ascii=False)
        ticket.proposed_action = res["action"]
        ticket.action_amount = res["amount"]
        ticket.reply_draft = res["reply_draft"]["text"]

        if esc["escalate"]:
            ticket.status = "Escalated"
            ticket.escalated_to = esc["team"]
            ticket.escalation_reason = "; ".join(esc["reasons"])
        elif res["requires_approval"]:
            ticket.status = "Awaiting Approval"
        else:
            self.execute(db, ticket, order_obj)
            ticket.status = "Resolved"
            self.log(db, ticket, "Workflow Engine", "Auto-resolved", f"Action '{res['action_label']}' executed within auto-approval policy.")

        db.commit()
        db.refresh(ticket)
        return ticket, trace

    def execute(self, db, ticket, order=None):
        order = order or (db.get(Order, ticket.order_id) if ticket.order_id else None)
        if not order:
            return
        if ticket.proposed_action == "issue_refund":
            order.status = "Refunded"
        elif ticket.proposed_action == "expedite_shipment":
            order.status = "Shipped"
        elif ticket.proposed_action == "offer_warranty_replacement":
            order.status = "Replacement Dispatched"

    def approve(self, db, ticket, reviewer, note=None):
        self.execute(db, ticket)
        ticket.status = "Resolved"
        self.log(db, ticket, "Human Reviewer", "Approved", f"{reviewer}: {note or 'Approved'}")
        db.commit()
        return ticket

    def reject(self, db, ticket, reviewer, note=None):
        ticket.status = "Escalated"
        ticket.escalated_to = ticket.escalated_to or "Tier-2 Support"
        ticket.escalation_reason = f"Rejected by {reviewer}: {note or 'No reason given'}"
        self.log(db, ticket, "Human Reviewer", "Rejected", ticket.escalation_reason)
        db.commit()
        return ticket
