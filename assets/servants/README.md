# Servant Assets

当前 `assets/servants/` 分为两层：

- 全局资料区：`assets/servants/_meta/`
- 单个从者目录：`assets/servants/<servant_name>/`

全局资料区当前按用途拆分：

- `scripts/`：全局下载、整理、合并脚本
- `indexes/`：长期保留的公共索引 JSON
- `sources/`：预留给后续可能需要保留的全局原始导出

例如：

- `assets/servants/_meta/scripts/build_servants_cn_en_min.py`
- `assets/servants/_meta/indexes/servants_cn_en_min.json`

单个从者目录当前分为三块：

- `_meta/`：该从者自己的原始 JSON、本地下载脚本和下载清单
- `atlas/`：该从者从 Atlas Academy 直接下载的原始图片库
- `support/`：助战头像识别用的本地资源。`support/source/` 放真正进入助战识别链的原图，`support/generated/` 放生成结果

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

`assets/servants/<servant_name>/atlas/<type>/<group>/<key>.png`

例如 Morgan：

- `assets/servants/morgan/_meta/704000.json`
- `assets/servants/morgan/_meta/download_assets.py`
- `assets/servants/morgan/_meta/download_manifest.json`
- `assets/servants/morgan/atlas/faces/ascension/1.png`
- `assets/servants/morgan/atlas/faces/costume/704030.png`
- `assets/servants/morgan/support/source/f_7040000.png`
- `assets/servants/morgan/support/generated/reference_bank.npz`

`assets/servants/_meta/indexes/servants_cn_en_min.json` 是长期保留的公共从者索引，不是临时文件。

从者目录里的 `atlas/` 是原始图片库，后续如果识别链需要其中某一类图，应当从 `atlas/` 挑选到专门的业务目录里使用，不直接把 `atlas/` 当运行目录。
