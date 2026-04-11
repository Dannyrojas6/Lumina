"""离线校验人物头像向量核验结果。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.shared import ResourceCatalog, load_battle_config
from core.support_recognition import load_rgb_image
from core.support_recognition.verifier import SupportPortraitVerifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="离线检查人物头像向量核验结果")
    parser.add_argument("--servant", required=True, help="从者 slug")
    parser.add_argument(
        "--positive-images",
        nargs="+",
        default=[],
        help="必须命中目标从者的截图路径列表",
    )
    parser.add_argument(
        "--negative-images",
        nargs="+",
        default=[],
        help="必须判定为未命中的截图路径列表",
    )
    parser.add_argument(
        "--expected-slot",
        type=int,
        default=2,
        help="正例默认期望命中的助战位序号",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_battle_config(str(REPO_ROOT / "config" / "battle_config.yaml"))
    config.support.recognition.save_debug_mismatches = False
    verifier = SupportPortraitVerifier.from_servant(
        servant_name=args.servant,
        resources=ResourceCatalog(str(REPO_ROOT / "assets")),
        config=config.support.recognition,
    )

    failures = 0
    for image_path in args.positive_images:
        analysis = verifier.analyze(load_rgb_image(Path(image_path)))
        result = verifier.match_image(Path(image_path))
        failures += _print_result(
            label="POS",
            image_path=Path(image_path),
            analysis=analysis,
            result=result,
            expected_slot=args.expected_slot,
            expect_none=False,
        )

    for image_path in args.negative_images:
        analysis = verifier.analyze(load_rgb_image(Path(image_path)))
        result = verifier.match_image(Path(image_path))
        failures += _print_result(
            label="NEG",
            image_path=Path(image_path),
            analysis=analysis,
            result=result,
            expected_slot=None,
            expect_none=True,
        )

    return 1 if failures else 0


def _print_result(
    *,
    label: str,
    image_path: Path,
    analysis,
    result,
    expected_slot: int | None,
    expect_none: bool,
) -> int:
    slot_text = ", ".join(
        f"slot{item.slot_index}={item.score:.4f}" for item in sorted(analysis.slot_scores, key=lambda x: x.slot_index)
    )
    actual_slot = result.slot_index if result is not None else None
    score = None if result is None else round(result.score, 4)
    margin = None if result is None else round(result.margin, 4)
    print(
        f"{label} {image_path.name}: {slot_text}; best={None if analysis.best_slot is None else analysis.best_slot.slot_index}; "
        f"analysis_margin={analysis.margin:.4f}; result_slot={actual_slot}; score={score}; margin={margin}"
    )
    if expect_none:
        return 1 if actual_slot is not None else 0
    return 1 if actual_slot != expected_slot else 0


if __name__ == "__main__":
    raise SystemExit(main())
