# Lumina

Lumina 是一个基于 `adbutils` 与 `OpenCV` 的 FGO 自动化脚本。

当前项目的目标比较明确：先围绕 MuMu 模拟器打通并稳定一套可用的自动战斗流程，再考虑更广泛的设备适配和更复杂的功能。

## 功能特性

- 通过 ADB 连接 Android 设备或模拟器
- 基于模板匹配识别关键游戏界面
- 处理队伍确认、加载提示、战斗、选卡、结算等基础流程
- 执行简单的预设技能序列
- 在状态未知时尝试点击常见通用按钮
- 在识别失败时自动保存未知状态截图，便于排查

## 当前状态

项目仍处于实验阶段。

当前优先事项：

- 优先保证 MuMu 模拟器上的稳定运行
- 提高状态识别的可靠性
- 先完成简单可用的一整场战斗自动化

当前暂不优先：

- 多设备适配
- 完整 GUI / TUI 工具
- 复杂战斗策略或高智能逻辑

## 环境要求

- Python 3.12+
- 系统可用的 `adb`
- 已连接的 Android 设备或模拟器
- 当前主要测试目标为 MuMu 模拟器

## 安装

使用 `uv`：

```bash
uv sync
```

如果不使用 `uv`，也可以根据 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml) 手动安装依赖。

## 快速开始

1. 通过 ADB 连接模拟器或设备。
2. 根据需要修改 [config/battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。
3. 运行：

```bash
uv run .\main.py
```

如果不用 `uv`，也可以直接运行：

```bash
python main.py
```

## 配置说明

运行配置位于 [config/battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。

常用字段：

- `loop_count`：完整战斗完成次数，若只想打一场可设为 `1`
- `match_threshold`：模板匹配阈值
- `log_level`：排查识别问题时建议使用 `DEBUG`
- `skill_pre_skip_delay`：点击技能后到点击加速跳过前的等待时间
- `master_skill_open_delay`：点击御主技能栏后到点具体技能前的等待时间
- `skill_interval`：点击加速跳过后的额外等待时间
- `quest_slot`：主菜单关卡入口序号
- `support`：助战筛选、目标从者与默认回退位配置
- `ocr`：宝具 NP 的 OCR 识别设置
- `smart_battle`：智能战斗 v1 的前排、波次动作计划与保守降级模式
- `skill_sequence`：仅在 `smart_battle.enabled: false` 时生效的固定技能顺序
- `save_debug_screenshots`：是否在每次刷新时把截图保存到磁盘

从者长期资料放在 `assets/servants/<servant_name>/manifest.yaml`，助战头像仍使用 `assets/servants/<servant_name>/support/portrait.png`。

智能战斗 v1 当前只覆盖先发三人，按波次、敌人数、当前回合、主打手 NP 和技能可用性做判断。普通指令卡仍保持现有补位规则，所有可释放宝具都会优先加入出卡计划。

## 项目结构

- [main.py](/D:/VSCodeRepository/Lumina/main.py)：程序入口
- [core](/D:/VSCodeRepository/Lumina/core)：核心运行逻辑
- [config](/D:/VSCodeRepository/Lumina/config)：YAML 配置
- [assets/ui](/D:/VSCodeRepository/Lumina/assets/ui)：界面模板资源
- [assets/screenshots](/D:/VSCodeRepository/Lumina/assets/screenshots)：调试截图目录

## 调试建议

- 将 `log_level` 调成 `DEBUG`，查看更详细的识别日志
- 当流程落入 `UNKNOWN` 时，检查 [assets/screenshots/unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)
- NP 识别异常时，如已开启 `ocr.save_ocr_crops`，检查 `assets/screenshots/ocr`
- 若某个稳定界面突然识别不到，优先检查 [assets/ui](/D:/VSCodeRepository/Lumina/assets/ui) 中对应模板是否需要重截

## 开发说明

面向开发者或下一个 Agent 的接手文档已移动到 [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)。

