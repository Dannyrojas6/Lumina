# Servant Assets

这份说明只描述当前仓库里真正保留的从者资源规则。

## 当前结构

当前从者资源分成两块：

- 公共资料：`assets/servants/_meta/`
- 本地从者资源：`local_data/servants/<className>/<slug>/`

`assets/servants/` 本身现在只应保留公共资料；如果出现单个从者目录，说明是旧残留，不属于当前主链资源。

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

## `manifest.yaml`

下载脚本当前默认生成的 `manifest.yaml` 只保留仍在主链里使用的字段：

- `servant_name`
- `display_name`
- `class_name`
- `support_recognition`
- `skills`

下面这些旧字段不再生成：

- `role`
- `support_template`

原因很直接：当前运行链路已经不再读取它们。

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

## 目录命名规则

默认使用公共索引里的英文名生成 `slug`。

括号内容的处理规则当前只有一条特殊约束：

- 如果括号内容只是区分身份所必需的短标记，例如 `Alter`，保留。
- 如果括号内容是很长的附属称号，例如 `Zhuge Liang (Lord El-Melloi II)`，去掉括号部分后再生成目录名。

极少数同职阶同英文名的从者，为了避免批量下载时互相覆盖，会自动在目录名后补上 `id`。

因此当前会得到：

- `caster/zhuge_liang`
- `saber/altria_pendragon_alter`
- `moonCancer/kishinami_hakuno_2300700`

## 下载入口

公共下载脚本入口：

- 单个从者：`uv run .\assets\servants\_meta\scripts\download_servant_assets.py --id 704000`
- 整个职阶：`uv run .\assets\servants\_meta\scripts\download_servant_assets.py --class-name berserker`
- 指定职阶和星级：`uv run .\assets\servants\_meta\scripts\download_servant_assets.py --class-name berserker --rarity 5`
- 全部从者：`uv run .\assets\servants\_meta\scripts\download_servant_assets.py --all`

并行下载默认使用 `8` 个线程。需要调整时：

- `uv run .\assets\servants\_meta\scripts\download_servant_assets.py --class-name berserker --rarity 5 --max-workers 16`

默认会跳过已存在文件；如果要强制重下：

- `uv run .\assets\servants\_meta\scripts\download_servant_assets.py --class-name berserker --rarity 5 --overwrite`

当前项目运行时不会从 `assets/servants/<className>/<slug>/` 读取单个从者资源，只认 `local_data/servants/`。
