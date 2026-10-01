from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import DATA_DIR, DATABASE_URL

DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    company = Column(String(120))
    tier = Column(String(20), default="Standard")
    phone = Column(String(30))
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="customer")
    tickets = relationship("Ticket", back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(40), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    category = Column(String(60))
    price = Column(Float, nullable=False)
    warranty_months = Column(Integer, default=12)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(String(30), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    amount = Column(Float, nullable=False)
    status = Column(String(30), default="Processing")
    order_date = Column(DateTime, default=datetime.utcnow)
    delivery_date = Column(DateTime, nullable=True)
    tracking_id = Column(String(40))
    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product")


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    ticket_number = Column(String(30), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    message = Column(Text, nullable=False)
    intent = Column(String(40))
    intent_confidence = Column(Float)
    priority = Column(String(20), default="Medium")
    sentiment = Column(String(20))
    status = Column(String(30), default="Open")
    findings = Column(Text)
    resolution = Column(Text)
    proposed_action = Column(String(60))
    action_amount = Column(Float, default=0.0)
    escalated_to = Column(String(60))
    escalation_reason = Column(Text)
    reply_draft = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer = relationship("Customer", back_populates="tickets")
    order = relationship("Order")
    logs = relationship("AgentLog", back_populates="ticket", order_by="AgentLog.id")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    agent = Column(String(40))
    step = Column(String(80))
    detail = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="logs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
