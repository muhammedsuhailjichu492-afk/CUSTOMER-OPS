from app import llm
from app.config import AUTO_APPROVE_REFUND_LIMIT

ACTION_LABELS = {
    "share_tracking": "Share tracking details",
    "share_delivery_proof": "Share proof of delivery",
    "expedite_shipment": "Expedite shipment",
    "issue_refund": "Issue refund",
    "offer_warranty_replacement": "Warranty replacement",
    "offer_paid_repair": "Offer paid repair",
    "decline_with_alternatives": "Decline refund, offer alternatives",
    "send_troubleshooting": "Send troubleshooting steps",
    "schedule_technician": "Schedule field technician",
    "billing_review": "Billing review by finance",
    "account_update": "Update account details",
    "respond_with_information": "Respond with information",
    "request_more_info": "Request more information",
    "escalate": "Escalate to human",
}

REQUIRES_APPROVAL = {"issue_refund", "offer_warranty_replacement", "expedite_shipment", "schedule_technician", "account_update"}


class ResolutionAgent:
    name = "Resolution Agent"

    def run(self, message, intent_result, customer_data, investigation, kb_hits):
        action = investigation["recommended_action"]
        order = customer_data.get("order") if customer_data.get("found") else None
        amount = 0.0
        if action == "issue_refund" and order:
            amount = order["amount"]

        needs_approval = action in REQUIRES_APPROVAL
        auto_ok = action == "issue_refund" and amount <= AUTO_APPROVE_REFUND_LIMIT
        if auto_ok:
            needs_approval = False

        steps = self._steps(action, order, kb_hits)
        reply = self._reply(message, intent_result, customer_data, investigation, kb_hits, action, steps)

        return {
            "action": action,
            "action_label": ACTION_LABELS.get(action, action),
            "amount": amount,
            "requires_approval": needs_approval,
            "steps": steps,
            "reply_draft": reply,
            "generated_by": "llm" if reply.get("llm") else "template",
        }

    def _steps(self, action, order, kb_hits):
        on = order["order_number"] if order else "the order"
        if action == "issue_refund":
            return [f"Validate return eligibility for {on}", f"Initiate refund of ₹{order['amount']:,.2f}" if order else "Initiate refund",
                    "Update order status to Refunded", "Notify customer with refund reference"]
        if action == "offer_warranty_replacement":
            return ["Create RMA number", "Arrange reverse pickup of faulty unit", "Dispatch replacement unit", "Close ticket after delivery"]
        if action == "expedite_shipment":
            return [f"Flag {on} for priority dispatch", "Upgrade shipping to express at no cost", "Send new ETA to customer"]
        if action == "send_troubleshooting":
            src = kb_hits[0]["section"] if kb_hits else "troubleshooting guide"
            return [f"Send steps from '{src}'", "Ask customer to confirm outcome within 48 hours", "Auto-escalate to field service if unresolved"]
        if action == "schedule_technician":
            return ["Collect site address and availability", "Assign nearest field engineer", "Confirm visit slot with customer"]
        if action == "share_tracking":
            return [f"Share tracking ID {order['tracking_id']}" if order and order["tracking_id"] else "Share dispatch timeline"]
        if action == "share_delivery_proof":
            return ["Share proof of delivery and receiver details", "Offer investigation if item not found on site"]
        if action == "billing_review":
            return ["Forward invoice and payment details to finance", "Issue corrected invoice or reversal"]
        if action == "account_update":
            return ["Verify identity via registered phone OTP", "Apply requested account change", "Send confirmation email"]
        if action == "request_more_info":
            return ["Ask customer for order number and registered email"]
        if action == "offer_paid_repair":
            return ["Share paid repair quote", "Offer extended AMC plan"]
        if action == "decline_with_alternatives":
            return ["Explain return policy", "Offer paid repair or trade-in"]
        return ["Answer customer query using knowledge base"]

    def _reply(self, message, intent_result, customer_data, investigation, kb_hits, action, steps):
        name = customer_data["customer"]["name"].split()[0] if customer_data.get("found") else "there"
        context = "\n\n".join(f"[{h['source']} - {h['section']}]\n{h['text']}" for h in kb_hits)
        prompt = (
            f"Customer message:\n{message}\n\n"
            f"Detected intent: {intent_result['intent']}\n"
            f"Investigation findings:\n- " + "\n- ".join(investigation["findings"]) + "\n\n"
            f"Chosen action: {ACTION_LABELS.get(action, action)}\n"
            f"Planned steps:\n- " + "\n- ".join(steps) + "\n\n"
            f"Company knowledge base excerpts:\n{context or 'None'}\n\n"
            f"Write a concise, professional reply email body to {name}. Use only facts above. "
            "Do not promise anything beyond the planned steps. If approval is pending, say the team is processing it. "
            "Sign off as 'EVOLVE Customer Operations'. Max 150 words."
        )
        text = llm.generate(prompt)
        if text:
            return {"text": text, "llm": True}
        return {"text": self._template(name, action, customer_data, investigation, kb_hits, steps), "llm": False}

    def _template(self, name, action, customer_data, investigation, kb_hits, steps):
        order = customer_data.get("order") if customer_data.get("found") else None
        on = order["order_number"] if order else "your order"
        lines = [f"Hi {name},", "", "Thank you for reaching out to us."]
        if action == "share_tracking" and order:
            lines.append(f"Your order {on} is currently '{order['status']}'."
                         + (f" You can track it using ID {order['tracking_id']}." if order["tracking_id"] else ""))
        elif action == "share_delivery_proof" and order:
            lines.append(f"Our records show {on} was delivered on {order['delivery_date']}. "
                         "If it has not reached your team, please let us know and we will investigate with the carrier.")
        elif action == "expedite_shipment":
            lines.append(f"We are sorry that {on} is delayed. We have flagged it for priority dispatch with express shipping at no extra cost.")
        elif action == "issue_refund" and order:
            lines.append(f"Your refund request for {on} (₹{order['amount']:,.2f}) is eligible and is being processed. "
                         "You will receive a refund reference shortly.")
        elif action == "offer_warranty_replacement":
            lines.append(f"Your product from {on} is under warranty. We will raise an RMA and arrange a replacement.")
        elif action == "send_troubleshooting" and kb_hits:
            lines.append("Please try the following steps from our support guide:")
            body = [l for l in kb_hits[0]["text"].splitlines()[1:] if l.strip()][:6]
            lines.extend(body)
            lines.append("If the issue persists, reply to this email and we will schedule a field engineer.")
        elif action == "schedule_technician":
            lines.append("We will arrange a field engineer visit. Please share your site address and a convenient time slot.")
        elif action == "billing_review":
            lines.append("We have forwarded your billing concern to our finance team, who will verify and correct it within 2 business days.")
        elif action == "account_update":
            lines.append("To protect your account, we will verify your identity via your registered phone before applying the change.")
        elif action == "request_more_info":
            lines.append("To help you faster, please share your order number (e.g. ORD-10001) and the email registered with us.")
        elif action == "offer_paid_repair":
            lines.append("Your product's warranty has expired, but we can offer a paid repair or an extended maintenance plan.")
        elif action == "decline_with_alternatives":
            lines.append("Unfortunately this order is outside our 30-day return window. We can offer a paid repair or trade-in option.")
        else:
            if kb_hits:
                lines.append([l for l in kb_hits[0]["text"].splitlines()[1:] if l.strip()][0])
            else:
                lines.append("Our team will review your query and get back to you shortly.")
        lines += ["", "Regards,", "EVOLVE Customer Operations"]
        return "\n".join(lines)
