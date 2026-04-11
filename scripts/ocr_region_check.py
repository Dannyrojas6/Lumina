from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.shared.config_models import BattleOcrConfig
from core.shared.screen_coordinates import GameCoordinates
from core.perception.battle_ocr import BattleOcrReader


def _resolve_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    return resolved


def _parse_region(raw: str) -> tuple[int, int, int, int]:
    parts = [item.strip() for item in raw.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("region 必须是 x1,y1,x2,y2")
    try:
        x1, y1, x2, y2 = (int(item) for item in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("region 只能包含整数") from exc
    return (x1, y1, x2, y2)


@dataclass(frozen=True)
class RegionCase:
    label: str
    region: tuple[int, int, int, int]


def _named_group_cases(group: str) -> list[RegionCase]:
    if group == "enemy_hp":
        return [
            RegionCase(label=f"enemy_hp_{index}", region=region)
            for index, region in GameCoordinates.ENEMY_HP_REGIONS.items()
        ]
    if group == "np":
        return [
            RegionCase(label=f"np_{index}", region=region)
            for index, region in GameCoordinates.NP_TEXT_REGIONS.items()
        ]
    raise ValueError(f"不支持的 group: {group}")


def _manual_region_cases(
    regions: Iterable[tuple[int, int, int, int]],
    *,
    label_prefix: str,
) -> list[RegionCase]:
    return [
        RegionCase(label=f"{label_prefix}_{index}", region=region)
        for index, region in enumerate(regions, start=1)
    ]


def _load_screen_rgb(image_path: Path) -> np.ndarray:
    raw_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    if raw_bytes.size == 0:
        raise FileNotFoundError(f"无法读取截图：{image_path}")
    screen = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
    if screen is None:
        raise FileNotFoundError(f"无法读取截图：{image_path}")
    if screen.shape[1] != 1920 or screen.shape[0] != 1080:
        screen = cv2.resize(screen, (1920, 1080))
    return cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)


def _crop_region(screen: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = region
    return screen[y1:y2, x1:x2]


def _save_original_crop(
    crop: np.ndarray,
    *,
    debug_dir: Path,
    label: str,
    timestamp: str,
) -> Path:
    debug_dir.mkdir(parents=True, exist_ok=True)
    save_path = debug_dir / f"{timestamp}_{label}_raw.png"
    cv2.imwrite(str(save_path), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
    return save_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用当前主流程 OCR 检查任意截图区域。")
    parser.add_argument("--image", required=True, help="截图路径。")
    parser.add_argument(
        "--group",
        choices=["enemy_hp", "np"],
        help="使用内置区域组。",
    )
    parser.add_argument(
        "--region",
        action="append",
        type=_parse_region,
        help="手动指定区域，格式 x1,y1,x2,y2；可重复传入。",
    )
    parser.add_argument(
        "--label-prefix",
        default="manual",
        help="手动区域的标签前缀。",
    )
    parser.add_argument(
        "--mode",
        choices=["number", "text"],
        default="number",
        help="读取数字还是原文本。",
    )
    parser.add_argument(
        "--preset",
        choices=["default", "skill_corner"],
        default="default",
        help="OCR 预处理模式。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="格式化输出 JSON。",
    )
    parser.add_argument(
        "--dump-chunks",
        action="store_true",
        help="额外输出 OCR 返回的每个文本块详情。",
    )
    parser.add_argument(
        "--debug-dir",
        default=str(REPO_ROOT / "assets" / "screenshots" / "ocr_region_check"),
        help="原始裁图和处理后图片输出目录。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.group and not args.region:
        parser.error("--group 和 --region 至少要传一个")

    cases: list[RegionCase] = []
    if args.group:
        cases.extend(_named_group_cases(args.group))
    if args.region:
        cases.extend(_manual_region_cases(args.region, label_prefix=args.label_prefix))

    image_path = _resolve_path(args.image)
    screen_rgb = _load_screen_rgb(image_path)
    debug_dir = _resolve_path(args.debug_dir)
    reader = BattleOcrReader(
        config=BattleOcrConfig(save_ocr_crops=True),
        debug_dir=str(debug_dir),
    )
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    results: list[dict[str, object]] = []
    for case in cases:
        crop = _crop_region(screen_rgb, case.region)
        raw_path = _save_original_crop(
            crop,
            debug_dir=debug_dir,
            label=case.label,
            timestamp=timestamp,
        )
        if args.mode == "number" and case.label.startswith("enemy_hp_"):
            result = reader.read_enemy_hp_crop(crop, label=case.label)
            payload = {
                "text": result.raw_text,
                "value": result.hp_value,
                "confidence": result.confidence,
                "success": result.success,
            }
            if args.dump_chunks:
                chunks = reader.ocr_engine.read_chunks(
                    crop,
                    label=f"{case.label}_chunks",
                    preset=args.preset,
                )
                payload["chunks"] = [
                    {
                        "text": item.text,
                        "confidence": item.confidence,
                        "left_x": item.left_x,
                        "box": [list(point) for point in item.box],
                    }
                    for item in sorted(chunks, key=lambda item: item.left_x)
                ]
        elif args.mode == "number":
            result = reader.read_number(crop, label=case.label, preset=args.preset)
            payload = asdict(result)
            if args.dump_chunks:
                chunks = reader.ocr_engine.read_chunks(
                    crop,
                    label=f"{case.label}_chunks",
                    preset=args.preset,
                )
                payload["chunks"] = [
                    {
                        "text": item.text,
                        "confidence": item.confidence,
                        "left_x": item.left_x,
                        "box": [list(point) for point in item.box],
                    }
                    for item in chunks
                ]
        else:
            text, confidence = reader.read_text(crop, label=case.label, preset=args.preset)
            payload = {
                "text": text,
                "value": None,
                "confidence": confidence,
                "success": bool(text),
            }
        payload["label"] = case.label
        payload["region"] = list(case.region)
        payload["raw_crop_path"] = str(raw_path)
        payload["processed_crop_dir"] = str(debug_dir)
        results.append(payload)

    dump_kwargs = {"ensure_ascii": False}
    if args.pretty:
        dump_kwargs["indent"] = 2
    print(json.dumps(results, **dump_kwargs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


