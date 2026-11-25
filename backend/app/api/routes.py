"""Rotas iniciais da API REST do ErgoAI (esqueleto conforme SPEC.md)."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.contracts import ChatRequest, FeedbackRequest, PostureEvent

router = APIRouter(prefix="/api/v1", tags=["ergoai"])


@router.get("/knowledge/status")
def knowledge_status() -> dict[str, str]:
    """Consulta o estado da base de conhecimento do RAG."""
    return {"status": "not_indexed", "detail": "Base de conhecimento ainda não indexada."}


@router.post("/recommendations", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_recommendation(event: PostureEvent) -> dict[str, str]:
    """Gera recomendações fundamentadas via RAG a partir de um PostureEvent."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Pipeline RAG + LLM ainda não implementado.",
    )


@router.post("/chat", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def chat_ergonomics(payload: ChatRequest) -> dict[str, str]:
    """Responde dúvidas sobre ergonomia e pausas com citações rastreáveis."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint de chat RAG ainda não implementado.",
    )


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
