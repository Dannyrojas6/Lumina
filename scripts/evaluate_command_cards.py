"""普通指令卡样本评估脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.command_card_recognition import CommandCardRecognizer, load_command_card_samples
from core.command_card_recognition.metrics import compute_metrics
from core.shared import ResourceCatalog
from core.support_recognition import load_rgb_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="评估普通指令卡样本集")
    parser.add_argument(
        "--sample-path",
        default=None,
        help="样本清单路径，默认使用 tests/replay/command_card_samples.json",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="可选，输出 JSON 汇总文件路径",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    samples = load_command_card_samples(args.sample_path) if args.sample_path else load_command_card_samples()
    recognizer = CommandCardRecognizer(ResourceCatalog())
    results: list[tuple] = []
    for sample in samples:
        screen = load_rgb_image(sample.image_path)
        prediction = recognizer.analyze_frontline(
            screen,
            sample.frontline,
            support_attacker=sample.support_attacker,
        )
        results.append((sample, prediction))

    metrics = compute_metrics(results)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
