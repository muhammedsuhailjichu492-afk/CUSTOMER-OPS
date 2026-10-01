import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

TRAINING_DATA = {
    "order_status": [
        "where is my order", "track my shipment", "order not delivered yet",
        "when will my order arrive", "delivery is delayed", "status of my order",
        "has my order shipped", "shipment tracking number please", "order still processing",
        "my package is late", "expected delivery date", "i have not received my order",
    ],
    "refund_request": [
        "i want a refund", "please refund my payment", "return this product and refund",
        "money back for my order", "cancel and refund", "refund for wrong item",
        "i was charged but want my money back", "request refund for damaged product",
        "process my refund", "want to return the item", "refund status", "return and get reimbursed",
    ],
    "technical_issue": [
        "plc not powering on", "servo motor making noise", "error code on the display",
        "sensor not detecting objects", "vfd tripping overcurrent", "hmi screen frozen",
        "device keeps restarting", "controller firmware issue", "machine stopped working",
        "gateway not connecting to network", "temperature controller showing wrong value",
        "motor overheating", "fault alarm on drive", "communication error modbus",
    ],
    "warranty_claim": [
        "is my product under warranty", "warranty replacement", "claim warranty for faulty unit",
        "product failed within warranty", "warranty repair request", "replace under warranty",
        "defective unit warranty", "warranty coverage question", "extend warranty",
    ],
    "billing_issue": [
        "charged twice", "wrong invoice amount", "billing error", "invoice not received",
        "gst details incorrect on invoice", "payment failed but money deducted",
        "overcharged for my order", "need corrected invoice", "discount not applied",
    ],
    "account_update": [
        "change my email address", "update phone number", "change shipping address",
        "update company details", "add a new user to account", "reset my password",
        "update billing address", "change contact person",
    ],
    "complaint": [
        "very disappointed with service", "worst support ever", "nobody responds to my emails",
        "i am going to cancel the contract", "this is unacceptable", "escalate to manager",
        "your technician was rude", "third time i am complaining", "legal action",
    ],
    "general_inquiry": [
        "what products do you sell", "business hours", "do you offer installation",
        "product catalog please", "price of plc", "bulk order discount", "training available",
        "compatible accessories", "datasheet for sensor",
    ],
}

NEGATIVE_WORDS = {
    "angry", "frustrated", "disappointed", "worst", "unacceptable", "terrible", "useless",
    "horrible", "furious", "rude", "never", "cancel", "legal", "lawyer", "again", "still",
    "waste", "pathetic", "delay", "delayed", "broken", "failed", "urgent",
}
URGENT_WORDS = {"urgent", "asap", "immediately", "production stopped", "line down", "shutdown", "critical", "emergency"}

ORDER_RE = re.compile(r"\bORD-?(\d{4,6})\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)
ERROR_RE = re.compile(r"\b(?:error|fault|code|alarm)\s*[:#]?\s*([A-Z]{0,3}-?\d{2,4})\b", re.IGNORECASE)


class IntentAgent:
    name = "Intent Detection Agent"

    def __init__(self):
        texts, labels = [], []
        for label, samples in TRAINING_DATA.items():
            texts.extend(samples)
            labels.extend([label] * len(samples))
        self.model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            LogisticRegression(max_iter=1000, C=5.0),
        )
        self.model.fit(texts, labels)

    def extract_entities(self, text):
        entities = {}
        m = ORDER_RE.search(text)
        if m:
            entities["order_number"] = f"ORD-{m.group(1)}"
        m = EMAIL_RE.search(text)
        if m:
            entities["email"] = m.group(0).lower()
        m = AMOUNT_RE.search(text)
        if m:
            entities["amount"] = float(m.group(1).replace(",", ""))
        m = ERROR_RE.search(text)
        if m:
            entities["error_code"] = m.group(1).upper()
        return entities

    def sentiment(self, text):
        words = set(re.findall(r"[a-z]+", text.lower()))
        score = len(words & NEGATIVE_WORDS) + text.count("!") * 0.5
        if score >= 2:
            return "Negative"
        if score >= 1:
            return "Slightly Negative"
        return "Neutral"

    def priority(self, text, intent, sentiment, tier):
        low = text.lower()
        if any(w in low for w in URGENT_WORDS):
            return "Critical"
        if intent == "complaint" or sentiment == "Negative":
            return "High"
        if tier == "Enterprise" and intent in ("technical_issue", "refund_request", "warranty_claim"):
            return "High"
        if intent in ("general_inquiry", "account_update"):
            return "Low"
        return "Medium"

    def run(self, text):
        probs = self.model.predict_proba([text])[0]
        classes = self.model.classes_
        ranked = sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)
        intent, confidence = ranked[0]
        return {
            "intent": intent,
            "confidence": round(float(confidence), 3),
            "alternatives": [{"intent": c, "score": round(float(p), 3)} for c, p in ranked[1:3]],
            "entities": self.extract_entities(text),
            "sentiment": self.sentiment(text),
        }
