import random
from datetime import datetime, timedelta

from app.database import Customer, Order, Product, SessionLocal, init_db

CUSTOMERS = [
    ("Arjun Menon", "arjun@kochimachines.in", "Kochi Machines Pvt Ltd", "Enterprise", "+91 98470 11111"),
    ("Priya Nair", "priya@malabarfoods.in", "Malabar Foods", "Premium", "+91 98470 22222"),
    ("Rahul Verma", "rahul@deccanauto.com", "Deccan Auto Components", "Enterprise", "+91 98470 33333"),
    ("Sneha Iyer", "sneha@coastalpack.in", "Coastal Packaging", "Standard", "+91 98470 44444"),
    ("Fathima Rasheed", "fathima@spicetrail.in", "Spice Trail Exports", "Premium", "+91 98470 55555"),
    ("Vikram Singh", "vikram@northsteel.com", "North Steel Works", "Standard", "+91 98470 66666"),
    ("Anjali Das", "anjali@greentex.in", "GreenTex Textiles", "Standard", "+91 98470 77777"),
    ("Kiran Kumar", "kiran@bharatpumps.com", "Bharat Pumps", "Enterprise", "+91 98470 88888"),
]

PRODUCTS = [
    ("PLC-X200", "X200 Programmable Logic Controller", "Controllers", 48500.0, 24),
    ("SRV-750", "750W AC Servo Motor Kit", "Motion", 32000.0, 18),
    ("SEN-PX10", "PX10 Proximity Sensor (Pack of 10)", "Sensors", 6500.0, 12),
    ("HMI-7T", "7-inch Touch HMI Panel", "Displays", 21500.0, 12),
    ("VFD-5K", "5kW Variable Frequency Drive", "Drives", 38900.0, 24),
    ("CNV-M1", "Modular Conveyor Belt Segment", "Conveyors", 72000.0, 36),
    ("TMP-TC4", "TC4 Industrial Temperature Controller", "Controllers", 4200.0, 12),
    ("GWY-IOT", "Industrial IoT Gateway", "Networking", 18750.0, 12),
]

STATUSES = ["Delivered", "Delivered", "Delivered", "Shipped", "Processing", "Delayed", "Returned"]


def seed():
    init_db()
    db = SessionLocal()
    if db.query(Customer).count() > 0:
        db.close()
        return
    random.seed(42)
    customers = [Customer(name=n, email=e, company=c, tier=t, phone=p) for n, e, c, t, p in CUSTOMERS]
    products = [Product(sku=s, name=n, category=c, price=pr, warranty_months=w) for s, n, c, pr, w in PRODUCTS]
    db.add_all(customers + products)
    db.commit()

    order_no = 10001
    now = datetime.utcnow()
    for cust in customers:
        for _ in range(random.randint(2, 4)):
            prod = random.choice(products)
            qty = random.randint(1, 3)
            status = random.choice(STATUSES)
            order_date = now - timedelta(days=random.randint(3, 400))
            delivery = order_date + timedelta(days=random.randint(3, 10)) if status in ("Delivered", "Returned") else None
            db.add(Order(
                order_number=f"ORD-{order_no}",
                customer_id=cust.id,
                product_id=prod.id,
                quantity=qty,
                amount=round(prod.price * qty, 2),
                status=status,
                order_date=order_date,
                delivery_date=delivery,
                tracking_id=f"TRK{random.randint(100000, 999999)}" if status != "Processing" else None,
            ))
            order_no += 1
    db.commit()
    db.close()


if __name__ == "__main__":
    seed()
    print("Database seeded.")
