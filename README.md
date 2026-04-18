# Lumina

Lumina 是一个面向 `FGO` 的自动化脚本。当前只服务可通过 `ADB` 控制的 `1920x1080` 模拟器或安卓设备，目标是先把刷本主链路做稳，而不是做通用多端方案。

## 当前范围

- `ADB` 连接模拟器并持续截图
- 主菜单进本、助战筛选、编队确认、战斗、结算继续
- 助战按目标从者查找，找不到时回退默认位
- 战斗内读取当前波次、敌方剩余数量、当前回合数
- `OCR` 读取前排三位从者 `NP`
- `OCR` 读取敌方三个位的 `HP`
- 判断前排九个技能位当前是否可点
- `battle_mode=main` 下支持固定开局动作和保守版 `smart_battle`
- 支持按 `wave + turn` 执行自定义操作序列，并在攻击阶段按录入时机释放宝具
- 识别五张普通卡的归属和颜色，并按基础连携优先补满出卡
- 普通卡默认只在低置信度或显式调试时保存识别证据；任一张卡低置信度时直接停止等待人工确认

## 当前限制

- 不做多设备适配
- 不做后排、换人、替补上场
- 不做御主技能智能判断
- 自定义操作序列模式本轮不做换人
- 不做普通卡完整智能化，只保留基础连携和从者优先出卡
- `tests/` 当前不是主验证入口

## 环境要求

- `Python 3.12`
- 可用的 `adb`
- 可通过 `ADB` 控制的 `1920x1080` 模拟器或安卓设备
- Python 依赖使用 `uv` 管理
- `battle_config.yaml` 中的 `device.serial` 可留空；留空时只允许当前只有一台可用设备

依赖定义见 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml)。

## 安装

```bash
uv sync
```

## 运行

```bash
uv run .\main.py
```

Qt 主程序入口：

```bash
uv run python .\gui_main.py
```

## 配置入口

主配置文件在 [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。

常用字段：

- `loop_count`：刷本次数，`-1` 为无限循环
- `match_threshold`：界面模板识别阈值
- `log_level`：排查时建议用 `DEBUG`
- `device`：可选目标设备序列号、启动前自动连接地址
- `support`：助战职阶、目标从者、回退位、头像核验参数
- `ocr`：战斗文字读取参数
- `smart_battle`：主链路下的保守智能战斗开关、前排角色和出卡优先级
- `battle_mode`：选择当前主链路或自定义操作序列战斗
- `custom_sequence_battle`：选择当前要加载的自定义操作序列文件
- `skill_sequence`：`battle_mode=main` 下两种主链路子模式临时共用的开局技能顺序

`battle_mode` 当前规则：

- `main`：沿用当前主链路
  - `smart_battle.enabled=false`：首回合按 `skill_sequence` 释放开局技能，后续回合直接攻击
  - `smart_battle.enabled=true`：进入当前保守版 `smart_battle`，宝具和普通卡优先助战，且一场战斗结算后直接停止
- `custom_sequence`：按 `custom_sequence_battle.sequence` 指向的独立 YAML 执行录入动作
- `custom_sequence` 模式下，攻击阶段会优先使用普通卡归属识别；归属低置信度时再回退为只按颜色连携出卡
- `custom_sequence` 模式下，宝具只按当前回合录入的 `nobles` 释放；未录入时不自动放宝具
- 自定义操作序列文件统一放在 `config/custom_sequences/*.yaml`
- `smart_battle.wave_plan` 已废弃，配置中不再允许出现

`device` 当前规则：

- 项目直接固定为 `1920x1080`
- `device.serial` 留空时，启动阶段会在恢复后自动绑定唯一可用设备
- `device.connect_targets` 只用于启动前执行 `adb connect`，当前默认示例是 `127.0.0.1:7555`
- 启动阶段若找不到可用设备，会先执行一次 `kill-server -> start-server -> adb connect`
- 运行中若 `ADB` 断开，会直接停止主链，不做自动重连

## 识别方式

- 界面状态：模板匹配
- 战斗文字：固定区域 `PaddleOCR`
- 助战头像：固定三个位区域 + 遮挡排除 + 双路人物头像向量核验
- 技能可用性：按钮主体和角落信息的混合判断

## 从者资源

当前从者资源分成两块：

- 公共资料：`assets/servants/_meta/`
- 本地从者资源：`local_data/servants/<className>/<slug>/`

原始从者图片只放在本地从者目录里的 `atlas/`，`support/` 只保留运行和生成结果。
更细的目录说明和下载命令见 [assets/servants/README.md](/D:/VSCodeRepository/Lumina/assets/servants/README.md)。

## 目录入口

- [main.py](/D:/VSCodeRepository/Lumina/main.py)：程序入口
- [gui_main.py](/D:/VSCodeRepository/Lumina/gui_main.py)：Qt 主程序入口
- [core/gui](/D:/VSCodeRepository/Lumina/core/gui)：Qt GUI 主程序、运行页与工具页
- [core/perception](/D:/VSCodeRepository/Lumina/core/perception)：模板识别与战斗 OCR
- [core/support_recognition](/D:/VSCodeRepository/Lumina/core/support_recognition)：助战头像识别
- [core/shared](/D:/VSCodeRepository/Lumina/core/shared)：配置、资源、坐标与基础类型
- [core/battle_runtime](/D:/VSCodeRepository/Lumina/core/battle_runtime)：战斗判断、快照与动作执行
- [core/runtime](/D:/VSCodeRepository/Lumina/core/runtime)：主流程引擎、会话状态、等待层与状态处理器
- [core/device](/D:/VSCodeRepository/Lumina/core/device)：设备控制
- [config](/D:/VSCodeRepository/Lumina/config)：运行配置
- [custom_sequences](/D:/VSCodeRepository/Lumina/config/custom_sequences)：自定义操作序列文件
- [assets/ui](/D:/VSCodeRepository/Lumina/assets/ui)：界面模板
- [assets/servants](/D:/VSCodeRepository/Lumina/assets/servants)：从者公共资料、索引与下载脚本
- [assets/screenshots](/D:/VSCodeRepository/Lumina/assets/screenshots)：调试截图
- [scripts](/D:/VSCodeRepository/Lumina/scripts)：离线检查和资源处理脚本

## 调试入口

- [unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)：未识别界面截图
- [ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)：`OCR` 裁图与调试图
- [command_cards](/D:/VSCodeRepository/Lumina/assets/screenshots/command_cards)：普通卡识别截图与分析 JSON
- [tests/replay](/D:/VSCodeRepository/Lumina/tests/replay)：静态回放回归样本
- [ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)：`NP` 离线检查
- [ocr_region_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_region_check.py)：通用区域 `OCR` 检查
- [analyze_command_cards.py](/D:/VSCodeRepository/Lumina/scripts/analyze_command_cards.py)：普通卡单图分析
- [custom_sequence_recorder.py](/D:/VSCodeRepository/Lumina/scripts/custom_sequence_recorder.py)：自定义操作序列 GUI 录入器
- [gui_main.py](/D:/VSCodeRepository/Lumina/gui_main.py)：统一 Qt 主程序入口
- [check_portrait_verifier.py](/D:/VSCodeRepository/Lumina/scripts/check_portrait_verifier.py)：助战头像离线检查
- [build_reference_bank.py](/D:/VSCodeRepository/Lumina/scripts/build_reference_bank.py)：助战头像向量库生成
- [watch_support_match.py](/D:/VSCodeRepository/Lumina/scripts/watch_support_match.py)：助战页持续观察与命中留证

## 相关文档

- [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md)：执行约束
- [PROJECT_HANDOFF.md](/D:/VSCodeRepository/Lumina/PROJECT_HANDOFF.md)：当前项目状态总入口
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)：当前开发接手说明
- [assets/servants/README.md](/D:/VSCodeRepository/Lumina/assets/servants/README.md)：从者资源目录说明
