from app.config import AUTO_APPROVE_REFUND_LIMIT, ESCALATION_CONFIDENCE_THRESHOLD

TEAMS = {
    "technical_issue": "Field Service Engineering",
    "warranty_claim": "Warranty & RMA Desk",
    "refund_request": "Finance & Refunds",
    "billing_issue": "Finance & Refunds",
    "complaint": "Customer Success Manager",
    "order_status": "Logistics Team",
    "account_update": "Account Management",
    "general_inquiry": "Tier-2 Support",
}


class EscalationAgent:
    name = "Escalation Agent"

    def run(self, intent_result, customer_data, investigation, resolution, priority):
        reasons = []
        intent = intent_result["intent"]

        if investigation["confidence"] < ESCALATION_CONFIDENCE_THRESHOLD:
            reasons.append(f"Low confidence ({investigation['confidence']:.2f})")
        if intent == "complaint":
            reasons.append("Formal complaint")
        if priority == "Critical":
            reasons.append("Critical priority (production impact)")
        if intent_result["sentiment"] == "Negative" and customer_data.get("found") and customer_data["customer"]["tier"] == "Enterprise":
            reasons.append("Negative sentiment from Enterprise customer")
        if len(customer_data.get("ticket_history", [])) >= 3:
            reasons.append("Repeat contact (3+ previous tickets)")
        if resolution["action"] == "issue_refund" and resolution["amount"] > AUTO_APPROVE_REFUND_LIMIT * 10:
            reasons.append(f"High-value refund ₹{resolution['amount']:,.2f}")
        if resolution["action"] in ("billing_review", "escalate"):
            reasons.append("Requires specialist team")

        escalate = len(reasons) > 0
        return {
            "escalate": escalate,
            "team": TEAMS.get(intent, "Tier-2 Support") if escalate else None,
            "reasons": reasons,
        }
