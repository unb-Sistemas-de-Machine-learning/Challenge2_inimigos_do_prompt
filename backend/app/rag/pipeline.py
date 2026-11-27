"""Pipeline de RAG (recuperação + geração com citação literal obrigatória)."""

from __future__ import annotations

import re
from uuid import uuid4

from app.llm.client import GeminiClient
from app.rag.retriever import HybridRetriever, RetrievedChunk, tokenize
from app.schemas.contracts import (
    ChatResponse,
    EvidenceItem,
    PostureEvent,
    RecommendationResponse,
    SafetyDecision,
)

_POSTURE_QUERY_MAP: dict[str, str] = {
    "FORWARD_HEAD": "protrusão cervical cabeça à frente altura monitor distância tela ergonomia NR-17",
    "TOO_CLOSE": "distância monitor tela olhos conforto visual mobiliário posto de trabalho NR-17",
    "SHOULDER_TILT": "assimetria ombros apoio antebraços altura mesa cadeira postura sentada NR-17",
    "HEAD_TILT": "inclinação lateral cabeça posicionamento monitor alinhamento visual NR-17",
    "ELEVATED_SHOULDERS": "ombros elevados tensão cervical altura mesa apoio antebraços NR-17",
    "TRUNK_ROTATION": "rotação de tronco alinhamento monitor teclado assento NR-17",
    "PROLONGED_ABSENCE": "pausas ativas comportamento sedentário atividade física OMS",
    "BREAK_NEEDED": "pausas ativas comportamento sedentário tempo sentado OMS",
    "ADEQUATE": "manutenção postura neutra pausas ativas comportamento sedentário OMS",
}


def extract_literal_quote(chunk_text: str, query: str, max_chars: int = 320) -> str:
    """Extrai trecho literal (`exact_quote`) garantidamente presente em `chunk_text`."""
    cleaned = chunk_text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    query_tokens = set(tokenize(query))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if s.strip()]
    best_sentence = ""
    best_overlap = -1
    for sent in sentences:
        if sent not in chunk_text:
            continue
        overlap = len(query_tokens & set(tokenize(sent)))
        if overlap > best_overlap:
            best_overlap = overlap
            best_sentence = sent

    if best_sentence and len(best_sentence) <= max_chars:
        return best_sentence

    # Garante substring literal exata caso a sentença seja maior que max_chars
    snippet = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    if snippet and snippet in chunk_text:
        return snippet
    return cleaned[:max_chars]


def _build_evidence(chunks: list[RetrievedChunk], query: str) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for chunk in chunks:
        quote = extract_literal_quote(chunk.text, query)
        if not quote or quote not in chunk.text:
            continue
        evidence.append(
            EvidenceItem(
                document_id=chunk.document_id,
                source=chunk.source,
                section=chunk.section,
                page=chunk.page,
                exact_quote=quote,
            )
        )
    return evidence


def _synthesize_extractive_answer(
    chunks: list[RetrievedChunk],
    evidence: list[EvidenceItem],
    *,
    prefix: str = "",
) -> str:
    lines: list[str] = []
    if prefix:
        lines.append(prefix)
    for item in evidence[:2]:
        loc = f"{item.document_id}"
        if item.section and item.section != "unspecified":
            loc += f" ({item.section})"
        if item.page is not None:
            loc += f", p. {item.page}"
        lines.append(f"Segundo [{loc}]: \"{item.exact_quote}\"")
    return "\n\n".join(lines)


class RagPipeline:
    """Orquestra recuperação híbrida e geração fundamentada com citações obrigatórias."""

    def __init__(self, retriever: HybridRetriever, llm_client: GeminiClient | None = None) -> None:
        self.retriever = retriever
        self.llm_client = llm_client or GeminiClient()

    def answer_question(self, question: str, top_k: int = 3) -> ChatResponse:
        """Responde perguntas livres de ergonomia e pausas com citação literal obrigatória."""
        chunks = self.retriever.retrieve(question, top_k=top_k)
        evidence = _build_evidence(chunks, question)
        if not evidence:
            return ChatResponse(
                answer=(
                    "Não encontrei evidências suficientes na base oficial (NR-17 e OMS 2020) "
                    "para responder com segurança a essa pergunta."
                ),
                grounded=False,
                confidence=0.0,
                mode="insufficient_evidence",
                evidence=[],
            )

        llm_payload = [
            {
                "document_id": c.document_id,
                "section": c.section,
                "page": c.page,
                "text": c.text,
            }
            for c in chunks
        ]
        llm_answer = self.llm_client.generate_grounded_answer(
            question, llm_payload, is_posture_event=False
        )
        if llm_answer:
            return ChatResponse(
                answer=llm_answer,
                grounded=True,
                confidence=0.85,
                mode="rag_llm",
                evidence=evidence,
            )

        extractive = _synthesize_extractive_answer(
            chunks,
            evidence,
            prefix="Com base nas fontes oficiais recuperadas:",
        )
        return ChatResponse(
            answer=extractive,
            grounded=True,
            confidence=0.75,
            mode="rag_extractive",
            evidence=evidence,
        )

    def recommend_for_posture(self, event: PostureEvent, top_k: int = 3) -> RecommendationResponse:
        """Gera recomendação fundamentada via RAG a partir de um PostureEvent numérico (sem imagem)."""
        label = event.classification.label.upper()
        query = _POSTURE_QUERY_MAP.get(
            label,
            f"ergonomia postura {label.lower().replace('_', ' ')} NR-17 OMS",
        )
        chunks = self.retriever.retrieve(query, top_k=top_k)
        evidence = _build_evidence(chunks, query)

        if not evidence:
            return RecommendationResponse(
                recommendation_id=uuid4(),
                recommendation=(
                    "Não foi possível recuperar evidências oficiais suficientes para este evento postural. "
                    "Os alertas locais continuam operando de forma independente."
                ),
                category=label,
                confidence=0.0,
                evidence=[],
                safety=SafetyDecision(
                    approved=False,
                    scope="ergonomic_guidance",
                    evidence_verified=False,
                    requires_professional=False,
                    reason="Sem evidência literal recuperada na base oficial.",
                ),
                mode="insufficient_evidence",
                local_alerts_independent=True,
            )

        event_summary = (
            f"Evento postural detectado localmente: {label} "
            f"(confiança={event.classification.confidence:.2f}, "
            f"duração={event.duration_minutes:.1f} min, modo={event.camera_mode})."
        )
        llm_payload = [
            {
                "document_id": c.document_id,
                "section": c.section,
                "page": c.page,
                "text": c.text,
            }
            for c in chunks
        ]
        llm_answer = self.llm_client.generate_grounded_answer(
            f"{event_summary} Consulta: {query}",
            llm_payload,
            is_posture_event=True,
        )
        mode = "rag_llm" if llm_answer else "rag_extractive"
        recommendation_text = llm_answer or _synthesize_extractive_answer(
            chunks,
            evidence,
            prefix=f"Orientação ergonômica para {label}:",
        )

        return RecommendationResponse(
            recommendation_id=uuid4(),
            recommendation=recommendation_text,
            category=label,
            confidence=0.85 if llm_answer else 0.75,
            evidence=evidence,
            safety=SafetyDecision(
                approved=True,
                scope="ergonomic_guidance",
                evidence_verified=True,
                requires_professional=False,
                reason="Recomendação fundamentada com citações literais verificadas da base oficial.",
            ),
            mode=mode,
            local_alerts_independent=True,
        )
