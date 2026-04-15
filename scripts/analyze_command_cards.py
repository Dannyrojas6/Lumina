"""普通指令卡离线分析脚本。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.command_card_recognition import (
    CommandCardRecognizer,
    format_prediction,
    write_masked_preview_image,
    write_part_preview_image,
    write_prediction_json,
)
from core.shared import ResourceCatalog
from core.support_recognition import load_rgb_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="分析单张普通指令卡截图")
    parser.add_argument("--image", required=True, help="战斗截图路径")
    parser.add_argument(
        "--frontline",
        nargs=3,
        required=True,
        metavar=("SLOT1", "SLOT2", "SLOT3"),
        help="前三名从者，例如 caster/zhuge_liang caster/merlin berserker/morgan",
    )
    parser.add_argument(
        "--support-attacker",
        required=False,
        default=None,
        help="助战打手，例如 berserker/morgan",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        default=None,
        help="JSON 输出目录，默认写到 assets/screenshots/command_cards/manual",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    resources = ResourceCatalog()
    recognizer = CommandCardRecognizer(resources)
    image_path = Path(args.image).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else Path(resources.command_card_debug_dir) / "manual"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    screen = load_rgb_image(image_path)
    prediction = recognizer.analyze_frontline(
        screen,
        list(args.frontline),
        support_attacker=args.support_attacker,
    )

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"{image_path.stem}_{timestamp}.json"
    masked_path = output_dir / f"{image_path.stem}_{timestamp}_masked.png"
    parts_path = output_dir / f"{image_path.stem}_{timestamp}_parts.png"
    write_masked_preview_image(masked_path, prediction, screen)
    write_part_preview_image(parts_path, prediction, screen)
    write_prediction_json(
        json_path,
        prediction,
        context={
            "image_path": str(image_path),
            "frontline": list(args.frontline),
            "support_attacker": args.support_attacker,
        },
        masked_preview_path=str(masked_path),
        parts_preview_path=str(parts_path),
    )

    print(format_prediction(prediction))
    print(f"masked={masked_path}")
    print(f"parts={parts_path}")
    print(f"json={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
