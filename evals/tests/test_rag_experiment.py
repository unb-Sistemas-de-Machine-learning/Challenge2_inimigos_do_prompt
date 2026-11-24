"""Testes automatizados para o Experimento Comparativo LLM Puro vs. RAG (Issue #2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.rag_experiment import (
    CorpusChunk,
    DEFAULT_CORPUS_PATH,
    DEFAULT_GROUND_TRUTH_PATH,
    HybridErgonomicsRetriever,
    evaluate_generation_response,
    is_chunk_relevant,
    is_claim_supported_by_texts,
    main,
    run_comparative_experiment,
    synthesize_grounded_rag_response,
    verify_exact_quote_in_corpus,
)


class TestRagVsLlmExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        corpus_data = json.loads(DEFAULT_CORPUS_PATH.read_text(encoding="utf-8"))
        cls.chunks = [CorpusChunk(**item) for item in corpus_data["chunks"]]
        cls.retriever = HybridErgonomicsRetriever(cls.chunks)
        cls.gt_data = json.loads(DEFAULT_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    def test_ground_truth_dataset_integrity(self) -> None:
        questions = self.gt_data["questions"]
        self.assertGreaterEqual(len(questions), 10)
        for q in questions:
            self.assertIn("id", q)
            self.assertIn("question", q)
            self.assertIn("reference_answer", q)
            self.assertIn("expected_document_id", q)
            self.assertTrue(len(q["reference_answer"]) >= 40)
            self.assertIn("pure_llm_baseline", q)

    def test_hybrid_retriever_hit_rate_and_mrr(self) -> None:
        report = run_comparative_experiment(k=3)
        ret = report["retrieval_metrics"]
        self.assertGreaterEqual(ret["hit_rate_at_k"], 0.90)
        self.assertGreaterEqual(ret["mrr_at_k"], 0.85)
        self.assertEqual(ret["forbidden_leakage_rate_queries"], 0.0)

    def test_rag_outperforms_pure_llm_in_faithfulness_and_hallucination(self) -> None:
        report = run_comparative_experiment(k=3)
        comp = report["comparison_summary"]
        pure_llm = comp["pure_llm"]
        rag = comp["rag"]
        deltas = comp["deltas_rag_minus_llm"]

        # RAG deve apresentar alta fidelidade e zero citações inventadas
        self.assertEqual(rag["mean_faithfulness"], 1.0)
        self.assertEqual(rag["mean_hallucination_rate"], 0.0)
        self.assertEqual(rag["verified_citation_rate"], 1.0)

        # LLM puro apresenta alucinações normativas e citações não verificáveis
        self.assertGreater(pure_llm["mean_hallucination_rate"], 0.50)
        self.assertEqual(pure_llm["verified_citation_rate"], 0.0)
        self.assertGreater(deltas["faithfulness_gain"], 0.50)
        self.assertGreater(deltas["hallucination_reduction"], 0.50)

    def test_exact_quote_verification_blocks_fabricated_citations(self) -> None:
        valid_citation = {
            "document_id": "nr17",
            "section": "17.7 Trabalho com máquinas, equipamentos e ferramentas manuais",
            "page": 10,
            "exact_quote": "proporcionar corretos ângulos de visibilidade ao trabalhador",
        }
        fabricated_citation = {
            "document_id": "nr17",
            "section": "17.7 Trabalho com máquinas, equipamentos e ferramentas manuais",
            "page": 10,
            "exact_quote": "Todo monitor deve ficar obrigatoriamente a 72 cm exatos com filtro INMETRO.",
        }
        self.assertTrue(verify_exact_quote_in_corpus(valid_citation, self.chunks))
        self.assertFalse(verify_exact_quote_in_corpus(fabricated_citation, self.chunks))

    def test_claim_support_detection_rejects_invented_numbers(self) -> None:
        ref_texts = [
            "Os equipamentos devem permitir o ajuste da tela à iluminação do ambiente, protegendo-a contra reflexos."
        ]
        self.assertTrue(
            is_claim_supported_by_texts(
                "Os equipamentos devem permitir o ajuste da tela à iluminação do ambiente contra reflexos.",
                ref_texts,
            )
        )
        self.assertFalse(
            is_claim_supported_by_texts(
                "A tela deve ficar a 72 cm exatos com inclinação de 22 graus segundo o INMETRO.",
                ref_texts,
            )
        )

    def test_empty_retrieval_returns_safe_abstain_response(self) -> None:
        sample_q = self.gt_data["questions"][0]
        resp = synthesize_grounded_rag_response(sample_q, [])
        self.assertEqual(resp["citations"], [])
        self.assertEqual(resp["claims"], [])
        self.assertIn("Não há evidências suficientes", resp["answer"])

    def test_cli_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "report.json"
            exit_code = main(["--k", "3", "--out", str(out_file)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_file.exists())
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["experiment_id"], "EXP-01-LLM-VS-RAG")


if __name__ == "__main__":
    unittest.main()
