from datetime import datetime

from eval.scripts.run_eval import evaluate_offline


def test_baseline_generation_time_uses_beijing_offset():
    generated_at = evaluate_offline()["generated_at"]

    assert datetime.fromisoformat(generated_at).utcoffset().total_seconds() == 8 * 60 * 60
