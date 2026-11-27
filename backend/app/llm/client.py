"""Cliente LLM (Google Gemini) para geração fundamentada no RAG."""

from __future__ import annotations

import logging
from collections.abc import Sequence

logger = logging.getLogger(__name__)


class GeminiClient:
    """Wrapper fino sobre `google-genai` com degradação graciosa sem chave de API."""

    def __init__(self, api_key: str = "", model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key.strip()
        self.model = model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_grounded_answer(
        self,
        question: str,
        evidence_chunks: Sequence[dict[str, str | int | None]],
        *,
        is_posture_event: bool = False,
    ) -> str | None:
        """Gera resposta em português estritamente baseada nos trechos recuperados.

        Retorna `None` quando `GEMINI_API_KEY` não está configurada ou em caso de falha,
        permitindo fallback extrativo determinístico sem interromper o serviço.
        """
        if not self.is_configured or not evidence_chunks:
            return None

        context_blocks = []
        for idx, chunk in enumerate(evidence_chunks, start=1):
            doc_id = chunk.get("document_id", "fonte")
            section = chunk.get("section") or "unspecified"
            page = chunk.get("page")
            page_str = f"p. {page}" if page is not None else "p. ?"
            text = str(chunk.get("text", "")).strip()
            context_blocks.append(f"[{idx}] ({doc_id} | {section} | {page_str})\n{text}")

        role_instruction = (
            "Você é o assistente ergonômico do ErgoAI. Gere uma recomendação prática e breve "
            "para o desvio postural/evento informado, usando EXCLUSIVAMENTE os trechos oficiais abaixo."
            if is_posture_event
            else "Você é o assistente ergonômico do ErgoAI. Responda à pergunta sobre ergonomia e "
            "pausas ativas usando EXCLUSIVAMENTE os trechos oficiais abaixo."
        )
        prompt = (
            f"{role_instruction}\n"
            "Regras obrigatórias:\n"
            "1. Não invente dados, números, normas ou diagnósticos médicos.\n"
            "2. Cite o identificador da fonte entre colchetes, ex.: [nr17] ou [oms2020].\n"
            "3. Se os trechos não responderem completamente, informe a limitação de forma clara.\n"
            "4. Responda em português do Brasil, de forma objetiva (máximo 2 parágrafos curtos).\n\n"
            f"Consulta:\n{question}\n\n"
            "Trechos oficiais recuperados:\n"
            + "\n\n".join(context_blocks)
        )

        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = getattr(response, "text", None)
            return text.strip() if isinstance(text, str) and text.strip() else None
        except Exception as exc:  # noqa: BLE001 - fallback extrativo garante disponibilidade sem LLM
            logger.warning("Falha ao chamar Gemini API (%s); usando fallback extrativo.", exc)
            return None
