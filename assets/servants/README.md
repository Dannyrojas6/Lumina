# Servant Assets

当前 `assets/servants/` 分为两层：

- 全局资料区：`assets/servants/_meta/`
- 单个从者目录：`assets/servants/<className>/<slug>/`

全局资料区当前按用途拆分：

- `scripts/`：全局下载、整理、合并脚本
- `indexes/`：长期保留的公共索引 JSON
- `sources/`：预留给后续可能需要保留的全局原始导出

例如：

- `assets/servants/_meta/scripts/build_servants_cn_en_min.py`
- `assets/servants/_meta/scripts/download_servant_assets.py`
- `assets/servants/_meta/indexes/servants_cn_en_min.json`

公共下载脚本第一版按单个从者 ID 工作：

`uv run python assets/servants/_meta/scripts/download_servant_assets.py --id 704000`

单个从者目录当前分为三块：

- `_meta/`：该从者自己的原始 JSON 和下载清单
- `atlas/`：该从者从 Atlas Academy 直接下载的原始图片库，也是唯一原始图片来源
- `support/`：助战头像识别用的本地资源。这里只保留运行结果，例如 `support/generated/`

从者目录里的 `atlas/` 当前只收六类图片：

- `charaGraph`
- `faces`
- `narrowFigure`
- `charaFigure`
- `commands`
- `status`

每一类目录内固定两层：

- `ascension/<stage>.png`
- `costume/<costume_id>.png`

因此单张图片的路径形式统一为：

`assets/servants/<className>/<slug>/atlas/<type>/<group>/<key>.png`

例如 Morgan：

- `assets/servants/berserker/morgan/manifest.yaml`
- `assets/servants/berserker/morgan/_meta/704000.json`
- `assets/servants/berserker/morgan/_meta/download_manifest.json`
- `assets/servants/berserker/morgan/atlas/faces/ascension/1.png`
- `assets/servants/berserker/morgan/atlas/faces/costume/704030.png`
- `assets/servants/berserker/morgan/support/generated/reference_bank.npz`

`assets/servants/_meta/indexes/servants_cn_en_min.json` 是长期保留的公共从者索引，不是运行目录。

助战识别需要的原图也直接从 `atlas/faces/` 读取，不再额外复制一份到 `support/source/`。
