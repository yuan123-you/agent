import json
import subprocess
import sys

from eval.scripts.calibrate_answerability import (
    HIGH_SCORES,
    MARGINS,
    MIN_SCORES,
    evaluate_thresholds,
    sweep,
)


def test_metrics_are_reproducible():
    rows = [
        {"answerable": True, "top1": .80, "top2": .20},
        {"answerable": True, "top1": .70, "top2": .69},
        {"answerable": False, "top1": .30, "top2": .29},
        {"answerable": False, "top1": .50, "top2": .49},
    ]
    metrics = evaluate_thresholds(
        rows, min_score=.45, high_score=.65, min_margin=.05
    )
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["reject_rate"] == .5


def test_sweep_only_returns_a_report(tmp_path):
    report = sweep([
        {"answerable": True, "top1": .8, "top2": .2},
        {"answerable": False, "top1": .3, "top2": .29},
    ])
    assert {"min_score", "high_score", "min_margin", "f1"} <= report["best"].keys()
    assert len(report["candidates"]) == len(MIN_SCORES) * len(HIGH_SCORES) * len(MARGINS)
    assert list(tmp_path.iterdir()) == []


def test_sweep_uses_required_ordering():
    report = sweep([
        {"answerable": True, "top1": .8, "top2": .2},
        {"answerable": False, "top1": .3, "top2": .29},
    ])
    expected = sorted(
        report["candidates"],
        key=lambda candidate: (
            -candidate["f1"],
            -candidate["precision"],
            candidate["reject_rate"],
            candidate["min_score"],
            candidate["high_score"],
            candidate["min_margin"],
        ),
    )
    assert report["candidates"] == expected
    assert report["best"] == expected[0]


def test_cli_writes_only_explicit_output(tmp_path):
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "chosen" / "report.json"
    input_path.write_text(
        '\n'.join([
            json.dumps({"query": "policy", "answerable": True, "top1": .8, "top2": .2}),
            json.dumps({"query": "unrelated", "answerable": False, "top1": .3, "top2": .29}),
        ]),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "eval/scripts/calibrate_answerability.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )

    assert json.loads(output_path.read_text(encoding="utf-8"))["best"]
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "chosen",
        "chosen/report.json",
        "input.jsonl",
    ]
