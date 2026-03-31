import json
from pathlib import Path
from urllib.request import Request, urlopen

CN_URL = "https://api.atlasacademy.io/export/CN/basic_servant.json"
JP_EN_URL = "https://api.atlasacademy.io/export/JP/basic_servant_lang_en.json"
ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT_DIR / "indexes" / "servants_cn_en_min.json"
HEADERS = {"User-Agent": "Lumina/1.0"}


def fetch_json(url: str):
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    cn_data = fetch_json(CN_URL)
    jp_en_data = fetch_json(JP_EN_URL)

    # 用 collectionNo 做映射更稳
    jp_name_map = {}
    for row in jp_en_data:
        collection_no = row.get("collectionNo")
        if collection_no is not None:
            jp_name_map[collection_no] = row.get("name", "")

    result = []
    seen = set()

    for row in cn_data:
        servant_id = row.get("id")
        collection_no = row.get("collectionNo")
        name_cn = row.get("name", "")
        name_en = jp_name_map.get(collection_no, "")
        class_name = row.get("className", "")

        if servant_id is None or collection_no is None:
            continue

        key = (servant_id, collection_no)
        if key in seen:
            continue
        seen.add(key)

        result.append(
            {
                "name_cn": name_cn,
                "name_en": name_en,
                "id": servant_id,
                "collectionNo": collection_no,
                "className": class_name,
            }
        )

    result.sort(key=lambda x: x["collectionNo"])

    OUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"已输出 {len(result)} 条到 {OUT_FILE}")


if __name__ == "__main__":
    main()
