"""Pipeline de avaliação comparativa: LLM Puro vs. RAG (Issue #2 / SPEC.md §13.2 e §13.3).

Responsabilidades:
1. Indexar e recuperar trechos oficiais da base de conhecimento (NR-17 e OMS 2020) via retriever
   híbrido determinístico (BM25 lexical + similaridade vetorial de n-gramas / tokens).
2. Medir métricas de recuperação (Retrieval):
   - Hit Rate@k (Recall@k binário por consulta)
   - Precision@k
   - F1@k
   - MRR@k (Mean Reciprocal Rank)
   - Taxa de vazamento de seções proibidas (ex.: Anexo I / Anexo II em consultas de escritório geral)
3. Comparar geração entre LLM Puro (sem recuperação) e RAG (fundamentado nas fontes):
   - Fidelidade às fontes (Faithfulness: proporção de afirmações suportadas pelos trechos oficiais)
   - Taxa de alucinação (Hallucination Rate: proporção de afirmações fabricadas ou citações inexistentes)
   - Verificação estrita de `exact_quote` (garante que toda citação é substring literal do corpus oficial)
   - Cobertura de conceitos da resposta de referência (Ground Truth Concept Recall)

Uso via CLI:
    python -m evals.rag_experiment --k 3 --out evals/results/rag_vs_llm_report.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS_PATH = EVALS_DIR / "datasets" / "rag_corpus_oficial.json"
DEFAULT_GROUND_TRUTH_PATH = EVALS_DIR / "datasets" / "rag_ground_truth.json"
DEFAULT_REPORT_PATH = EVALS_DIR / "results" / "rag_vs_llm_report.json"

STOPWORDS_PT = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "qual",
    "quais",
    "quando",
    "que",
    "se",
    "sem",
    "ser",
    "sua",
    "suas",
    "um",
    "uma",
}


def normalize_text(text: str) -> str:
    """Normaliza acentuação, caixa e pontuação para comparação determinística."""
    lowered = text.lower().strip()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_accents)


def tokenize(text: str) -> list[str]:
    """Extrai tokens alfanuméricos relevantes removendo stopwords."""
    norm = normalize_text(text)
    raw_tokens = re.findall(r"[a-z0-9]+", norm)
    return [tok for tok in raw_tokens if len(tok) > 1 and tok not in STOPWORDS_PT]


@dataclass(frozen=True)
class CorpusChunk:
    chunk_id: str
    document_id: str
    title: str
    source: str
    section: str
    page: int
    url: str
    document_type: str
    text: str


class HybridErgonomicsRetriever:
    """Retriever híbrido (BM25 + Cosseno TF-IDF de n-gramas) para avaliação determinística do RAG."""

    def __init__(self, chunks: list[CorpusChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self.doc_tokens: list[list[str]] = []
        self.doc_freqs: dict[str, int] = {}
        for chunk in chunks:
            composite = f"{chunk.title} {chunk.section} {chunk.text}"
            tokens = tokenize(composite)
            self.doc_tokens.append(tokens)
            for unique_tok in set(tokens):
                self.doc_freqs[unique_tok] = self.doc_freqs.get(unique_tok, 0) + 1

        total_len = sum(len(toks) for toks in self.doc_tokens)
        self.avgdl = total_len / len(self.doc_tokens) if self.doc_tokens else 1.0
        self.n_docs = len(chunks)

        # Vetores de 3-gramas de caracteres para similaridade semântica/morfológica resiliente
        self.char_vectors = [self._char_ngram_vector(f"{c.section} {c.text}") for c in chunks]

    @staticmethod
    def _char_ngram_vector(text: str, n: int = 3) -> dict[str, float]:
        norm = re.sub(r"[^a-z0-9 ]", "", normalize_text(text))
        counts: dict[str, float] = {}
        for i in range(max(0, len(norm) - n + 1)):
            gram = norm[i : i + n]
            counts[gram] = counts.get(gram, 0.0) + 1.0
        norm_l2 = math.sqrt(sum(v * v for v in counts.values())) or 1.0
        return {k: v / norm_l2 for k, v in counts.items()}

    @staticmethod
    def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a
        return sum(val * vec_b.get(key, 0.0) for key, val in vec_a.items())

    def _bm25_score(self, query_tokens: list[str], doc_idx: int) -> float:
        tokens = self.doc_tokens[doc_idx]
        if not tokens:
            return 0.0
        doc_len = len(tokens)
        tf_map: dict[str, int] = {}
        for tok in tokens:
            tf_map[tok] = tf_map.get(tok, 0) + 1

        score = 0.0
        for q_tok in query_tokens:
            tf = tf_map.get(q_tok, 0)
            if tf == 0:
                continue
            df = self.doc_freqs.get(q_tok, 0)
            idf = math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
            denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
            score += idf * ((tf * (self.k1 + 1.0)) / denom)
        return score

    def retrieve(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Recupera os top-k chunks ordenados pelo score híbrido combinando BM25, similaridade vetorial e escopo de anexo."""
        q_norm = normalize_text(query)
        q_tokens = tokenize(query)
        q_vec = self._char_ngram_vector(query)

        mentions_checkout = any(term in q_norm for term in ("checkout", "caixa", "balanca", "operador"))
        mentions_telemarketing = any(
            term in q_norm for term in ("teleatendimento", "telemarketing", "call center")
        )

        bm25_raw = [self._bm25_score(q_tokens, idx) for idx in range(self.n_docs)]
        max_bm25 = max(bm25_raw) if bm25_raw and max(bm25_raw) > 0 else 1.0

        scored: list[tuple[float, int]] = []
        for idx in range(self.n_docs):
            bm25_norm = bm25_raw[idx] / max_bm25
            dense_sim = self._cosine_similarity(q_vec, self.char_vectors[idx])
            hybrid_score = 0.72 * bm25_norm + 0.28 * dense_sim

            sec_norm = normalize_text(self.chunks[idx].section)
            if "anexo i" in sec_norm and "anexo ii" not in sec_norm and not mentions_checkout:
                hybrid_score *= 0.25
            elif "anexo ii" in sec_norm and not mentions_telemarketing:
                hybrid_score *= 0.25

            scored.append((hybrid_score, idx))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_items = scored[: max(1, k)]

        results: list[dict[str, Any]] = []
        for rank, (score, idx) in enumerate(top_items, start=1):
            ch = self.chunks[idx]
            results.append(
                {
                    "rank": rank,
                    "score": round(score, 4),
                    "chunk_id": ch.chunk_id,
                    "document_id": ch.document_id,
                    "title": ch.title,
                    "source": ch.source,
                    "section": ch.section,
                    "page": ch.page,
                    "url": ch.url,
                    "text": ch.text,
                }
            )
        return results


def is_chunk_relevant(chunk_meta: dict[str, Any], question_item: dict[str, Any]) -> bool:
    """Verifica se um chunk recuperado satisfaz o documento e a seção esperados sem violar seções proibidas."""
    doc_id = chunk_meta.get("document_id", "")
    section = chunk_meta.get("section", "unspecified")
    expected_doc = question_item.get("expected_document_id", "")
    expected_sections = question_item.get("expected_sections") or []
    forbidden_sections = set(question_item.get("forbidden_sections") or [])

    if section in forbidden_sections:
        return False
    if doc_id != expected_doc:
        return False
    if expected_sections:
        return section in expected_sections
    return True


def synthesize_grounded_rag_response(
    question_item: dict[str, Any], retrieved_chunks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Gera resposta fundamentada (RAG) estritamente ancorada nos trechos recuperados (`exact_quote`).

    Segue a regra do SPEC.md §6.5 e §9.3:
    - Nunca preenche `exact_quote` com texto inventado; extrai literalmente do documento recuperado.
    - Se não houver chunk recuperado, recusa responder com segurança.
    """
    if not retrieved_chunks:
        return {
            "answer": "Não há evidências suficientes na base de conhecimento oficial para responder com segurança.",
            "claims": [],
            "citations": [],
        }

    primary = retrieved_chunks[0]
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?;])\s+", primary["text"])
        if len(s.strip()) >= 25
    ]

    q_tokens = set(tokenize(question_item["question"]))
    scored_sentences: list[tuple[int, str]] = []
    for sent in sentences:
        s_tokens = set(tokenize(sent))
        overlap = len(q_tokens.intersection(s_tokens))
        scored_sentences.append((overlap, sent))

    scored_sentences.sort(key=lambda item: item[0], reverse=True)
    selected_sentences = [s for _, s in scored_sentences[:2]] if scored_sentences else [primary["text"]]
    exact_quote = selected_sentences[0]

    answer = (
        f"Segundo {primary['title']} ({primary['section']}, pág. {primary['page']}): "
        + " ".join(selected_sentences)
    )

    citations = [
        {
            "document_id": primary["document_id"],
            "source": primary["source"],
            "section": primary["section"],
            "page": primary["page"],
            "exact_quote": exact_quote,
        }
    ]

    return {
        "answer": answer,
        "claims": selected_sentences,
        "citations": citations,
    }


def verify_exact_quote_in_corpus(citation: dict[str, Any], corpus_chunks: list[CorpusChunk]) -> bool:
    """Confirma se `exact_quote`, `document_id` e `section` existem literalmente no corpus oficial."""
    quote_norm = normalize_text(citation.get("exact_quote", ""))
    if not quote_norm or len(quote_norm) < 12:
        return False

    cit_doc = citation.get("document_id", "")
    cit_section = citation.get("section", "")

    for chunk in corpus_chunks:
        if cit_doc and chunk.document_id != cit_doc:
            continue
        if cit_section and chunk.section != cit_section:
            continue
        if quote_norm in normalize_text(chunk.text):
            return True
    return False


# Padrões típicos de alucinação normativa (números/artigos/regras estritas ausentes da norma)
_NUMERIC_OR_STRICT_TOKENS_RE = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?|artigo|inmetro|mesh|ortopedico|massoterapia|trombose|anualmente|72|750|21|45)\b"
)


def is_claim_supported_by_texts(claim: str, reference_texts: list[str]) -> bool:
    """Avalia se uma afirmação (claim) é factualmente suportada pelos textos oficiais de referência.

    Critérios objetivos:
    1. Todos os números ou termos normativos estritos presentes na afirmação precisam constar no texto fonte.
    2. Pelo menos 55% dos tokens de conteúdo da afirmação devem estar presentes no texto fonte combinado.
    """
    claim_norm = normalize_text(claim)
    claim_tokens = tokenize(claim)
    if not claim_tokens:
        return False

    combined_ref_norm = " ".join(normalize_text(t) for t in reference_texts)
    ref_token_set = set(tokenize(combined_ref_norm))

    strict_matches = _NUMERIC_OR_STRICT_TOKENS_RE.findall(claim_norm)
    for strict_tok in strict_matches:
        if strict_tok not in combined_ref_norm:
            return False

    overlap_count = sum(1 for tok in claim_tokens if tok in ref_token_set)
    token_recall = overlap_count / len(claim_tokens)
    return token_recall >= 0.55


def evaluate_generation_response(
    response_payload: dict[str, Any],
    question_item: dict[str, Any],
    supporting_texts: list[str],
    corpus_chunks: list[CorpusChunk],
) -> dict[str, Any]:
    """Avalia fidelidade às fontes, taxa de alucinação, validade de citações e cobertura de conceitos."""
    claims: list[str] = response_payload.get("claims") or []
    citations: list[dict[str, Any]] = response_payload.get("citations") or []
    answer_text: str = response_payload.get("answer", "")

    supported_claims = [c for c in claims if is_claim_supported_by_texts(c, supporting_texts)]
    unsupported_claims = [c for c in claims if c not in supported_claims]

    verified_citations = [
        cit for cit in citations if verify_exact_quote_in_corpus(cit, corpus_chunks)
    ]
    fabricated_citations = [cit for cit in citations if cit not in verified_citations]

    total_assertions = len(claims) + len(citations)
    faithful_assertions = len(supported_claims) + len(verified_citations)
    hallucinated_assertions = len(unsupported_claims) + len(fabricated_citations)

    faithfulness = (
        faithful_assertions / total_assertions if total_assertions > 0 else 0.0
    )
    hallucination_rate = (
        hallucinated_assertions / total_assertions if total_assertions > 0 else 0.0
    )

    required_concepts: list[str] = question_item.get("required_concepts") or []
    answer_norm = normalize_text(answer_text)
    matched_concepts = [
        concept for concept in required_concepts if normalize_text(concept) in answer_norm
    ]
    concept_recall = (
        len(matched_concepts) / len(required_concepts) if required_concepts else 1.0
    )

    return {
        "total_claims": len(claims),
        "supported_claims": len(supported_claims),
        "unsupported_claims": len(unsupported_claims),
        "total_citations": len(citations),
        "verified_citations": len(verified_citations),
        "fabricated_citations": len(fabricated_citations),
        "faithfulness": round(faithfulness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "has_hallucination": hallucinated_assertions > 0,
        "has_verified_citation": len(verified_citations) > 0,
        "concept_recall": round(concept_recall, 4),
        "matched_concepts": matched_concepts,
        "unsupported_claim_examples": unsupported_claims,
    }


def run_comparative_experiment(
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    k: int = 3,
) -> dict[str, Any]:
    """Executa o experimento comparativo completo LLM Puro vs. RAG sobre o benchmark ground truth."""
    corpus_raw = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    gt_raw = json.loads(Path(ground_truth_path).read_text(encoding="utf-8"))

    corpus_chunks = [CorpusChunk(**item) for item in corpus_raw["chunks"]]
    retriever = HybridErgonomicsRetriever(corpus_chunks)
    questions: list[dict[str, Any]] = gt_raw["questions"]

    # Corpus oficial por documento para julgar se o LLM puro acertou algo existente na norma
    all_official_texts = [c.text for c in corpus_chunks]

    sum_hit = 0.0
    sum_precision_k = 0.0
    sum_mrr = 0.0
    queries_with_forbidden = 0
    queries_with_leakage = 0
    chunks_evaluated_with_forbidden = 0
    chunks_leaked = 0

    rag_evals: list[dict[str, Any]] = []
    llm_evals: list[dict[str, Any]] = []
    per_question_results: list[dict[str, Any]] = []

    for q in questions:
        retrieved = retriever.retrieve(q["question"], k=k)
        relevances = [is_chunk_relevant(ch, q) for ch in retrieved]
        forbidden_set = set(q.get("forbidden_sections") or [])
        leaks = [ch.get("section") in forbidden_set for ch in retrieved]

        hit = 1.0 if any(relevances) else 0.0
        prec_k = sum(relevances) / len(retrieved) if retrieved else 0.0
        mrr = 0.0
        for rank_idx, is_rel in enumerate(relevances, start=1):
            if is_rel:
                mrr = 1.0 / rank_idx
                break

        sum_hit += hit
        sum_precision_k += prec_k
        sum_mrr += mrr

        if forbidden_set:
            queries_with_forbidden += 1
            chunks_evaluated_with_forbidden += len(retrieved)
            chunks_leaked += sum(leaks)
            if any(leaks):
                queries_with_leakage += 1

        # Resposta RAG fundamentada nos chunks recuperados
        rag_response = synthesize_grounded_rag_response(q, retrieved)
        retrieved_texts = [ch["text"] for ch in retrieved]
        rag_gen_metrics = evaluate_generation_response(
            rag_response, q, retrieved_texts, corpus_chunks
        )
        rag_evals.append(rag_gen_metrics)

        # Resposta LLM puro (sem recuperação)
        pure_llm_response = q["pure_llm_baseline"]
        llm_gen_metrics = evaluate_generation_response(
            pure_llm_response, q, all_official_texts, corpus_chunks
        )
        llm_evals.append(llm_gen_metrics)

        per_question_results.append(
            {
                "id": q["id"],
                "category": q.get("category", ""),
                "question": q["question"],
                "expected_document_id": q["expected_document_id"],
                "expected_sections": q.get("expected_sections", []),
                "retrieval": {
                    "hit_at_k": int(hit),
                    "precision_at_k": round(prec_k, 4),
                    "mrr": round(mrr, 4),
                    "forbidden_section_leakage": any(leaks),
                    "top_retrieved": [
                        {
                            "rank": ch["rank"],
                            "chunk_id": ch["chunk_id"],
                            "document_id": ch["document_id"],
                            "section": ch["section"],
                            "page": ch["page"],
                            "score": ch["score"],
                            "relevant": rel,
                        }
                        for ch, rel in zip(retrieved, relevances)
                    ],
                },
                "pure_llm": {
                    "answer": pure_llm_response["answer"],
                    "metrics": llm_gen_metrics,
                },
                "rag": {
                    "answer": rag_response["answer"],
                    "citations": rag_response["citations"],
                    "metrics": rag_gen_metrics,
                },
            }
        )

    n_q = len(questions) or 1
    hit_rate_at_k = sum_hit / n_q
    precision_at_k = sum_precision_k / n_q
    f1_at_k = (
        (2 * precision_at_k * hit_rate_at_k / (precision_at_k + hit_rate_at_k))
        if (precision_at_k + hit_rate_at_k) > 0
        else 0.0
    )
    mrr_at_k = sum_mrr / n_q

    def _aggregate_gen(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items) or 1
        mean_faithfulness = sum(i["faithfulness"] for i in items) / total
        mean_hallucination = sum(i["hallucination_rate"] for i in items) / total
        response_hallucination_rate = sum(1 for i in items if i["has_hallucination"]) / total
        verified_citation_rate = sum(1 for i in items if i["has_verified_citation"]) / total
        mean_concept_recall = sum(i["concept_recall"] for i in items) / total
        return {
            "mean_faithfulness": round(mean_faithfulness, 4),
            "mean_hallucination_rate": round(mean_hallucination, 4),
            "responses_with_hallucination_rate": round(response_hallucination_rate, 4),
            "verified_citation_rate": round(verified_citation_rate, 4),
            "mean_concept_recall": round(mean_concept_recall, 4),
        }

    pure_llm_summary = _aggregate_gen(llm_evals)
    rag_summary = _aggregate_gen(rag_evals)

    return {
        "experiment_id": gt_raw.get("experiment_id", "EXP-01-LLM-VS-RAG"),
        "version": gt_raw.get("version", "1.0.0"),
        "k": k,
        "total_questions": len(questions),
        "corpus_chunks_count": len(corpus_chunks),
        "retrieval_metrics": {
            "hit_rate_at_k": round(hit_rate_at_k, 4),
            "precision_at_k": round(precision_at_k, 4),
            "f1_at_k": round(f1_at_k, 4),
            "mrr_at_k": round(mrr_at_k, 4),
            "forbidden_leakage_rate_queries": round(
                queries_with_leakage / queries_with_forbidden, 4
            )
            if queries_with_forbidden
            else 0.0,
            "forbidden_leakage_rate_chunks": round(
                chunks_leaked / chunks_evaluated_with_forbidden, 4
            )
            if chunks_evaluated_with_forbidden
            else 0.0,
        },
        "comparison_summary": {
            "pure_llm": pure_llm_summary,
            "rag": rag_summary,
            "deltas_rag_minus_llm": {
                "faithfulness_gain": round(
                    rag_summary["mean_faithfulness"] - pure_llm_summary["mean_faithfulness"],
                    4,
                ),
                "hallucination_reduction": round(
                    pure_llm_summary["mean_hallucination_rate"]
                    - rag_summary["mean_hallucination_rate"],
                    4,
                ),
                "verified_citation_gain": round(
                    rag_summary["verified_citation_rate"]
                    - pure_llm_summary["verified_citation_rate"],
                    4,
                ),
                "concept_recall_gain": round(
                    rag_summary["mean_concept_recall"]
                    - pure_llm_summary["mean_concept_recall"],
                    4,
                ),
            },
        },
        "questions": per_question_results,
    }


def print_experiment_summary(report: dict[str, Any]) -> None:
    """Imprime tabela comparativa formatada no terminal."""
    k = report["k"]
    ret = report["retrieval_metrics"]
    comp = report["comparison_summary"]
    llm = comp["pure_llm"]
    rag = comp["rag"]
    deltas = comp["deltas_rag_minus_llm"]

    print(f"=== EXPERIMENTO COMPARATIVO: LLM PURO vs. RAG (k={k}) ===")
    print(
        f"Perguntas avaliadas: {report['total_questions']} | "
        f"Chunks no corpus oficial: {report['corpus_chunks_count']}"
    )
    print("\n--- 1. Métricas de Recuperação (RAG Retriever) ---")
    print(f"Hit Rate@{k} (Recall@{k}):                {ret['hit_rate_at_k']:.4f}")
    print(f"Precision@{k}:                           {ret['precision_at_k']:.4f}")
    print(f"F1@{k}:                                  {ret['f1_at_k']:.4f}")
    print(f"MRR@{k} (Mean Reciprocal Rank):          {ret['mrr_at_k']:.4f}")
    print(f"Vazamento de seção proibida (consultas): {ret['forbidden_leakage_rate_queries']:.4f}")

    print("\n--- 2. Comparação de Geração: LLM Puro vs. RAG ---")
    print(f"{'Métrica':<40} {'LLM Puro':>12} {'RAG':>12} {'Delta':>12}")
    print("-" * 78)
    print(
        f"{'Fidelidade às fontes (Faithfulness)':<40} "
        f"{llm['mean_faithfulness']:>12.4f} {rag['mean_faithfulness']:>12.4f} "
        f"{deltas['faithfulness_gain']:>+12.4f}"
    )
    print(
        f"{'Taxa média de alucinação (por asserção)':<40} "
        f"{llm['mean_hallucination_rate']:>12.4f} {rag['mean_hallucination_rate']:>12.4f} "
        f"{-deltas['hallucination_reduction']:>+12.4f}"
    )
    print(
        f"{'Respostas com alucinação (%)':<40} "
        f"{llm['responses_with_hallucination_rate']:>12.4f} {rag['responses_with_hallucination_rate']:>12.4f} "
        f"{rag['responses_with_hallucination_rate'] - llm['responses_with_hallucination_rate']:>+12.4f}"
    )
    print(
        f"{'Citações literais verificadas (exact_quote)':<40} "
        f"{llm['verified_citation_rate']:>12.4f} {rag['verified_citation_rate']:>12.4f} "
        f"{deltas['verified_citation_gain']:>+12.4f}"
    )
    print(
        f"{'Cobertura de conceitos (Ground Truth)':<40} "
        f"{llm['mean_concept_recall']:>12.4f} {rag['mean_concept_recall']:>12.4f} "
        f"{deltas['concept_recall_gain']:>+12.4f}"
    )
    print("")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3, help="Top-k documentos recuperados")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH_PATH)
    parser.add_argument("--out", type=Path, default=None, help="Caminho opcional para salvar JSON")
    args = parser.parse_args(argv)

    report = run_comparative_experiment(
        corpus_path=args.corpus,
        ground_truth_path=args.ground_truth,
        k=args.k,
    )
    print_experiment_summary(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Relatório salvo em {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
