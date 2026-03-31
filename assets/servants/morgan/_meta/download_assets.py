import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


TARGET_FIELDS = {
    "charaGraph": ["ascension", "costume"],
    "faces": ["ascension", "costume"],
    "narrowFigure": ["ascension", "costume"],
    "charaFigure": ["ascension", "costume"],
    "commands": ["ascension", "costume"],
    "status": ["ascension", "costume"],
}


SCRIPT_DIR = Path(__file__).resolve().parent
SERVANT_DIR = SCRIPT_DIR.parent
INPUT_JSON = SCRIPT_DIR / "704000.json"
OUTPUT_DIR = SERVANT_DIR / "atlas"
MANIFEST_PATH = SCRIPT_DIR / "download_manifest.json"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_extra_assets(data: dict) -> dict:
    if "extraAssets" in data:
        return data["extraAssets"]
    return data


def build_save_path(asset_type: str, group_type: str, key: str, url: str) -> Path:
    suffix = Path(urlparse(url).path).suffix or ".png"
    return OUTPUT_DIR / asset_type / group_type / f"{key}{suffix}"


def collect_download_tasks(extra_assets: dict) -> list[dict]:
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
                save_path = build_save_path(asset_type, group_type, str(key), url)
                tasks.append(
                    {
                        "asset_type": asset_type,
                        "group_type": group_type,
                        "key": str(key),
                        "url": url,
                        "save_path": str(save_path.relative_to(SERVANT_DIR)),
                    }
                )
    return tasks


def save_manifest(tasks: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as file:
        json.dump(tasks, file, ensure_ascii=False, indent=2)


def download_file(url: str, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    save_path.write_bytes(payload)


def main() -> None:
    data = load_json(INPUT_JSON)
    extra_assets = get_extra_assets(data)
    tasks = collect_download_tasks(extra_assets)

    print(f"共找到 {len(tasks)} 个下载任务")
    for task in tasks:
        print(
            f"[{task['asset_type']}] {task['group_type']} {task['key']} -> {task['save_path']}"
        )

    save_manifest(tasks)
    print(f"\n已生成清单: {MANIFEST_PATH}")

    success = 0
    failed = 0
    for task in tasks:
        save_path = SERVANT_DIR / task["save_path"]
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


if __name__ == "__main__":
    main()
