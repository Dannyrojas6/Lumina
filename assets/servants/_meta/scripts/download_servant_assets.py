import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

TARGET_FIELDS = {
    "charaGraph": ["ascension", "costume"],
    "faces": ["ascension", "costume"],
    "narrowFigure": ["ascension", "costume"],
    "charaFigure": ["ascension", "costume"],
    "commands": ["ascension", "costume"],
    "status": ["ascension", "costume"],
}

SCRIPT_DIR = Path(__file__).resolve().parent
SERVANTS_ROOT = SCRIPT_DIR.parents[1]
INDEX_PATH = SERVANTS_ROOT / "_meta" / "indexes" / "servants_cn_en_min.json"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
ATLAS_SERVANT_URL = "https://api.atlasacademy.io/nice/CN/servant/{servant_id}"
DEFAULT_SUPPORT_RECOGNITION = {
    "source_dir": "atlas/faces",
    "source_glob": "**/*.png",
    "generated_dir": "support/generated",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按从者 ID 下载 Atlas 原始资料")
    parser.add_argument("--id", required=True, type=int, help="从者 ID，例如 704000")
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def fetch_json(url: str):
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise ValueError(f"无法从英文名生成 slug: {name}")
    return slug


def get_extra_assets(data: dict) -> dict:
    if "extraAssets" in data:
        return data["extraAssets"]
    return data


def build_save_path(servant_dir: Path, asset_type: str, group_type: str, key: str, url: str) -> Path:
    suffix = Path(urlparse(url).path).suffix or ".png"
    return servant_dir / "atlas" / asset_type / group_type / f"{key}{suffix}"


def collect_download_tasks(servant_dir: Path, extra_assets: dict) -> list[dict]:
    tasks: list[dict] = []
    for asset_type, groups in TARGET_FIELDS.items():
        asset_block = extra_assets.get(asset_type, {})
        if not isinstance(asset_block, dict):
            continue
        for group_type in groups:
            group_block = asset_block.get(group_type, {})
            if not isinstance(group_block, dict):
                continue
            for key, url in sorted(group_block.items(), key=lambda item: str(item[0])):
                if not isinstance(url, str) or not url.startswith("http"):
                    continue
                save_path = build_save_path(servant_dir, asset_type, group_type, str(key), url)
                tasks.append(
                    {
                        "asset_type": asset_type,
                        "group_type": group_type,
                        "key": str(key),
                        "url": url,
                        "save_path": str(save_path.relative_to(servant_dir)),
                    }
                )
    return tasks


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_index_entry(servant_id: int) -> dict:
    index_data = load_json(INDEX_PATH)
    for row in index_data:
        if int(row.get("id", -1)) == servant_id:
            return row
    raise FileNotFoundError(f"公共索引里未找到从者 ID: {servant_id}")


def ensure_manifest(servant_dir: Path, *, slug: str, display_name: str, class_name: str) -> None:
    manifest_path = servant_dir / "manifest.yaml"
    manifest_data = {}
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest_data = yaml.safe_load(file) or {}
        if not isinstance(manifest_data, dict):
            raise TypeError(f"manifest 不是合法 mapping: {manifest_path}")

    manifest_data.setdefault("servant_name", slug)
    manifest_data.setdefault("display_name", display_name)
    manifest_data.setdefault("class_name", class_name)
    manifest_data.setdefault("role", "")
    manifest_data.setdefault("support_template", "support/portrait.png")
    manifest_data.setdefault("support_recognition", DEFAULT_SUPPORT_RECOGNITION.copy())
    manifest_data.setdefault("skills", [])

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(manifest_data, file, allow_unicode=True, sort_keys=False)


def ensure_support_dirs(servant_dir: Path) -> None:
    (servant_dir / "support" / "source").mkdir(parents=True, exist_ok=True)
    (servant_dir / "support" / "generated").mkdir(parents=True, exist_ok=True)


def download_file(url: str, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    save_path.write_bytes(payload)


def main() -> int:
    args = parse_args()
    entry = load_index_entry(args.id)
    class_name = str(entry.get("className", "")).strip()
    display_name = str(entry.get("name_en", "")).strip()
    if not class_name or not display_name:
        raise ValueError(f"公共索引缺少 className 或 name_en: {entry}")

    slug = slugify(display_name)
    servant_dir = SERVANTS_ROOT / class_name / slug
    raw_json_path = servant_dir / "_meta" / f"{args.id}.json"
    manifest_path = servant_dir / "_meta" / "download_manifest.json"

    data = fetch_json(ATLAS_SERVANT_URL.format(servant_id=args.id))
    extra_assets = get_extra_assets(data)
    tasks = collect_download_tasks(servant_dir, extra_assets)

    ensure_manifest(servant_dir, slug=slug, display_name=display_name, class_name=class_name)
    ensure_support_dirs(servant_dir)
    save_json(raw_json_path, data)
    save_json(manifest_path, tasks)

    print(f"从者目录: {servant_dir}")
    print(f"共找到 {len(tasks)} 个下载任务")

    success = 0
    failed = 0
    for task in tasks:
        save_path = servant_dir / task["save_path"]
        try:
            download_file(task["url"], save_path)
            print(f"下载成功: {save_path}")
            success += 1
        except Exception as exc:
            print(f"下载失败: {task['url']} -> {exc}")
            failed += 1

    print("\n========== 下载完成 ==========")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
