"""Retriever híbrido (BM25 + ChromaDB via RRF) para a base de conhecimento ErgoAI."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

COLECAO = "ergonomia"

_STOPWORDS_PT = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e",
    "em", "entre", "na", "nas", "no", "nos", "o", "os", "ou", "para", "pela",
    "pelas", "pelo", "pelos", "por", "qual", "quais", "quando", "que", "se",
    "sem", "ser", "sua", "suas", "um", "uma", "sobre", "devo", "posso",
}

_ANNEX_I_TERMS = ("telemarketing", "call center", "teleatendimento", "anexo i", "anexo 1")
_ANNEX_II_TERMS = ("checkout", "operador de caixa", "supermercado", "anexo ii", "anexo 2")


def normalize_text(text: str) -> str:
    """Normaliza acentuação, caixa e espaços para busca lexical."""
    lowered = text.lower().strip()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_accents)


def tokenize(text: str) -> list[str]:
    """Tokeniza texto removendo pontuação e stopwords em português."""
    norm = normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", norm)
    return [tok for tok in tokens if len(tok) > 1 and tok not in _STOPWORDS_PT]


@dataclass(frozen=True)
class RetrievedChunk:
    """Chunk recuperado com metadados rastreáveis."""

    chunk_id: str
    document_id: str
    source: str
    section: str | None
    page: int | None
    text: str
    score: float


def _is_annex_allowed(section: str | None, normalized_query: str) -> bool:
    """Evita vazamento de anexos específicos da NR-17 em consultas gerais de escritório."""
    if not section:
        return True
    sec_norm = normalize_text(section)
    if "anexo i" in sec_norm and "anexo ii" not in sec_norm:
        return any(term in normalized_query for term in _ANNEX_I_TERMS)
    if "anexo ii" in sec_norm:
        return any(term in normalized_query for term in _ANNEX_II_TERMS)
    return True


class HybridRetriever:
    """Busca híbrida combinando BM25 (corpus JSONL) e ChromaDB vetorial quando disponível."""

    def __init__(
        self,
        chroma_persist_dir: str | Path,
        corpus_chunks_path: str | Path,
        kb_manifest_path: str | Path | None = None,
    ) -> None:
        self.chroma_persist_dir = Path(chroma_persist_dir)
        self.corpus_chunks_path = Path(corpus_chunks_path)
        self.kb_manifest_path = Path(kb_manifest_path) if kb_manifest_path else None

        self._corpus_records: list[dict[str, Any]] = []
        self._corpus_tokens: list[list[str]] = []
        self._bm25: BM25Okapi | None = None
        self._load_corpus()

    def _load_corpus(self) -> None:
        if not self.corpus_chunks_path.exists():
            return
        records: list[dict[str, Any]] = []
        for line in self.corpus_chunks_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not records:
            return
        self._corpus_records = records
        self._corpus_tokens = [tokenize(str(r.get("text", ""))) for r in records]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def _get_chroma_collection(self):
        if not self.chroma_persist_dir.exists():
            return None
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.chroma_persist_dir))
            return client.get_collection(COLECAO)
        except Exception:  # noqa: BLE001 - ChromaDB é opcional quando apenas BM25 está ativo
            return None

    def _encode_for_chroma(self, query: str) -> list[list[float]] | None:
        if not self.kb_manifest_path or not self.kb_manifest_path.exists():
            return None
        try:
            manifest = json.loads(self.kb_manifest_path.read_text(encoding="utf-8"))
            embedder_name = manifest.get("parametros", {}).get("embedder", "")
            if not embedder_name:
                return None
            from knowledge_base.embed import get_embedder

            return get_embedder(embedder_name).encode([query])
        except Exception as exc:  # noqa: BLE001 - embedder pode não estar instalado sem --extra rag
            logger.debug("Embedder indisponível para busca vetorial (%s); usando BM25.", exc)
            return None

    def status(self) -> dict[str, Any]:
        """Retorna estado atual dos índices (ChromaDB e corpus BM25)."""
        col = self._get_chroma_collection()
        chroma_count = 0
        if col is not None:
            try:
                chroma_count = int(col.count())
            except Exception:  # noqa: BLE001
                chroma_count = 0

        corpus_count = len(self._corpus_records)
        if chroma_count > 0:
            mode = "hybrid_chroma_bm25"
            status_val = "indexed"
            detail = f"Índice vetorial ChromaDB ativo ({chroma_count} chunks) com busca híbrida BM25."
        elif corpus_count > 0:
            mode = "bm25_corpus"
            status_val = "not_indexed"
            detail = (
                f"ChromaDB não indexado; corpus versionado disponível ({corpus_count} chunks) "
                "em modo de busca lexical BM25."
            )
        else:
            mode = "unavailable"
            status_val = "not_indexed"
            detail = "Base de conhecimento ainda não indexada."

        return {
            "status": status_val,
            "detail": detail,
            "chroma_chunks": chroma_count,
            "corpus_chunks": corpus_count,
            "retrieval_mode": mode,
        }

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        """Recupera até `top_k` chunks relevantes usando BM25 + ChromaDB (RRF)."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        norm_query = normalize_text(query)
        rrf_scores: dict[str, float] = {}
        chunk_by_id: dict[str, dict[str, Any]] = {}

        # 1. Busca lexical BM25 no corpus
        if self._bm25 is not None and self._corpus_records:
            bm25_scores = self._bm25.get_scores(query_tokens)
            ranked_indices = sorted(
                range(len(bm25_scores)),
                key=lambda idx: bm25_scores[idx],
                reverse=True,
            )
            rank = 1
            for idx in ranked_indices:
                score = float(bm25_scores[idx])
                if score <= 0.0:
                    break
                rec = self._corpus_records[idx]
                meta = rec.get("metadata", {})
                if not _is_annex_allowed(meta.get("section"), norm_query):
                    continue
                cid = str(rec.get("id", f"bm25-{idx}"))
                chunk_by_id[cid] = rec
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (60.0 + rank)
                rank += 1
                if rank > max(top_k * 4, 15):
                    break

        # 2. Busca vetorial no ChromaDB (quando indexado e com embedder compatível)
        col = self._get_chroma_collection()
        if col is not None:
            emb = self._encode_for_chroma(query)
            if emb is not None:
                try:
                    res = col.query(query_embeddings=emb, n_results=max(top_k * 4, 12))
                    ids = res.get("ids", [[]])[0]
                    docs = res.get("documents", [[]])[0]
                    metas = res.get("metadatas", [[]])[0]
                    rank = 1
                    for cid, doc, meta in zip(ids, docs, metas):
                        if not _is_annex_allowed(meta.get("section"), norm_query):
                            continue
                        cid_str = str(cid)
                        if cid_str not in chunk_by_id:
                            chunk_by_id[cid_str] = {
                                "id": cid_str,
                                "text": doc,
                                "metadata": meta,
                            }
                        rrf_scores[cid_str] = rrf_scores.get(cid_str, 0.0) + 1.0 / (60.0 + rank)
                        rank += 1
                except Exception as exc:  # noqa: BLE001 - fallback seguro para BM25
                    logger.warning("Falha na consulta ao ChromaDB (%s); mantendo BM25.", exc)

        if not rrf_scores:
            return []

        ordered_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
        results: list[RetrievedChunk] = []
        for cid in ordered_ids:
            rec = chunk_by_id[cid]
            meta = rec.get("metadata", {})
            raw_page = meta.get("page")
            page = int(raw_page) if isinstance(raw_page, (int, float)) else None
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    document_id=str(meta.get("document_id", "desconhecido")),
                    source=str(meta.get("source", meta.get("title", "Fonte oficial"))),
                    section=meta.get("section"),
                    page=page,
                    text=str(rec.get("text", "")),
                    score=round(rrf_scores[cid], 6),
                )
            )
        return results
