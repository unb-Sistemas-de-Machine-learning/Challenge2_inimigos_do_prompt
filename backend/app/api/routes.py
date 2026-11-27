"""Rotas da API REST do ErgoAI (RAG, recomendações, status e feedback)."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.llm.client import GeminiClient
from app.rag.pipeline import RagPipeline
from app.rag.retriever import HybridRetriever
from app.schemas.contracts import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    KnowledgeStatusResponse,
    PostureEvent,
    RecommendationResponse,
)

router = APIRouter(prefix="/api/v1", tags=["ergoai"])


@lru_cache
def _cached_retriever(
    chroma_persist_dir: str,
    corpus_chunks_path: str,
    kb_manifest_path: str,
) -> HybridRetriever:
    return HybridRetriever(
        chroma_persist_dir=chroma_persist_dir,
        corpus_chunks_path=corpus_chunks_path,
        kb_manifest_path=kb_manifest_path,
    )


def get_rag_pipeline(settings: Annotated[Settings, Depends(get_settings)]) -> RagPipeline:
    """Dependência FastAPI que fornece o pipeline RAG configurado."""
    retriever = _cached_retriever(
        settings.chroma_persist_dir,
        settings.corpus_chunks_path,
        settings.kb_manifest_path,
    )
    llm_client = GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )
    return RagPipeline(retriever=retriever, llm_client=llm_client)


@router.get("/knowledge/status", response_model=KnowledgeStatusResponse)
def knowledge_status(
    pipeline: Annotated[RagPipeline, Depends(get_rag_pipeline)],
) -> KnowledgeStatusResponse:
    """Consulta o estado da base de conhecimento do RAG (ChromaDB e corpus BM25)."""
    return KnowledgeStatusResponse(**pipeline.retriever.status())


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendation(
    event: PostureEvent,
    pipeline: Annotated[RagPipeline, Depends(get_rag_pipeline)],
) -> RecommendationResponse:
    """Gera recomendações fundamentadas via RAG a partir de um PostureEvent numérico (sem vídeo)."""
    return pipeline.recommend_for_posture(event)


@router.post("/chat", response_model=ChatResponse)
def chat_ergonomics(
    payload: ChatRequest,
    pipeline: Annotated[RagPipeline, Depends(get_rag_pipeline)],
) -> ChatResponse:
    """Responde dúvidas sobre ergonomia e pausas ativas com citações literais obrigatórias."""
    return pipeline.answer_question(payload.question, top_k=payload.top_k)


@router.post("/setup/analyze", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def analyze_setup() -> dict[str, str]:
    """Analisa imagem do posto de trabalho (sem persistir imagens)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Análise multimodal de setup ainda não implementada.",
    )


@router.post("/feedback")
def register_feedback(payload: FeedbackRequest) -> dict[str, str]:
    """Registra feedback do usuário sobre alertas posturais."""
    return {"status": "received", "event_id": str(payload.event_id)}
