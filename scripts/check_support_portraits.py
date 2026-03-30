"""离线校验助战头像识别结果。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import SupportRecognitionConfig
from core.resources import ResourceCatalog
from core.support_portrait_recognition import SupportPortraitMatcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="离线检查助战头像识别结果")
    parser.add_argument("--servant", required=True, help="从者目录名")
    parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="要检查的助战截图路径列表",
    )
    parser.add_argument(
        "--expected-slot",
        type=int,
        required=True,
        help="期望命中的助战位序号，取值 1/2/3",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resources = ResourceCatalog()
    matcher = SupportPortraitMatcher.from_servant(
        servant_name=args.servant,
        resources=resources,
        config=SupportRecognitionConfig(),
    )

    failures = 0
    for image_path in args.images:
        result = matcher.match_image(Path(image_path))
        actual_slot = result.slot_index if result is not None else None
        print(f"{Path(image_path).name}: slot={actual_slot}")
        if actual_slot != args.expected_slot:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
