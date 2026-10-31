"""运行 AI 客服标准评测基准并产出完整评测报告。

用法：
  python eval/scripts/run_benchmark.py              # 默认离线全面评测（CI/本地均可秒级运行）
  python eval/scripts/run_benchmark.py --json       # 以 JSON 格式输出结果
  python eval/scripts/run_benchmark.py --category PRE_SALES  # 仅评测指定维度
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from eval.benchmark import CustomerServiceBenchmark, DEFAULT_BENCHMARK_PATH, RESULTS_DIR


def main():
    parser = argparse.ArgumentParser(description="AI Mall 电商客服标准评测基准")
    parser.add_argument("--mode", choices=["offline"], default="offline", help="评测模式（默认离线状态机与规则评测）")
    parser.add_argument("--dataset", default=str(DEFAULT_BENCHMARK_PATH), help="评测集路径")
    parser.add_argument("--category", default="ALL", help="指定评测维度（如 PRE_SALES, ORDER_FULFILLMENT）")
    parser.add_argument("--json", action="store_true", help="打印 JSON 结构体到控制台")
    parser.add_argument("--output-dir", default=str(RESULTS_DIR), help="输出目录")
    args = parser.parse_args()

    bench = CustomerServiceBenchmark(args.dataset)
    report = bench.evaluate_all(mode=args.mode)

    if args.category != "ALL":
        filtered_cases = [c for c in report.bad_cases if c["category"] == args.category]
        report.bad_cases = filtered_cases

    json_path, md_path = bench.save_reports(report, args.output_dir)

    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2))
    else:
        print("=================================================================")
        print("           AI Mall 电商客服标准评测基准 (AI CS Benchmark)         ")
        print("=================================================================")
        print(f" 评测时间    : {report.generated_at}")
        print(f" 运行模式    : {report.mode}")
        print(f" 评测用例总量 : {report.total_cases} 条")
        print(f" 综合评测得分 : {report.overall_score} / 100")
        print(f" 综合通过率   : {round(report.overall_pass_rate * 100, 1)}%")
        print(f" 意图识别准确 : {round(report.intent_accuracy * 100, 1)}%")
        print(f" 状态路由准确 : {round(report.route_accuracy * 100, 1)}%")
        print(f" 工具决策准确 : {round(report.tool_accuracy * 100, 1)}%")
        print(f" 参数提取准确 : {round(report.argument_accuracy * 100, 1)}%")
        print(f" 安全合规率   : {round(report.safety_compliance_rate * 100, 1)}%")
        print("-----------------------------------------------------------------")
        print(" 场景分项得分：")
        for sc in report.scorecards:
            print(f"   [{sc['category']}] {sc['category_name']:<14} : {sc['average_score']:>5} 分 | 通过率 {round(sc['pass_rate']*100, 1):>5}% ({sc['passed_cases']}/{sc['total_cases']})")
        print("-----------------------------------------------------------------")
        print(f" JSON 报告已保存至 : {json_path}")
        print(f" Markdown 报告保存至: {md_path}")
        print("=================================================================")


if __name__ == "__main__":
    main()
