"""Embedders. O mesmo embedder deve ser usado na indexação e na consulta (ver manifest.json)."""
import hashlib
import math

# PROVISÓRIO: confirmar o nome do modelo na documentação do sentence-transformers / Hugging Face.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class HashEmbedder:
    """Determinístico, sem download. SÓ para testes e CI do pipeline; não serve para avaliar a recuperação."""
    name = "hash"

    def __init__(self, dim=64):
        self.dim = dim

    def encode(self, texts):
        saida = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in t.lower().split():
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            saida.append([x / n for x in v])
        return saida


class SentenceTransformerEmbedder:
    def __init__(self, model_name):
        from sentence_transformers import SentenceTransformer
        self.name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()


def get_embedder(name):
    return HashEmbedder() if name == "hash" else SentenceTransformerEmbedder(name)
