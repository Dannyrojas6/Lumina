# Lumina

## 项目简介

Lumina 是一个面向 `FGO` 的自动化脚本项目。
当前只服务可通过 `ADB` 控制的 `1920x1080` 安卓模拟器，目标是先把固定环境下的刷本主链路做稳。

## 当前状态摘要

- 主链已经贯通：主菜单进本、助战筛选、编队确认、加载等待、战斗、结算页处理。
- 当前支持两条战斗链路：`battle_mode=main` 和 `battle_mode=custom_sequence`。
- `smart_battle.enabled=true` 当前仍是保守模式，且单场结算后会主动停止，不会继续刷满 `loop_count`。
- 普通卡已支持归属识别、颜色识别和基础连携补卡；低置信度时会直接停止等待人工确认。
- 当前不做多设备适配、后排与换人、御主技能智能判断、普通卡完整智能化。
- `tests/` 已是正式验证入口之一，但不是唯一真相；主链路验证仍要结合现有脚本、日志、调试截图和必要的实际运行。

## 环境要求

- `Python 3.12`
- 可用的 `adb`
- 只支持可通过 `ADB` 控制的 `1920x1080` 安卓模拟器
- 需支持 `ADB`，一般安卓模拟器都支持
- Python 依赖使用 `uv` 管理

依赖定义见 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml)。

## 安装与运行

安装依赖：

```bash
uv sync
```

主程序入口：

```bash
uv run .\main.py
```

Qt 主程序入口：

```bash
uv run python .\gui_main.py
```

## 配置快速入口

主配置文件在 [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。

最常用字段：

- `loop_count`：刷本次数，`-1` 为无限循环
- `battle_mode`：选择 `main` 或 `custom_sequence`
- `continue_battle`：结算后若出现连续出击界面，是否继续
- `support.servant`：目标助战从者
- `support.allow_fallback_pick`：找不到目标助战时，是否允许回退默认位一次
- `custom_sequence_battle.sequence`：当前加载的自定义操作序列文件
- `log_level`：运行日志级别
- `device.serial`：目标设备序列号；留空时只允许当前 `adb` 只有一台可用设备

运行页当前可直接修改 `loop_count`、`battle_mode`、`smart_battle.enabled`、`continue_battle` 和 `log_level`。

## 最小验证入口

不连设备时，先跑：

```powershell
uv run python -m unittest discover -s tests -v
uv run .\scripts\ocr_region_check.py --help
```

连设备时，再确认：

```powershell
uv run .\main.py
uv run python .\gui_main.py
```

## 更多文档

- [PROJECT_HANDOFF.md](/D:/VSCodeRepository/Lumina/PROJECT_HANDOFF.md)：当前真实状态、行为边界和最容易看错的地方
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)：接手背景、当前优先级和判断原则
- [docs/current-project-implementation-audit.md](/D:/VSCodeRepository/Lumina/docs/current-project-implementation-audit.md)：按模块拆开的详细实现审查
- [docs/ocr_np_validation.md](/D:/VSCodeRepository/Lumina/docs/ocr_np_validation.md)：战斗 `OCR` 专项说明
- [assets/servants/README.md](/D:/VSCodeRepository/Lumina/assets/servants/README.md)：从者资源目录与下载规则
