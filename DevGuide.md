# Lumina DevGuide

这份文档只写当前真实状态，方便继续接手，不写未来愿景。

## 1. 项目定位

- 主环境固定为 `MuMu + 1920x1080`
- 当前目标是把固定环境下的刷本主链路做稳
- 现在不是通用框架，也不是多设备方案

## 2. 当前主链路

当前流程已经覆盖：

1. 主菜单点击固定关卡入口
2. 助战筛选、搜索目标从者、失败回退
3. 编队确认并开始任务
4. 加载等待
5. 战斗内释放技能、进入攻击、选卡
6. 结算点击继续并进入下一轮

后续改动默认以“不破坏这条链路”为前提。

## 3. 战斗识别现状

### 3.1 已稳定接入

- 当前波次：固定区域 `OCR`
- 敌方剩余数量：固定区域 `OCR`
- 当前回合数：固定区域 `OCR`
- 前排三位从者 `NP`：固定区域 `OCR`
- 前排九个技能位可用性：主体区域 + 角落小区域混合判断

### 3.2 仍未使用

在 [core/coordinates.py](/D:/VSCodeRepository/Lumina/core/coordinates.py) 里：

- 从者生命值区域当前保留空位，不参与任何逻辑
- 从者真名区域当前保留空位，不参与任何逻辑
- 总波次区域已留坐标，但当前主判断仍只实际依赖当前波次

### 3.3 技能可用性现状

当前技能判断不再是单一亮度判断。

现在的规则是：

- 先看技能按钮主体
- 主体明显正常时，直接视为可点
- 主体偏暗或不稳时，再读左下和右下角的小区域
- 读到冷却信息时，视为不能点
- 读不稳时，默认按不能点处理

这套逻辑只服务前排九个固定技能位，不依赖每个从者单独做战斗技能模板。

## 4. 智能战斗 v1

当前智能战斗 v1：

- 只处理先发三人
- 前排身份由配置指定，不自动识别
- 读取当前波次、敌方剩余、当前回合、主打手 `NP`、九个技能位可用性
- 按 `smart_battle.frontline` 和 `wave_plan` 生成本回合动作
- 已记录本战已用技能，避免重复点同一技能
- 当前回合未变化时，不会重复执行同一轮智能判断

## 5. 资源结构

### 5.1 `assets/ui`

- 用于界面状态和常见按钮模板
- 当前状态识别仍然高度依赖这一层

### 5.2 `assets/servants`

- 当前只承担助战头像模板和从者资料
- `manifest.yaml` 主要描述技能序号、目标类型、效果标签
- 当前战斗内九个技能位的可用性判断，不依赖每个从者的战斗技能模板

## 6. 关键文件

- [core/workflow.py](/D:/VSCodeRepository/Lumina/core/workflow.py)
  主流程状态机
- [core/state_detector.py](/D:/VSCodeRepository/Lumina/core/state_detector.py)
  界面状态识别
- [core/image_recognizer.py](/D:/VSCodeRepository/Lumina/core/image_recognizer.py)
  模板匹配
- [core/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/battle_ocr.py)
  战斗 `OCR` 入口
- [core/battle_snapshot.py](/D:/VSCodeRepository/Lumina/core/battle_snapshot.py)
  战斗快照，负责波次、敌人、回合、`NP`、技能位判断
- [core/smart_battle.py](/D:/VSCodeRepository/Lumina/core/smart_battle.py)
  智能战斗决策
- [core/coordinates.py](/D:/VSCodeRepository/Lumina/core/coordinates.py)
  当前版本的固定坐标
- [scripts/coordinate_picker.py](/D:/VSCodeRepository/Lumina/scripts/coordinate_picker.py)
  坐标获取工具

## 7. 调试入口

- `DEBUG` 日志
- [assets/screenshots/unknown](/D:/VSCodeRepository/Lumina/assets/screenshots/unknown)
- [assets/screenshots/ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)
- [scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)

## 8. 当前明确限制

- 只按 `MuMu + 1920x1080` 调整
- 不做多设备适配
- 不做御主技能智能判断
- 不做后排和换人逻辑
- 不做普通卡完整智能化
- `tests/` 当前不维护
- 不要改 [DevLog.md](/D:/VSCodeRepository/Lumina/DevLog.md) 和 [DevRecord.md](/D:/VSCodeRepository/Lumina/DevRecord.md)

## 9. 下一步更值得投入的方向

按现在的代码形态，下一步更值得做的是：

1. 优化或重构模板匹配方法，先处理状态识别和助战识别的脆弱点
2. 继续补真实截图样本，校准战斗文字 `OCR`
3. 在主链路稳定后，再考虑更完整的战斗策略
