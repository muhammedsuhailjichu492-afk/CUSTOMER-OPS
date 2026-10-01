import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "knowledge_base"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "customer_ops.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"

AUTO_APPROVE_REFUND_LIMIT = 5000.0
ESCALATION_CONFIDENCE_THRESHOLD = 0.45
RAG_TOP_K = 3
