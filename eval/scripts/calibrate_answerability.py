"""Report-only threshold calibration for the production answerability rule."""

import argparse
import json
from itertools import product
from pathlib import Path

MIN_SCORES = [.30, .35, .40, .45, .50, .55]
HIGH_SCORES = [.55, .60, .65, .70, .75, .80]
MARGINS = [.00, .03, .05, .08, .10, .15]


def evaluate_thresholds(rows, *, min_score, high_score, min_margin):
    """Calculate binary-classification metrics using the production rule."""
    true_positive = false_positive = false_negative = rejected = 0

    for row in rows:
        top1 = row["top1"]
        predicted = top1 >= high_score or (
            top1 >= min_score and top1 - row["top2"] >= min_margin
        )
        actual = row["answerable"]
        true_positive += predicted and actual
        false_positive += predicted and not actual
        false_negative += not predicted and actual
        rejected += not predicted

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "reject_rate": rejected / len(rows) if rows else 0.0,
    }


def sweep(rows):
    """Evaluate and rank the finite threshold grid without writing files."""
    candidates = []
    for min_score, high_score, min_margin in product(MIN_SCORES, HIGH_SCORES, MARGINS):
        candidates.append({
            "min_score": min_score,
            "high_score": high_score,
            "min_margin": min_margin,
            **evaluate_thresholds(
                rows,
                min_score=min_score,
                high_score=high_score,
                min_margin=min_margin,
            ),
        })

    candidates.sort(key=lambda candidate: (
        -candidate["f1"],
        -candidate["precision"],
        candidate["reject_rate"],
        candidate["min_score"],
        candidate["high_score"],
        candidate["min_margin"],
    ))
    return {"best": candidates[0], "candidates": candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.input.open(encoding="utf-8") as source:
        rows = [json.loads(line) for line in source if line.strip()]
    report = sweep(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
