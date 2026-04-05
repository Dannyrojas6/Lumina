# Servant Assets

这份说明只描述当前仓库里真正保留的从者资源规则。

## 当前结构

当前从者资源分成两块：

- 公共资料：`assets/servants/_meta/`
- 本地从者资源：`local_data/servants/<className>/<slug>/`

`assets/servants/` 本身现在只保留公共资料，不再保存单个从者的运行资源。

## `assets/servants/_meta/`

当前长期保留的内容：

- `scripts/`：公共下载和整理脚本
- `indexes/`：公共索引 JSON
- `sources/`：少量公共原始导出

例如：

- `assets/servants/_meta/scripts/download_servant_assets.py`
- `assets/servants/_meta/indexes/servants_cn_en_min.json`

## 本地从者资源目录

单个从者资源固定放在：

`local_data/servants/<className>/<slug>/`

目录当前分为三块：

- `_meta/`：该从者自己的原始 JSON 和下载清单
- `atlas/`：原始图片库，也是唯一原始图片来源
- `support/`：助战识别运行结果，例如 `support/generated/`

## `atlas/` 规则

原始图片只认 `atlas/`。

当前实际使用最直接的是：

- `atlas/faces/`

目录形式统一为：

- `ascension/<stage>.png`
- `costume/<costume_id>.png`

例如：

- `local_data/servants/berserker/morgan/atlas/faces/ascension/1.png`
- `local_data/servants/berserker/morgan/atlas/faces/costume/704030.png`

## `support/` 规则

`support/` 只保留运行结果和生成物，不放原始图。

例如：

- `local_data/servants/berserker/morgan/support/generated/reference_bank.npz`
- `local_data/servants/berserker/morgan/support/generated/reference_meta.json`

## 下载入口

公共下载脚本入口：

`.\\.venv\\Scripts\\python.exe .\\assets\\servants\\_meta\\scripts\\download_servant_assets.py`

当前项目运行时不会从 `assets/servants/<className>/<slug>/` 读取单个从者资源，只认 `local_data/servants/`。
