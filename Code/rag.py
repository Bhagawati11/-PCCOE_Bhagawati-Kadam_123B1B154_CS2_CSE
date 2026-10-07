import re, csv
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import config

_model = None


def embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model


class VectorIndex:
    def __init__(self, items):
        self.items = items
        vecs = embedder().encode([i["text"] for i in items], normalize_embeddings=True).astype("float32")
        self.index = faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs)

    def search(self, query, k=config.TOP_K):
        v = embedder().encode([query], normalize_embeddings=True).astype("float32")
        scores, ids = self.index.search(v, min(k, len(self.items)))
        return [dict(self.items[i], score=float(s)) for s, i in zip(scores[0], ids[0]) if i >= 0]


def load_blocks(path, tag):
    """Blocks separated by blank lines, each starting with 'ITEM <ID>' or 'RULE <ID>'."""
    txt = open(path, encoding="utf-8").read()
    items = []
    for block in re.split(r"\n\s*\n", txt):
        m = re.match(rf"\s*{tag}\s+([A-Z]+-\d+)", block)
        if m:
            items.append({"id": m.group(1), "text": block.strip(), "file": path.split("/")[-1]})
    return items


def load_library(path):
    items = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            text = (f"[{r['id']}] Function: {r['function']}. Malfunction: {r['malfunction']}. "
                    f"Hazard: {r['hazard']}. Situation: {r['scenario']}. "
                    f"Rating S{r['S']} E{r['E']} C{r['C']} = ASIL {r['asil']}. Rationale: {r['rationale']}.")
            items.append({"id": r["id"], "text": text, "file": "hara_library.csv", "function": r["function"],
                          "malfunction": r["malfunction"], "hazard": r["hazard"], "scenario": r["scenario"],
                          "S": int(r["S"]), "E": int(r["E"]), "C": int(r["C"]), "asil": r["asil"]})
    return items
