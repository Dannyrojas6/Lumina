# Lumina

Lumina 是一个面向 `FGO` 的自动化脚本。当前只服务 `MuMu + 1920x1080` 这一套固定环境，目标是先把刷本主链路做稳，而不是做通用多端方案。

## 当前范围

- `ADB` 连接模拟器并持续截图
- 主菜单进本、助战筛选、编队确认、战斗、结算继续
- 助战按目标从者查找，找不到时回退默认位
- 战斗内读取当前波次、敌方剩余数量、当前回合数
- `OCR` 读取前排三位从者 `NP`
- `OCR` 读取敌方三个位的 `HP`
- 判断前排九个技能位当前是否可点
- 按 `smart_battle` 配置决定本回合技能动作

## 当前限制

- 不做多设备适配
- 不做后排、换人、替补上场
- 不做御主技能智能判断
- 不做普通卡完整智能化
- `tests/` 当前不是主验证入口

## 环境要求

- `Python 3.12`
- 可用的 `adb`
- `MuMu + 1920x1080`
- Python 依赖使用 `uv` 管理

依赖定义见 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml)。

## 安装

```bash
uv sync
```

## 运行

```bash
uv run .\main.py
```

## 配置入口

主配置文件在 [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。

常用字段：

- `loop_count`：刷本次数，`-1` 为无限循环
- `match_threshold`：界面模板识别阈值
- `log_level`：排查时建议用 `DEBUG`
- `support`：助战职阶、目标从者、回退位、头像核验参数
- `ocr`：战斗文字读取参数
- `smart_battle`：前排角色和各波次动作计划
- `skill_sequence`：关闭 `smart_battle` 时使用的固定技能顺序

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
- [core](/D:/VSCodeRepository/Lumina/core)：主流程、识别、判断
- [config](/D:/VSCodeRepository/Lumina/config)：运行配置
- [assets/ui](/D:/VSCodeRepository/Lumina/assets/ui)：界面模板
- [assets/servants](/D:/VSCodeRepository/Lumina/assets/servants)：从者公共资料、索引与下载脚本
- [assets/screenshots](/D:/VSCodeRepository/Lumina/assets/screenshots)：调试截图
- [scripts](/D:/VSCodeRepository/Lumina/scripts)：离线检查和资源处理脚本

## 调试入口

- [unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)：未识别界面截图
- [ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)：`OCR` 裁图与调试图
- [ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)：`NP` 离线检查
- [ocr_region_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_region_check.py)：通用区域 `OCR` 检查
- [check_portrait_verifier.py](/D:/VSCodeRepository/Lumina/scripts/check_portrait_verifier.py)：助战头像离线检查
- [build_reference_bank.py](/D:/VSCodeRepository/Lumina/scripts/build_reference_bank.py)：助战头像向量库生成
- [watch_support_match.py](/D:/VSCodeRepository/Lumina/scripts/watch_support_match.py)：助战页持续观察与命中留证

## 相关文档

- [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md)：执行约束
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)：当前开发接手说明
- [assets/servants/README.md](/D:/VSCodeRepository/Lumina/assets/servants/README.md)：从者资源目录说明
