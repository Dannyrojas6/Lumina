# Lumina

Lumina 是面向 `FGO` 的自动化脚本，当前只围绕 `MuMu + 1920x1080` 这一套固定环境做稳定化。

项目现在的重点不是通用化，也不是做完整工具链，而是先把固定环境下的主链路跑稳。

## 当前能做什么

- 通过 `ADB` 连接模拟器并持续截图
- 用模板识别主菜单、助战、编队确认、战斗可操作、选卡、结算等界面
- 按配置搜索助战，失败时回退到默认位置
- 读取战斗内的当前波次、敌方剩余数量、当前回合数
- 用 `OCR` 读取前排三位从者 `NP`
- 判断前排九个技能位当前能不能点
- 按 `smart_battle` 配置生成本回合技能动作
- 优先选择可释放宝具，不足时补普通卡
- 未识别状态时保存截图并尝试点击常见通用按钮

## 当前判断方式

### 界面状态

- 仍然是模板匹配
- 这部分对截图来源最敏感
- 当前项目里最值得继续优化的，也是这一层

### 战斗文字

- 当前波次、敌方剩余数量、当前回合数都已经接入固定区域 `OCR`
- 这部分已经比早期裁图更稳，但还在继续校准

### 技能可用性

- 不再只看整块亮度
- 现在是“按钮主体 + 角落冷却信息”的混合判断
- 主体明显正常时直接放行
- 主体偏暗或边界不稳时，继续读左下和右下的小区域
- 读到冷却信息就判定为不能点
- 读不稳时默认按不能点处理

### 智能战斗 v1

- 只处理先发三人
- 依赖：当前波次、敌方剩余、当前回合、主打手 `NP`、九个技能位可用性
- 已有保守降级：关键读取不稳时，宁可少放技能，也不误点

## 当前不做什么

- 不做多设备适配
- 不做后排、换人、替补上场
- 不做御主技能智能判断
- 不做普通卡颜色、连携、克制等完整智能化
- 不做按每个从者准备战斗技能模板

## 环境要求

- `Python 3.12`
- 可用的 `adb`
- `MuMu + 1920x1080`

依赖见 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml)。

## 安装

```bash
uv sync
```

## 运行

主程序：

```bash
uv run .\main.py
```

或：

```bash
python main.py
```

坐标工具：

```bash
python scripts/coordinate_picker.py
```

## 配置入口

运行配置在 [config/battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)。

最常用的字段：

- `loop_count`：刷本次数，`-1` 为无限循环
- `match_threshold`：模板匹配阈值
- `log_level`：建议排查时用 `DEBUG`
- `support`：助战职阶、目标从者、回退位置
- `ocr`：战斗 `OCR` 设置
- `smart_battle`：前排配置、波次动作计划、保守模式
- `skill_sequence`：关闭 `smart_battle` 时使用的固定技能顺序
- `save_debug_screenshots`：是否保留调试截图

## 目录说明

- [main.py](/D:/VSCodeRepository/Lumina/main.py)：程序入口
- [core](/D:/VSCodeRepository/Lumina/core)：主流程、识别、判断
- [config](/D:/VSCodeRepository/Lumina/config)：运行配置
- [assets/ui](/D:/VSCodeRepository/Lumina/assets/ui)：界面模板
- [assets/servants](/D:/VSCodeRepository/Lumina/assets/servants)：助战头像和从者资料
- [assets/screenshots](/D:/VSCodeRepository/Lumina/assets/screenshots)：调试截图
- [scripts/coordinate_picker.py](/D:/VSCodeRepository/Lumina/scripts/coordinate_picker.py)：坐标获取工具

## 调试入口

- `UNKNOWN` 状态排查：[assets/screenshots/unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)
- `OCR` 裁图排查：[assets/screenshots/ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)
- 离线 `NP` 检查脚本：[scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)

## 当前最值得继续做的事

1. 优化模板匹配这条识别链，尤其是状态识别和助战识别
2. 继续补战斗截图样本，稳住文字 `OCR`
3. 再往后才是普通卡智能化和更完整的战斗判断

## 接手说明

接手文档在 [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)。
