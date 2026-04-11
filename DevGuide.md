# Lumina DevGuide

这份文档只写当前真实开发状态、接手时必须知道的事实，以及接下来更值得投入的方向。
如果只是快速接手当前项目状态，先读 [PROJECT_HANDOFF.md](/D:/VSCodeRepository/Lumina/PROJECT_HANDOFF.md)，再回来看这份文档。

## 1. 当前定位

- Lumina 只服务 `FGO`
- 当前唯一主目标环境是 `MuMu + 1920x1080`
- 当前阶段目标不是通用化，而是把固定环境下的刷本主链路做稳

## 2. 当前状态一览

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 主菜单进本、编队确认、结算继续 | 已完成 | 主链路已能贯通 |
| 战斗内波次、敌人数量、回合数读取 | 已完成 | 当前依赖固定区域 `OCR` |
| 敌方 `HP` 读取 | 已完成 | 当前依赖固定区域 `OCR` |
| 前排三位 `NP` 读取 | 已完成 | 当前依赖固定区域 `OCR` |
| 前排九个技能位可用性判断 | 已完成 | 使用按钮主体和角落信息混合判断 |
| 助战头像识别 | 已优化 | 当前主链已切到遮挡排除后的双路向量核验 |
| 普通卡基础识别与选卡 | 已完成 | 已能识别归属和颜色，并做基础连携选卡 |
| 界面状态识别 | 进行中 | 仍依赖模板匹配，稳定性继续补 |
| 智能战斗 v1 | 进行中 | 已能按配置执行，但仍以保守策略为主 |
| 多设备适配 | 未开始 | 当前不做 |
| 后排、换人、御主技能智能判断 | 未开始 | 当前不做 |
| 普通卡完整智能化 | 未开始 | 当前不做 |

## 3. 当前主链路

当前流程已经覆盖：

1. 主菜单点击固定关卡入口
2. 助战筛选与目标助战查找
3. 编队确认并开始任务
4. 加载等待
5. 战斗内释放技能、进入攻击、选卡
6. 结算点击继续并进入下一轮

后续改动默认以“不破坏这条链路”为前提。

## 4. 当前识别现状

### 4.1 界面状态识别

- 仍然主要依赖模板匹配
- 这部分仍是当前项目里最脆弱的识别链之一
- 继续补稳时，优先考虑固定环境下的准确率，不优先考虑通用化

### 4.2 战斗文字读取

当前这些内容已经接入固定区域 `OCR`：

- 当前波次
- 敌方剩余数量
- 当前回合数
- 敌方三个位 `HP`
- 前排三位从者 `NP`

当前已经固定成单一 `PaddleOCR`，后续重点是继续补裁图和区域规则，不再并行维护多套 `OCR`。

### 4.3 技能可用性判断

当前技能判断不再是单一亮度判断。

现在的规则是：

- 先看技能按钮主体
- 主体明显正常时直接放行
- 主体偏暗或不稳时，再读左下和右下角的小区域
- 读到冷却信息时，判定为不能点
- 读不稳时，默认按不能点处理

这套逻辑目前只服务前排九个固定技能位。

### 4.4 助战头像识别

现在的主链路是：

- 固定助战头像区域
- 固定三个位候选
- 统一成 `240x260` 基准尺寸
- 先忽略固定遮挡区，再拆成两路：
  - 去遮挡后的整块人物区
  - 中心脸部区
- 用人物头像向量模型做双路核验
- 与目标从者正反例向量库比较
- 分数和分差同时满足条件时才点击

当前这套方法不是“只看像不像目标从者”，而是同时看两件事：

- 它像不像目标从者正例库
- 它像不像已知误判对象反例库

当前向量库分为两部分：

- 默认正例库：目标从者的 `atlas/faces` 原图
- 默认反例库：空
- 只有显式传 `--negative-atlas-class-peers` 或 `--negative-atlas-servants` 时，才会加入 `Atlas` 反例
- 如果显式传入截图样本，也可以额外混入真实截图裁块和误判样本

当前最终分数的思路不是单看目标相似度，而是：

- 正例相似度越高越好
- 反例相似度越高扣分越多
- 只有最终分数和第一名领先差值同时达线，才允许点击

所以当前助战识别的主要调优方式，不是只改阈值，还包括：

- 补目标从者正例
- 补高相似非目标反例
- 调整遮挡排除范围和脸部区域
- 重新生成向量库和默认阈值

当前这条链已经能直接接入本地检查和助战页持续观察脚本。

### 4.5 普通卡基础识别与选卡

当前普通卡不是完全固定顺序了。

现在已经接入：

- 五张普通卡归属识别
- 五张普通卡颜色识别
- 基础三卡连携优先
- `support attacker` 同从者三卡优先
- `command_card_priority` 从者顺序兜底

当前仍不属于“普通卡完整智能化”。

现在没有做的仍然包括：

- 敌方目标导向
- 伤害收益估算
- 收尾补刀策略
- 更复杂的回合级普通卡博弈

## 5. 当前资源结构

### 5.1 `assets/ui`

- 用于界面状态和通用按钮模板
- 当前界面状态识别仍高度依赖这里的资源

### 5.2 从者资源

当前资源分成两层：

- 公共资料：`assets/servants/_meta/`
- 本地从者资源：`local_data/servants/<className>/<slug>/`

本地从者目录当前分为三块：

- `_meta/`：该从者自己的原始 JSON 和下载清单
- `atlas/`：从 Atlas Academy 下载的原始图片库，也是唯一原始图片来源
- `support/`：助战识别运行结果，例如 `support/generated/`

助战识别原图现在直接从 `atlas/faces/` 读取，不再保留 `support/source/` 这种重复资源层。

## 6. 当前关键文件

- [core/runtime/workflow.py](/D:/VSCodeRepository/Lumina/core/runtime/workflow.py)：主流程状态机
- [core/perception/state_detector.py](/D:/VSCodeRepository/Lumina/core/perception/state_detector.py)：界面状态识别
- [core/perception/image_recognizer.py](/D:/VSCodeRepository/Lumina/core/perception/image_recognizer.py)：模板匹配基础能力
- [core/perception/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/perception/battle_ocr.py)：战斗 `OCR` 入口
- [core/battle_runtime/snapshot_reader.py](/D:/VSCodeRepository/Lumina/core/battle_runtime/snapshot_reader.py)：战斗快照
- [core/battle_runtime/planner.py](/D:/VSCodeRepository/Lumina/core/battle_runtime/planner.py)：智能战斗决策
- [core/support_recognition/verifier.py](/D:/VSCodeRepository/Lumina/core/support_recognition/verifier.py)：助战人物头像核验
- [core/support_recognition](/D:/VSCodeRepository/Lumina/core/support_recognition)：人物头像向量编码、遮挡裁图、向量库与调试辅助
- [core/shared/resource_catalog.py](/D:/VSCodeRepository/Lumina/core/shared/resource_catalog.py)：资源定位
- [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)：运行配置

## 7. 近期优先级

### 7.1 第一优先级：战斗内 `OCR` 与状态读取

当前最值得投入的是继续补稳战斗内读取，而不是再扩更多功能。

近期更值得做的事：

1. 继续校准敌方 `HP`
2. 继续补波次、敌人数、回合数、`NP` 的真实截图
3. 继续补技能角落小数字和提示字
4. 优先压低误读，不优先追求更复杂判断

### 7.2 第二优先级：界面状态识别

战斗内读取之后，更值得投入的是：

1. 补状态识别截图样本
2. 继续减少 `UNKNOWN` 和低置信度场景
3. 继续补稳模板资源和阈值

### 7.3 第三优先级：智能战斗继续补稳

当前智能战斗不是没有价值，而是优先级低于前两项。

当前更合适的方向是：

1. 继续稳住已有前排三人逻辑
2. 继续减少读取不稳导致的保守降级
3. 不急着扩到更复杂的战斗策略

## 8. 中期路线图

当前更合理的中期方向是：

1. 继续优化战斗 `OCR`
2. 继续优化状态识别
3. 在主链路更稳后，再继续补智能战斗策略
4. 助战识别只做必要维护，不作为当前主优先级

## 9. 当前明确不做的事

- 不做多设备适配
- 不做后排和换人逻辑
- 不做御主技能智能判断
- 不做普通卡完整智能化
- `tests/` 当前不是主验证入口；优先使用现有脚本、日志和调试截图验证
- 不改 [DevLog.md](/D:/VSCodeRepository/Lumina/DevLog.md) 和 [DevRecord.md](/D:/VSCodeRepository/Lumina/DevRecord.md)

## 10. 接手时的判断原则

- 优先稳主链路，不优先扩功能
- 优先修识别误判，不优先追求更复杂策略
- 先看当前真实资源和截图，再决定是否改代码
- 文档优先写当前真实状态，不写过期规划
