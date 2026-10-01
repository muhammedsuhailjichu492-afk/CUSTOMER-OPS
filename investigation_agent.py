from datetime import datetime


class InvestigationAgent:
    name = "Investigation Agent"

    def run(self, intent_result, customer_data, kb_hits):
        intent = intent_result["intent"]
        entities = intent_result["entities"]
        order = customer_data.get("order") if customer_data.get("found") else None
        findings = []
        checks = []
        root_cause = "Undetermined"
        recommended = "respond_with_information"
        confidence = intent_result["confidence"]

        if not customer_data.get("found"):
            findings.append("No matching customer record found in CRM for the given email/order number.")
            checks.append({"check": "CRM lookup", "passed": False})
            return {
                "findings": findings,
                "checks": checks,
                "root_cause": "Customer not identified",
                "recommended_action": "request_more_info",
                "confidence": min(confidence, 0.4),
            }

        checks.append({"check": "CRM lookup", "passed": True})
        cust = customer_data["customer"]
        findings.append(f"Customer identified: {cust['name']} ({cust['company']}), tier {cust['tier']}.")

        open_history = [t for t in customer_data["ticket_history"] if t["status"] not in ("Resolved", "Closed", "Rejected")]
        if len(customer_data["ticket_history"]) >= 2:
            findings.append(f"Customer has {len(customer_data['ticket_history'])} previous tickets ({len(open_history)} still open).")
            checks.append({"check": "Repeat contact", "passed": False})

        if order:
            findings.append(
                f"Order {order['order_number']}: {order['product']} x{order['quantity']}, "
                f"₹{order['amount']:,.2f}, status '{order['status']}', placed {order['days_since_order']} days ago."
            )
            if not customer_data.get("order_explicit"):
                findings.append("Order number not mentioned; matched the most relevant order from the customer's history.")

        if intent == "order_status":
            root_cause, recommended = self._order_status(order, findings, checks)
        elif intent == "refund_request":
            root_cause, recommended = self._refund(order, findings, checks)
        elif intent == "warranty_claim":
            root_cause, recommended = self._warranty(order, findings, checks)
        elif intent == "technical_issue":
            root_cause, recommended = self._technical(order, entities, kb_hits, findings, checks)
        elif intent == "billing_issue":
            root_cause, recommended = "Possible billing discrepancy", "billing_review"
            findings.append("Billing discrepancies require finance team verification against payment gateway records.")
            checks.append({"check": "Finance verification", "passed": False})
        elif intent == "account_update":
            root_cause, recommended = "Account change requested", "account_update"
            findings.append("Account changes require identity verification before being applied.")
        elif intent == "complaint":
            root_cause, recommended = "Customer dissatisfaction", "escalate"
            findings.append("Complaint detected; service recovery by a human manager is recommended.")
        else:
            root_cause, recommended = "Information request", "respond_with_information"

        if kb_hits:
            findings.append(f"Relevant policy found: {kb_hits[0]['source']} → '{kb_hits[0]['section']}'.")
            confidence = min(1.0, confidence + 0.1)
        else:
            findings.append("No strongly relevant knowledge base article found.")
            confidence = max(0.0, confidence - 0.1)

        return {
            "findings": findings,
            "checks": checks,
            "root_cause": root_cause,
            "recommended_action": recommended,
            "confidence": round(confidence, 3),
        }

    def _order_status(self, order, findings, checks):
        if not order:
            findings.append("No order found for this customer.")
            return "No order on record", "request_more_info"
        status = order["status"]
        if status == "Delivered":
            findings.append(f"Carrier shows delivered on {order['delivery_date']} (tracking {order['tracking_id']}).")
            checks.append({"check": "Delivery confirmed", "passed": True})
            return "Order already delivered", "share_delivery_proof"
        if status == "Shipped":
            findings.append(f"Order in transit, tracking {order['tracking_id']}.")
            checks.append({"check": "In transit", "passed": True})
            return "Order in transit", "share_tracking"
        if status == "Delayed" or (status == "Processing" and order["days_since_order"] > 7):
            findings.append("Order exceeds standard 7-day dispatch SLA.")
            checks.append({"check": "Dispatch SLA", "passed": False})
            return "Dispatch delay beyond SLA", "expedite_shipment"
        findings.append("Order is within normal processing time.")
        return "Order processing normally", "share_tracking"

    def _refund(self, order, findings, checks):
        if not order:
            return "No order to refund", "request_more_info"
        if order["status"] == "Refunded":
            findings.append("This order has already been refunded.")
            return "Duplicate refund request", "respond_with_information"
        if order["status"] in ("Processing", "Delayed"):
            findings.append("Order not yet shipped; eligible for cancellation with full refund.")
            checks.append({"check": "Refund eligibility", "passed": True})
            return "Cancellation before dispatch", "issue_refund"
        if order["delivery_date"]:
            days = (datetime.utcnow() - datetime.strptime(order["delivery_date"], "%Y-%m-%d")).days
            if days <= 30:
                findings.append(f"Delivered {days} days ago; within 30-day return window.")
                checks.append({"check": "30-day return window", "passed": True})
                return "Eligible return", "issue_refund"
            findings.append(f"Delivered {days} days ago; outside 30-day return window.")
            checks.append({"check": "30-day return window", "passed": False})
            if order["warranty_months_left"] and order["warranty_months_left"] > 0:
                findings.append("Product still under warranty; warranty replacement is an alternative.")
                return "Return window expired, warranty active", "offer_warranty_replacement"
            return "Return window expired", "decline_with_alternatives"
        findings.append("Order in transit; refund possible after return pickup.")
        return "In-transit refund", "issue_refund"

    def _warranty(self, order, findings, checks):
        if not order:
            return "No order found", "request_more_info"
        left = order["warranty_months_left"]
        if left is None:
            findings.append("Product not yet delivered; warranty not started.")
            return "Warranty not active", "respond_with_information"
        if left > 0:
            findings.append(f"Warranty active with {left} months remaining.")
            checks.append({"check": "Warranty active", "passed": True})
            return "Valid warranty claim", "offer_warranty_replacement"
        findings.append(f"Warranty expired {abs(left)} months ago.")
        checks.append({"check": "Warranty active", "passed": False})
        return "Warranty expired", "offer_paid_repair"

    def _technical(self, order, entities, kb_hits, findings, checks):
        code = entities.get("error_code")
        if code:
            findings.append(f"Error code {code} reported.")
            matched = any(code.lower() in h["text"].lower() for h in kb_hits)
            checks.append({"check": f"Error {code} in knowledge base", "passed": matched})
            if matched:
                return f"Known fault {code}", "send_troubleshooting"
        if kb_hits and kb_hits[0]["score"] > 0.12:
            return "Matches documented troubleshooting procedure", "send_troubleshooting"
        if order and order["warranty_months_left"] and order["warranty_months_left"] > 0:
            return "Unknown fault on in-warranty unit", "schedule_technician"
        return "Unknown technical fault", "schedule_technician"
