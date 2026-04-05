import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
META_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
SERVANTS_ROOT = PROJECT_ROOT / "local_data" / "servants"
INDEX_PATH = META_ROOT / "indexes" / "servants_cn_en_min.json"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
ATLAS_SERVANT_URL = "https://api.atlasacademy.io/nice/CN/servant/{servant_id}"
DEFAULT_SUPPORT_RECOGNITION = {
    "source_dir": "atlas/faces",
    "source_glob": "**/*.png",
    "generated_dir": "support/generated",
    "reference_bank": "support/generated/reference_bank.npz",
    "reference_meta": "support/generated/reference_meta.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Atlas assets for selected servants")
    parser.add_argument(
        "--id",
        dest="servant_ids",
        action="append",
        type=int,
        help="Single servant ID. Can be used multiple times.",
    )
    parser.add_argument(
        "--class-name",
        help="Download all servants in a class, for example berserker.",
    )
    parser.add_argument(
        "--rarity",
        type=int,
        choices=range(0, 6),
        metavar="RARITY",
        help="Filter by rarity. Can be combined with --class-name or --all.",
    )
    parser.add_argument(
        "--all",
        dest="include_all",
        action="store_true",
        help="Download all servants in the shared index.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Redownload files even if they already exist.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Maximum parallel download threads. Default is 8.",
    )
    args = parser.parse_args()
    if not args.servant_ids and not args.class_name and not args.include_all:
        parser.error("one of --id, --class-name, or --all is required")
    if args.max_workers < 1:
        parser.error("--max-workers must be at least 1")
    return args


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_index() -> list[dict]:
    index_data = load_json(INDEX_PATH)
    if not isinstance(index_data, list):
        raise TypeError(f"shared index is not a list: {INDEX_PATH}")
    return index_data


def fetch_json(url: str):
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def normalize_display_name(name: str) -> str:
    match = re.fullmatch(r"\s*(.+?)\s*\((.+)\)\s*", name)
    if not match:
        return name.strip()
    base_name = match.group(1).strip()
    suffix = match.group(2).strip()
    normalized_suffix = re.sub(r"[^a-z0-9]+", "", suffix.lower())
    if "alter" in normalized_suffix:
        return f"{base_name} ({suffix})"
    if len(suffix) >= 10 or " " in suffix or "-" in suffix:
        return base_name
    return f"{base_name} ({suffix})"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise ValueError(f"cannot build slug from name: {name}")
    return slug


def build_slug_counts(index_data: list[dict]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for row in index_data:
        class_name = str(row.get("className", "")).strip().lower()
        display_name = str(row.get("name_en", "")).strip()
        if not class_name or not display_name:
            continue
        slug = slugify(normalize_display_name(display_name))
        key = (class_name, slug)
        counts[key] = counts.get(key, 0) + 1
    return counts


def resolve_servant_slug(entry: dict, slug_counts: dict[tuple[str, str], int]) -> tuple[str, str]:
    display_name = str(entry.get("name_en", "")).strip()
    normalized_name = normalize_display_name(display_name)
    base_slug = slugify(normalized_name)
    class_name = str(entry.get("className", "")).strip().lower()
    if slug_counts.get((class_name, base_slug), 0) <= 1:
        return normalized_name, base_slug
    servant_id = int(entry["id"])
    return normalized_name, f"{base_slug}_{servant_id}"


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
                        "absolute_save_path": str(save_path),
                    }
                )
    return tasks


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def select_index_entries(
    index_data: list[dict],
    *,
    servant_ids: list[int] | None,
    class_name: str | None,
    rarity: int | None,
    include_all: bool,
) -> list[dict]:
    requested_ids = [int(item) for item in servant_ids or []]
    class_filter = (class_name or "").strip().lower()
    selected: list[dict] = []
    seen_ids: set[int] = set()
    missing_ids = set(requested_ids)

    for row in index_data:
        servant_id = int(row.get("id", -1))
        if servant_id <= 0 or servant_id in seen_ids:
            continue

        matches = False
        if servant_id in missing_ids:
            matches = True
            missing_ids.discard(servant_id)
        elif include_all:
            matches = True
        elif class_filter and str(row.get("className", "")).strip().lower() == class_filter:
            matches = True

        if not matches:
            continue

        if rarity is not None and int(row.get("rarity", -1)) != rarity:
            continue

        selected.append(row)
        seen_ids.add(servant_id)

    if missing_ids:
        missing_text = ", ".join(str(item) for item in sorted(missing_ids))
        raise FileNotFoundError(f"servant id not found in shared index: {missing_text}")

    if not selected:
        raise FileNotFoundError("no servants matched the selected filters")

    return sorted(selected, key=lambda row: int(row.get("id", 0)))


def ensure_manifest(servant_dir: Path, *, slug: str, display_name: str, class_name: str) -> None:
    manifest_path = servant_dir / "manifest.yaml"
    manifest_data = {}
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest_data = yaml.safe_load(file) or {}
        if not isinstance(manifest_data, dict):
            raise TypeError(f"manifest is not a mapping: {manifest_path}")

    manifest_data["servant_name"] = slug
    manifest_data["display_name"] = display_name
    manifest_data["class_name"] = class_name
    manifest_data["support_recognition"] = {
        **DEFAULT_SUPPORT_RECOGNITION,
        **dict(manifest_data.get("support_recognition") or {}),
    }
    manifest_data.setdefault("skills", [])
    manifest_data.pop("role", None)
    manifest_data.pop("support_template", None)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(manifest_data, file, allow_unicode=True, sort_keys=False)


def ensure_support_dirs(servant_dir: Path) -> None:
    (servant_dir / "support" / "generated").mkdir(parents=True, exist_ok=True)


def download_file(url: str, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    save_path.write_bytes(payload)


def _download_task(task: dict, *, overwrite: bool) -> tuple[str, str | None]:
    save_path = Path(task["absolute_save_path"])
    if save_path.exists() and not overwrite:
        return "skipped", None
    try:
        download_file(task["url"], save_path)
        return "success", None
    except Exception as exc:
        return "failed", str(exc)


def download_servant(
    entry: dict,
    *,
    overwrite: bool,
    slug_counts: dict[tuple[str, str], int],
    max_workers: int,
) -> tuple[int, int, int]:
    servant_id = int(entry["id"])
    class_name = str(entry.get("className", "")).strip()
    display_name = str(entry.get("name_en", "")).strip()
    if not class_name or not display_name:
        raise ValueError(f"shared index entry is missing className or name_en: {entry}")

    normalized_name, slug = resolve_servant_slug(entry, slug_counts)
    servant_dir = SERVANTS_ROOT / class_name / slug
    raw_json_path = servant_dir / "_meta" / f"{servant_id}.json"
    manifest_path = servant_dir / "_meta" / "download_manifest.json"

    data = fetch_json(ATLAS_SERVANT_URL.format(servant_id=servant_id))
    extra_assets = get_extra_assets(data)
    tasks = collect_download_tasks(servant_dir, extra_assets)

    ensure_manifest(servant_dir, slug=slug, display_name=display_name, class_name=class_name)
    ensure_support_dirs(servant_dir)
    save_json(raw_json_path, data)
    save_json(manifest_path, tasks)

    print(f"\n========== servant {servant_id} ==========")
    print(f"name: {display_name}")
    if normalized_name != display_name:
        print(f"normalized name: {normalized_name}")
    print(f"servant dir: {servant_dir}")
    print(f"download tasks: {len(tasks)}")
    print(f"max workers: {max_workers}")

    success = 0
    skipped = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_download_task, task, overwrite=overwrite): task for task in tasks
        }
        for future in as_completed(future_map):
            task = future_map[future]
            save_path = Path(task["absolute_save_path"])
            status, error_text = future.result()
            if status == "success":
                print(f"downloaded: {save_path}")
                success += 1
            elif status == "skipped":
                skipped += 1
            else:
                print(f"download failed: {task['url']} -> {error_text}")
                failed += 1

    print(f"success: {success}")
    print(f"skipped: {skipped}")
    print(f"failed: {failed}")
    return success, skipped, failed


def main() -> int:
    args = parse_args()
    index_data = load_index()
    slug_counts = build_slug_counts(index_data)
    selected_entries = select_index_entries(
        index_data,
        servant_ids=args.servant_ids,
        class_name=args.class_name,
        rarity=args.rarity,
        include_all=args.include_all,
    )

    print(f"selected servants: {len(selected_entries)}")

    total_success = 0
    total_skipped = 0
    total_failed = 0
    for entry in selected_entries:
        success, skipped, failed = download_servant(
            entry,
            overwrite=args.overwrite,
            slug_counts=slug_counts,
            max_workers=args.max_workers,
        )
        total_success += success
        total_skipped += skipped
        total_failed += failed

    print("\n========== done ==========")
    print(f"servants: {len(selected_entries)}")
    print(f"success: {total_success}")
    print(f"skipped: {total_skipped}")
    print(f"failed: {total_failed}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
