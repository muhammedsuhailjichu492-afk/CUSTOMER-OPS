from datetime import datetime

from sqlalchemy import func

from app.database import Customer, Order, Ticket


class CustomerDataAgent:
    name = "Customer Data Agent"

    def match_order_by_text(self, orders, text):
        if not text:
            return None
        words = set(w.strip(".,!?").lower() for w in text.split())
        best, best_score = None, 0
        for o in orders:
            if not o.product:
                continue
            tokens = set(o.product.name.lower().replace("-", " ").split()) | {o.product.sku.lower(), o.product.category.lower()}
            tokens = {t for t in tokens if len(t) > 2}
            score = len(tokens & words) + sum(1 for t in tokens for w in words if len(w) > 3 and w in t)
            if score > best_score:
                best, best_score = o, score
        return best

    def run(self, db, email=None, order_number=None, message=None):
        customer = None
        order = None

        if order_number:
            order = db.query(Order).filter(func.upper(Order.order_number) == order_number.upper()).first()
            if order:
                customer = order.customer

        if customer is None and email:
            customer = db.query(Customer).filter(func.lower(Customer.email) == email.lower()).first()

        if customer is None:
            return {"found": False, "customer": None, "order": None, "orders": [], "ticket_history": []}

        orders = db.query(Order).filter(Order.customer_id == customer.id).order_by(Order.order_date.desc()).all()

        if order is None:
            order = self.match_order_by_text(orders, message) or (orders[0] if orders else None)
        past_tickets = (
            db.query(Ticket)
            .filter(Ticket.customer_id == customer.id)
            .order_by(Ticket.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "found": True,
            "customer": self._customer(customer),
            "order": self._order(order) if order else None,
            "order_explicit": bool(order_number),
            "orders": [self._order(o) for o in orders],
            "ticket_history": [
                {
                    "ticket_number": t.ticket_number,
                    "intent": t.intent,
                    "status": t.status,
                    "created_at": t.created_at.strftime("%Y-%m-%d"),
                }
                for t in past_tickets
            ],
            "lifetime_value": round(sum(o.amount for o in orders), 2),
            "_order_obj": order,
            "_customer_obj": customer,
        }

    def _customer(self, c):
        return {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "company": c.company,
            "tier": c.tier,
            "phone": c.phone,
        }

    def _order(self, o):
        days_since = (datetime.utcnow() - o.order_date).days
        warranty_left = None
        if o.product and o.delivery_date:
            used = (datetime.utcnow() - o.delivery_date).days / 30.0
            warranty_left = round(o.product.warranty_months - used, 1)
        return {
            "id": o.id,
            "order_number": o.order_number,
            "product": o.product.name if o.product else None,
            "sku": o.product.sku if o.product else None,
            "quantity": o.quantity,
            "amount": o.amount,
            "status": o.status,
            "order_date": o.order_date.strftime("%Y-%m-%d"),
            "delivery_date": o.delivery_date.strftime("%Y-%m-%d") if o.delivery_date else None,
            "tracking_id": o.tracking_id,
            "days_since_order": days_since,
            "warranty_months_left": warranty_left,
        }
