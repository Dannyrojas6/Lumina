"""批量生成助战头像匹配模板。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.resources import ResourceCatalog
from core.support_portrait_recognition import SupportPortraitGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成助战头像匹配模板")
    parser.add_argument("--servant", help="指定单个从者 slug")
    parser.add_argument(
        "--all",
        action="store_true",
        help="遍历 assets/servants 下全部从者目录",
    )
    return parser.parse_args()


def iter_servants(resources: ResourceCatalog) -> list[str]:
    return resources.iter_servant_names()


def main() -> int:
    args = parse_args()
    resources = ResourceCatalog()
    generator = SupportPortraitGenerator(resources)

    if args.servant:
        servants = [args.servant]
    elif args.all:
        servants = iter_servants(resources)
    else:
        raise SystemExit("请提供 --servant 或 --all")

    for servant_name in servants:
        built = generator.build_for_servant(servant_name)
        print(f"{servant_name}: generated={len(built)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
