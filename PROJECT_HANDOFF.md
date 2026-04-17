# Lumina Project Handoff

这份文档给新 Codex 线程、其他 AI 和人类接手使用。
目标不是讲完整细节，而是让接手者在 5 分钟内知道：当前项目做到哪了、先看什么、哪些地方最容易看错。

## 项目一句话状态

- Lumina 是一个面向 `FGO` 的固定环境自动刷本项目。
- 当前唯一主目标环境是可通过 `ADB` 控制的 `1920x1080` 模拟器或安卓设备。
- 当前最重要的事不是扩功能，而是继续补稳主链路，尤其是战斗 `OCR` 和界面状态识别。

## 当前已经稳定到什么程度

### 主链路

当前主链已经贯通：

1. 主菜单进本
2. 助战筛选与目标助战查找
3. 编队确认
4. 加载等待
5. 战斗内释放技能、进入攻击、选卡
6. 结算继续并进入下一轮

### 已完成能力

- `ADB` 连接模拟器、截图、点击
- 页面状态模板识别
- 助战头像识别主链
- 战斗内波次、敌人数、回合数读取
- 前排三位 `NP` 读取
- 敌方三个位 `HP` 读取
- 前排九个技能位可用性判断
- 五张普通卡的归属识别、颜色识别和基础连携选卡
- 可选的 `custom_sequence` 战斗链路：按 `wave + turn` 执行录入动作，并按录入时机释放宝具
- 普通卡默认只在低置信度或显式调试时留证，低置信度时立即停止等待人工确认
- 启动前固定环境与关键资源自检
- `tests/replay/` 静态回放回归

### 半成品能力

- 页面状态识别仍然高度依赖模板匹配
- 助战识别仍依赖固定布局和纵向扫描

### 明确未做

- 多设备适配
- 后排、换人、替补逻辑
- 御主技能智能判断
- 普通卡完整智能化

## 新线程先读什么

### 第一步

先读 [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md)。
它只负责执行约束，不负责解释项目现状。

### 第二步

读当前这份 [PROJECT_HANDOFF.md](/D:/VSCodeRepository/Lumina/PROJECT_HANDOFF.md)。
这份文档是当前项目状态总入口。

### 第三步

按需要继续读：

- [README.md](/D:/VSCodeRepository/Lumina/README.md)：真实结构、入口、资源布局
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)：开发背景、现状和近期优先级
- [docs/current-project-implementation-audit.md](/D:/VSCodeRepository/Lumina/docs/current-project-implementation-audit.md)：细节审查
- [docs/ocr_np_validation.md](/D:/VSCodeRepository/Lumina/docs/ocr_np_validation.md)：战斗 `OCR` 专项说明
- [assets/servants/README.md](/D:/VSCodeRepository/Lumina/assets/servants/README.md)：从者资源与下载脚本
- [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml)：当前默认运行策略

## 当前关键设计

### 固定环境优先

- 项目当前不追求通用化
- 坐标、裁图、模板和资源都围绕 `1920x1080`
- [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml) 不再提供设备档位切换；项目直接固定为 `1920x1080`
- `device.serial` 留空时，只允许当前 `adb` 只有一台可用设备
- `device.connect_targets` 只用于启动前自动 `adb connect`
- 启动阶段若 `adb` 状态不对，会先执行一次 `kill-server -> start-server -> adb connect`
- 运行中若 `adb` 断开，会直接停止，不做自动重连

### 运行时结构

- [core/runtime/app.py](/D:/VSCodeRepository/Lumina/core/runtime/app.py) 只负责装配和启动前自检
- [core/runtime/engine.py](/D:/VSCodeRepository/Lumina/core/runtime/engine.py) 负责主循环和状态分派
- [core/runtime/session.py](/D:/VSCodeRepository/Lumina/core/runtime/session.py) 保存运行期状态
- [core/runtime/waiter.py](/D:/VSCodeRepository/Lumina/core/runtime/waiter.py) 统一页面级等待
- [core/runtime/handlers](/D:/VSCodeRepository/Lumina/core/runtime/handlers) 按页面拆分处理逻辑

### 助战识别

- 当前主链是固定三个位区域 + 遮挡排除 + 双路头像向量核验
- 原始图只来自本地从者目录里的 `atlas/faces/`
- 默认正例是目标从者自己的 `atlas/faces`
- 默认反例为空；只有显式传参时才加入 `Atlas` 反例

### 战斗 `OCR`

当前已经覆盖：

- 波次
- 敌人数
- 回合数
- 敌方三个位 `HP`
- 前排三位 `NP`

### 智能战斗当前真实边界

- `battle_mode=main` 下，当前主链只保留两条子模式：
  - `smart_battle.enabled=false`
  - `smart_battle.enabled=true`
- 这两条子模式当前都临时共用顶层 `skill_sequence` 作为开局动作
- `smart_battle.enabled=true` 时：
  - 宝具顺序优先助战打手
  - 普通卡先拿助战打手的卡，再补颜色连携
  - 一场战斗结算完成后直接停止，不继续下一场
- `smart_battle.wave_plan` 已废弃，配置中不再允许出现
- 当前还新增了一个独立可选链路：
  - `battle_mode=custom_sequence`
  - 按 `(wave, turn)` 执行录入好的从者技能、通用御主技能、敌方目标切换和宝具时机
  - 当前具体序列内容不再内联写在 `battle_config.yaml`，而是单独放在 `config/custom_sequences/*.yaml`
  - 进入攻击阶段后会优先使用普通卡归属识别；归属低置信度时再回退为只按颜色连携出卡

### 普通卡当前只做到什么程度

- 已能识别五张普通卡的归属和颜色
- 已能做基础三卡连携优先
- 已能结合 `support attacker` 和 `command_card_priority` 补卡
- 已有普通卡单图分析脚本和统一样本真值清单
- 每回合会保存普通卡识别截图和分析 JSON
- 任一张卡低置信度时会直接停止，不再继续自动出卡
- 还没有敌方目标导向、伤害估算和收尾补刀策略

## 当前最容易误判的点

- 不要把代码能力和默认配置混为一谈：
  - 代码里有 `smart_battle`
  - `battle_mode=main` 下是否启用它，要看 `smart_battle.enabled`
  - 代码里也有 `custom_sequence`
  - 当前示例配置写什么模式，要以 [battle_config.yaml](/D:/VSCodeRepository/Lumina/config/battle_config.yaml) 当前内容为准
- 不要把草稿文档当当前事实：
  - `docs/drafts/` 只看作草稿
- 不要把“能启动项目”误判成“助战链一定可跑”：
  - 助战识别依赖本地从者资源
- 不要把“配置里没写 `device`”当作还能继续兼容：
  - 现在固定环境已经是正式契约，不是口头约定
- 不要把 AI 执行环境里的 `uv run` 权限拦截误判成项目环境坏掉：
  - 受限环境里如果 `uv run` 被拦，先申请权限，不要改走别的 Python 启动链
- 不要把 `tests/` 当成唯一真相：
  - 当前主验证仍然依赖脚本、日志和调试截图

## 接手时的最小验证

### 不连模拟器时

先跑这几项：

```powershell
uv run python -m unittest discover -s tests -v
uv run .\scripts\ocr_region_check.py --help
uv run .\scripts\watch_support_match.py --help
uv run .\scripts\build_reference_bank.py --help
uv run .\scripts\analyze_command_cards.py --help
```

这组通过，说明：

- 当前 Python 依赖能起
- 主要脚本入口还活着
- 文档里写的主入口没有明显失效
- 回放回归样本还能按当前规则通过

### 连模拟器时

再跑：

```powershell
uv run .\main.py
```

至少要确认：

- 能连上 `ADB`
- 能读到当前分辨率
- 启动前若未直接发现设备，会先尝试一次自动恢复
- 主流程能进入页面识别
- 日志不会在启动阶段直接断掉

## 最近优先级

当前更值得做的事只有这几类：

1. 继续补稳战斗 `OCR`
2. 继续补稳界面状态识别，减少 `UNKNOWN`
3. 继续补稳当前智能战斗的保守逻辑，不急着扩大战略复杂度
4. 助战识别只做必要维护，不作为当前第一优先级

## 维护规则

### 必须同步改这份文档的情况

- 主链路新增或删除能力
- 模块目录结构变化
- 默认运行策略明显变化
- 助战识别主链变化
- 战斗 `OCR` 覆盖范围变化
- 最小验证入口变化
- 当前优先级变化

### 通常只改原文档、不必改这份文档的情况

- 某个专项参数说明更细
- 某个脚本帮助信息变化
- 某类资源目录里的细节说明变化

### 各文档分工

- [AGENTS.md](/D:/VSCodeRepository/Lumina/AGENTS.md)：执行约束
- [PROJECT_HANDOFF.md](/D:/VSCodeRepository/Lumina/PROJECT_HANDOFF.md)：当前项目状态总入口
- [README.md](/D:/VSCodeRepository/Lumina/README.md)：真实结构、入口、资源布局
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md)：开发背景和优先级
- [docs/current-project-implementation-audit.md](/D:/VSCodeRepository/Lumina/docs/current-project-implementation-audit.md)：细节审查
- [docs/ocr_np_validation.md](/D:/VSCodeRepository/Lumina/docs/ocr_np_validation.md)：专项说明
