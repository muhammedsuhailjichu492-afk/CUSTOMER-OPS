import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import KB_DIR, RAG_TOP_K


class RAGAgent:
    name = "Knowledge RAG Agent"

    def __init__(self):
        self.chunks = []
        self.vectorizer = None
        self.matrix = None
        self.load()

    def load(self):
        self.chunks = []
        for path in sorted(KB_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = path.stem.replace("_", " ").title()
            sections = re.split(r"\n(?=## )", text)
            for sec in sections:
                sec = sec.strip()
                if len(sec) < 30:
                    continue
                heading = sec.splitlines()[0].lstrip("# ").strip()
                self.chunks.append({"source": path.name, "doc": title, "section": heading, "text": sec})
        if self.chunks:
            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
            self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])

    def run(self, query, intent=None, extra_terms=None):
        if not self.chunks:
            return []
        q = query
        if intent:
            q += " " + intent.replace("_", " ")
        if extra_terms:
            q += " " + " ".join(t for t in extra_terms if t)
        vec = self.vectorizer.transform([q])
        scores = cosine_similarity(vec, self.matrix)[0]
        idx = scores.argsort()[::-1][:RAG_TOP_K]
        results = []
        for i in idx:
            if scores[i] <= 0.02:
                continue
            c = self.chunks[i]
            results.append({
                "source": c["source"],
                "section": c["section"],
                "score": round(float(scores[i]), 3),
                "text": c["text"][:900],
            })
        return results
