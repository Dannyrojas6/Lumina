# Lumina DevGuide

这份文档只保留接手时真正需要的信息。

## 1. 当前项目阶段

- 主环境：`MuMu + 1920x1080`
- 主目标：稳定跑通固定刷本链路
- 当前不是通用框架，也不是多设备方案
- 当前优先处理识别稳定性、战斗判断和配置可用性

## 2. 当前已跑通的主链路

当前主链路已经覆盖：

1. 主菜单点击固定关卡位
2. 助战职阶筛选、目标从者搜索、失败回退
3. 编队确认并开始任务
4. 加载提示等待
5. 进入战斗
6. 释放技能、进入攻击、选卡、结算
7. 循环刷本

这条链路是当前项目的核心，后续修改不要破坏它。

## 3. 当前战斗状态

### 3.1 宝具判断

- 已改成 `OCR` 读取三位从者 `NP`
- 规则是：`NP >= 100` 视为可放宝具
- 亮度判断方案已经废弃，不要再接回来

### 3.2 智能战斗 v1

已接入，但仍在校准：

- 只处理先发三人
- 读取：波次、敌人数、当前回合、三位从者 `NP`、九个技能可用性
- 根据 `smart_battle.frontline` 和 `wave_plan` 决定本回合技能
- 已加入本战已用技能记忆，避免重复点同一个技能
- 已接入当前回合数，避免同回合重复做智能判断

### 3.3 当前出卡规则

- 所有可释放宝具都会优先加入出卡计划
- 不足 3 张时再补普通卡
- 普通指令卡还没有做颜色、连携、助战优先等智能化

## 4. 当前识别情况

### 4.1 已接入固定区域的战斗信息

在 [core/coordinates.py](/D:/VSCodeRepository/Lumina/core/coordinates.py) 里，当前已经有这些区域：

- 战斗场次
- 敌方单位剩余数量
- 当前回合数
- 三位从者生命值
- 三位从者 `NP`
- 三位从者真名

### 4.2 识别现状

- `NP OCR` 当前可用
- 战斗文字类 OCR 还不够稳，后续仍需要继续校准或更换方案
- 技能可用性目前仍是图像特征近似判断，不是 OCR

### 4.3 调试入口

优先看这几类信息：

- `DEBUG` 日志
- [assets/screenshots/unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)
- `assets/screenshots/ocr`（如已开启 OCR 留图）
- [scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)

## 5. 关键文件

- [core/workflow.py](/D:/VSCodeRepository/Lumina/core/workflow.py)
  主流程状态机，最重要的文件
- [core/app.py](/D:/VSCodeRepository/Lumina/core/app.py)
  初始化各组件并启动主流程
- [core/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/battle_ocr.py)
  战斗 OCR 读取入口
- [core/battle_snapshot.py](/D:/VSCodeRepository/Lumina/core/battle_snapshot.py)
  波次、敌人数、当前回合、NP、技能可用性快照
- [core/smart_battle.py](/D:/VSCodeRepository/Lumina/core/smart_battle.py)
  智能战斗 v1 判断层
- [core/config.py](/D:/VSCodeRepository/Lumina/core/config.py)
  配置结构和解析
- [config/battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)
  实际运行配置
- [core/resources.py](/D:/VSCodeRepository/Lumina/core/resources.py)
  模板与从者资料入口

## 6. 当前明确限制

- 只按 `MuMu + 1920x1080` 调整
- 不做自动识别前排从者身份，前排由配置指定
- 不做后排、换人、替补上场逻辑
- 不做御主技能智能判断
- 不做普通卡智能选卡
- `tests/` 当前不维护

## 7. 当前最值得继续做的事

按优先级建议：

1. 继续校准战斗 OCR，尤其是战斗文字类区域
2. 提高技能可用性判断稳定度
3. 完成普通指令卡智能化
4. 再往后才是更完整的从者资料、御主技能智能化、结算记录

## 8. 不建议现在优先做的事

- 不要回到亮度版宝具判断
- 不要急着做多设备适配
- 不要急着做 GUI/TUI
- 不要急着做大重构
- 不要碰 `DevLog.md` 和 `DevRecord.md`
