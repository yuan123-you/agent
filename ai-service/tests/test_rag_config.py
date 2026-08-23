import pytest
from pydantic import ValidationError
from app.config import Settings


def test_t10_defaults():
    s = Settings(_env_file=None)
    assert (s.rag_vector_recall_k, s.rag_bm25_recall_k) == (20, 20)
    assert (s.rag_rrf_k, s.rag_rrf_top_k, s.rag_final_top_k) == (60, 10, 4)
    assert (s.rag_answer_min_score, s.rag_answer_high_confidence_score) == (.45, .65)
    assert s.rag_answer_min_margin == .05
    assert s.rag_reranker_enabled is False
    assert s.rag_reranker_model == "Qwen/Qwen3-Reranker-4B"


@pytest.mark.parametrize("values", [
    {"rag_final_top_k": 11, "rag_rrf_top_k": 10},
    {"rag_rrf_top_k": 21},
    {"rag_answer_min_score": -.01},
    {"rag_answer_high_confidence_score": 1.01},
    {"rag_vector_score_scale": 0},
    {"rag_reranker_timeout_s": 0},
])
def test_invalid_settings_fail(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_rrf_top_k_stays_capped_when_both_recall_windows_are_raised():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            rag_vector_recall_k=40,
            rag_bm25_recall_k=40,
            rag_rrf_top_k=21,
        )
