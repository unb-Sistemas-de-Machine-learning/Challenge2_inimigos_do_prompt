"""Testes unitários e de integração do pipeline RAG (Issue #7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.llm.client import GeminiClient
from app.rag.pipeline import RagPipeline
from app.rag.retriever import HybridRetriever
from app.schemas.contracts import PostureClassification, PostureEvent, PostureFeatures

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = REPO_ROOT / "knowledge_base" / "corpus" / "chunks.jsonl"


def _load_corpus_texts() -> list[str]:
    return [
        json.loads(line)["text"]
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _make_retriever() -> HybridRetriever:
    return HybridRetriever(
        chroma_persist_dir=REPO_ROOT / "backend" / "data" / "nao_existe",
        corpus_chunks_path=CORPUS_PATH,
    )


def test_rag_answer_question_retorna_citacoes_literais() -> None:
    pipeline = RagPipeline(retriever=_make_retriever())
    resp = pipeline.answer_question("Como deve ser o posicionamento do monitor e mobiliário na NR-17?", top_k=3)
    assert resp.grounded is True
    assert resp.mode == "rag_extractive"
    assert len(resp.evidence) >= 1

    corpus_texts = _load_corpus_texts()
    for ev in resp.evidence:
        assert ev.exact_quote
        assert any(ev.exact_quote in full_text for full_text in corpus_texts)


def test_rag_nao_vaza_anexos_em_consulta_geral() -> None:
    pipeline = RagPipeline(retriever=_make_retriever())
    resp = pipeline.answer_question("Quais pausas e cuidados para trabalho em escritório?", top_k=5)
    for ev in resp.evidence:
        sec = (ev.section or "").lower()
        assert "anexo i" not in sec
        assert "anexo ii" not in sec


def test_rag_recusa_quando_nao_ha_evidencia() -> None:
    pipeline = RagPipeline(retriever=_make_retriever())
    resp = pipeline.answer_question("xyzzyxwq receita culinária inexistente", top_k=3)
    assert resp.grounded is False
    assert resp.mode == "insufficient_evidence"
    assert resp.evidence == []


def test_rag_com_llm_mockado_preserva_evidencia_literal() -> None:
    class FakeGeminiClient(GeminiClient):
        def __init__(self) -> None:
            super().__init__(api_key="fake-key")

        def generate_grounded_answer(self, question, evidence_chunks, *, is_posture_event=False):
            return "Ajuste o monitor na altura dos olhos conforme [nr17]."

    pipeline = RagPipeline(retriever=_make_retriever(), llm_client=FakeGeminiClient())
    resp = pipeline.answer_question("Qual a altura ideal do monitor?")
    assert resp.mode == "rag_llm"
    assert resp.grounded is True
    assert "[nr17]" in resp.answer
    assert len(resp.evidence) >= 1


def test_rag_recommend_for_posture_retorna_evidencia_e_seguranca() -> None:
    pipeline = RagPipeline(retriever=_make_retriever())
    event = PostureEvent(
        event_id=uuid4(),
        timestamp=datetime.now(UTC),
        camera_mode="frontal",
        landmarks_confidence=0.92,
        duration_minutes=3.5,
        features=PostureFeatures(
            head_forward_offset=0.25,
            trunk_inclination=0.08,
            shoulder_asymmetry=0.03,
            apparent_face_scale=0.18,
        ),
        classification=PostureClassification(label="FORWARD_HEAD", confidence=0.88),
    )
    resp = pipeline.recommend_for_posture(event)
    assert resp.category == "FORWARD_HEAD"
    assert resp.safety.approved is True
    assert resp.safety.evidence_verified is True
    assert len(resp.evidence) >= 1


def test_hybrid_retriever_com_chromadb_indexado(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    from knowledge_base.ingest import reconstruir_de_chunks

    idx_dir = tmp_path / "chroma"
    manifest_path = tmp_path / "manifest.json"
    chunks_out = tmp_path / "chunks.jsonl"
    reconstruir_de_chunks(
        chunks_path=CORPUS_PATH,
        index_dir=idx_dir,
        manifest_path=manifest_path,
        embedder_name="hash",
        chunks_out=chunks_out,
    )

    retriever = HybridRetriever(
        chroma_persist_dir=idx_dir,
        corpus_chunks_path=CORPUS_PATH,
        kb_manifest_path=manifest_path,
    )
    st = retriever.status()
    assert st["status"] == "indexed"
    assert st["chroma_chunks"] == 507
    assert st["retrieval_mode"] == "hybrid_chroma_bm25"

    hits = retriever.retrieve("comportamento sedentário pausas", top_k=3)
    assert len(hits) == 3
    assert all(h.text for h in hits)
