
# Intelligent Battle System Plan

## 1. Goal

本模块的目标不是构造一个“像人类一样思考”的通用 AI，而是实现一个**可解释、可调试、可扩展**的战斗决策系统。

系统需要做到：

- 根据当前战场状态动态决策，而不是执行固定脚本
- 围绕明确目标选择当前更优动作
- 在识别不完整或局势不确定时采取保守策略
- 能逐步从简单规则演进到评分/规划式决策

---

## 2. What Is "Intelligent Battle"

在本项目中，智能战斗定义为：

> 一个以战斗状态为输入、以战斗目标为导向、对候选动作进行评估与排序，并输出当前最优或次优动作的决策系统。

这里的“智能”不等于：

- 模拟人类思维本身
- 永远做出绝对正确判断
- 一开始就处理所有复杂战斗机制

这里的“智能”指的是：

- 能感知局势变化
- 能围绕目标调整动作
- 能在多个可执行动作中进行取舍
- 能在不确定时选择风险更低的方案

---

## 3. Non-Goals

当前阶段不追求：

- 完整复刻高难本全部机制
- 端到端大模型式黑盒决策
- 复杂博弈搜索
- 100% 人类级最优操作
- 不依赖规则的完全自学习系统

---

## 4. Core Design Principle

智能战斗必须拆成四层：

1. **状态感知**
   - 当前局势是什么

2. **目标定义**
   - 当前想达成什么

3. **动作评估**
   - 现在有哪些动作可选，各自收益/风险如何

4. **策略选择**
   - 最终执行哪个动作

这四层缺一不可。

---

## 5. System Architecture

```text
Screen / CV Recognition
        ↓
Battle State Builder
        ↓
Threat Analyzer / Resource Analyzer
        ↓
Action Generator
        ↓
Action Evaluator
        ↓
Policy / Decision Engine
        ↓
Action Executor
        ↓
Battle Loop
```

### 5.1 Recognition Layer

负责从画面中提取事实：

- 当前 wave / turn
- 敌方数量、HP、职阶、目标
- 我方从者、HP、NP、技能可用性
- 指令卡信息
- 宝具可用性
- 御主礼装技能
- Buff / Debuff / 危险信号

这一层只负责“看见”，不负责“判断”。

### 5.2 State Builder

将零散识别结果整理成统一结构化数据 `BattleState`。

### 5.3 Analyzer

分析当前局势，例如：

- 是否存在生存危机
- 当前能否收掉关键目标
- 当前是否应当留资源
- 敌方哪一个威胁最高
- 本回合宝具/平A是否足够

### 5.4 Action Generator

生成当前所有“合法可执行动作”。

例如：

- 普攻攻击某个目标
- 释放某技能给某从者
- 使用宝具
- 换人
- 使用御主礼装技能
- 跳过某些技能保留资源

### 5.5 Action Evaluator

对所有候选动作评分。

### 5.6 Policy / Decision Engine

按当前模式（刷本 / 高难 / 保守 / 激进）选出最终动作。

### 5.7 Executor

把决策转换成点击与操作。

------

## 6. Battle Modes

不同模式必须有不同目标，否则“正确判断”无从定义。

### 6.1 Farming Mode

目标：

- 优先稳定通关
- 尽量少回合
- 尽量少浪费技能
- 尽量保留下一面所需资源

适合日常刷本、材料本、活动周回。

### 6.2 Boss / Challenge Mode

目标：

- 优先生存
- 控制敌方宝具风险
- 尽量避免关键从者阵亡
- 在安全前提下输出最大化

### 6.3 Conservative Mode

目标：

- 降低误操作成本
- 识别不完整时也能继续运行
- 避免高风险动作

### 6.4 Aggressive Mode

目标：

- 倾向当前回合爆发
- 在容错允许时优先击杀/压血线
- 允许较高资源消耗换取更快节奏

------

## 7. BattleState Design

建议统一使用结构化对象，而不是散乱变量。

## 7.1 Example

```python
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EnemyState:
    slot: int
    hp: int
    max_hp: int
    servant_class: str
    np_charge: int
    is_alive: bool = True
    is_boss: bool = False
    is_high_threat: bool = False
    has_special_mechanic: bool = False


@dataclass
class SkillState:
    skill_id: str
    name: str
    is_ready: bool
    cooldown: int = 0


@dataclass
class AllyState:
    slot: int
    name: str
    hp: int
    max_hp: int
    np: int
    servant_class: str
    role: str  # dps / support / tank / utility
    is_alive: bool = True
    skills: List[SkillState] = field(default_factory=list)
    buffs: List[str] = field(default_factory=list)
    debuffs: List[str] = field(default_factory=list)


@dataclass
class MysticCodeState:
    is_available: bool
    skills_ready: List[bool]


@dataclass
class BattleState:
    wave: int
    turn: int
    enemies: List[EnemyState]
    allies: List[AllyState]
    mystic_code: MysticCodeState
    selected_enemy_slot: Optional[int] = None
    command_cards: List[str] = field(default_factory=list)
    stars: int = 0
    confidence: float = 1.0
```

------

## 8. Action Design

动作必须抽象成统一格式，方便生成、评分、执行。

## 8.1 Action Types

- `UseServantSkill`
- `UseMysticCodeSkill`
- `TargetEnemy`
- `UseNoblePhantasm`
- `SelectCommandCards`
- `OrderChange`
- `DoNothing`

## 8.2 Example

```python
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class BattleAction:
    action_type: str
    actor_slot: Optional[int] = None
    skill_index: Optional[int] = None
    target_slot: Optional[int] = None
    payload: Optional[Any] = None
```

例如：

- 给 1 号位从者释放 2 技能到 3 号位
- 选择 2 号敌人为目标
- 开 1 号位从者宝具
- 选择三张指令卡

------

## 9. Decision Flow

建议每回合按以下顺序运行：

1. 识别战场状态
2. 构建 `BattleState`
3. 检查识别置信度
4. 分析威胁
5. 分析资源
6. 生成候选动作
7. 对候选动作评分
8. 按策略模式选出最优动作
9. 执行动作
10. 回读战场状态确认结果
11. 进入下一轮决策

------

## 10. Threat Analysis

智能的第一步不是输出，而是判断危险。

### 10.1 Threat Signals

需要重点关注：

- 敌方 NP 即将满格或已可开宝具
- 敌人为 boss 或高伤害单位
- 我方核心输出低血量
- 当前回合可能无法收掉高威胁敌人
- 我方关键保命技能不可用
- 下一 wave 已知存在高压敌人

### 10.2 Threat Levels

建议分级：

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

例如：

- `CRITICAL`：敌方下回合大概率开宝具且我方无无敌/回避
- `HIGH`：敌方高威胁目标存活且本回合无法处理
- `MEDIUM`：存在压制风险但仍有处理余地
- `LOW`：当前局势安全

------

## 11. Resource Analysis

智能系统不能只看当前回合，还要看资源是否值得现在交。

资源包括：

- 我方技能
- 宝具
- NP
- 御主礼装技能
- 换人机会
- 关键 Buff
- 生存技能

### 11.1 Waste Rules

以下通常视为“资源浪费”：

- 已可击杀时继续叠过量增伤
- NP 已满还继续充能
- 小怪残血时交全队爆发技能
- 高威胁 wave 前提前交关键保命技能
- 单体技能给错误角色
- 把下一面核心资源消耗在当前低价值目标上

------

## 12. Action Evaluation

这是智能战斗的核心。

每个候选动作都要打分，而不是简单写死。

## 12.1 Score Formula

```text
score =
    damage_gain
  + survival_gain
  + np_gain
  + tempo_gain
  + next_wave_value
  - waste_cost
  - risk_cost
```

## 12.2 Meaning

- `damage_gain`
  - 当前动作提升了多少输出
- `survival_gain`
  - 当前动作对保命有多大帮助
- `np_gain`
  - 是否提升后续宝具循环能力
- `tempo_gain`
  - 是否有助于当前回合/本面更快结束
- `next_wave_value`
  - 是否有利于下一面
- `waste_cost`
  - 是否过度消耗资源
- `risk_cost`
  - 是否增加失败概率

## 12.3 Example Heuristics

### 开增伤技能

适合加分情况：

- 当前需要伤害才能击杀关键目标
- 当前回合准备开宝具
- 下一面不是更高价值爆发点

减分情况：

- 当前已稳杀
- 下一面 boss 更需要该技能
- 识别不确定，可能打错目标

### 开充能技能

适合加分情况：

- 当前可直接开宝具
- 充能后形成下一面的稳定循环
- 当前节奏要求高

减分情况：

- NP 已接近满且当前不急需
- 关键输出不在本面
- 当前开了也无法带来实质收益

### 开保命技能

适合加分情况：

- 敌方快开宝具
- 当前无法击杀高威胁目标
- 我方核心输出血量危险

减分情况：

- 当前无明显威胁
- 下一回合更危险
- 当前只是“轻微风险”

------

## 13. Policy Layer

策略层决定如何解释评分结果。

### 13.1 Rule First, Score Second

初期建议采用混合方案：

- 先用规则排除明显错误动作
- 再对剩余动作评分排序

这样最稳。

### 13.2 Example Rules

#### 生存优先规则

如果敌方宝具风险高，优先考虑：

- 无敌 / 回避
- 减充能 / 控场
- 击杀高威胁目标

#### 斩杀优先规则

如果当前回合能击杀关键敌人：

- 提高爆发类动作权重
- 降低保守动作权重

#### 资源保留规则

如果当前面低压：

- 降低大技能使用倾向
- 提高普攻收尾倾向

------

## 14. Fallback Strategy

没有 fallback 的系统不算可用。

### 14.1 When to Fallback

以下情况应进入降级策略：

- 识别置信度过低
- 关键状态缺失
- 无法确认目标
- 技能可用状态异常
- 候选动作为空
- 执行后结果与预期不符

### 14.2 Fallback Behavior

可以采用：

- 不使用高价值技能
- 只执行低风险动作
- 优先普通攻击
- 不进行复杂换人
- 不释放关键宝具链
- 等待下一次识别刷新

------

## 15. Explainability

智能系统必须可解释，否则无法调试。

每次决策建议输出日志：

```text
[Decision]
wave=2 turn=1 mode=farming
threat=MEDIUM
candidate_actions=8
best_action=UseServantSkill(actor=1, skill=2, target=1)
reason:
- damage_gain=35
- np_gain=20
- next_wave_value=10
- waste_cost=5
- risk_cost=3
final_score=57
```

这样后面你才能知道：

- 为什么它开了这个技能
- 为什么没保留到下一面
- 为什么它没开宝具
- 为什么它判定当前危险

------

## 16. Development Stages

不要一开始就追求完整智能，必须分阶段。

### Stage 1: Rule-Based MVP

目标：

- 能识别当前基本局势
- 能按简单规则做战斗决策
- 能处理最基本刷本场景

能力范围：

- 判断是否开宝具
- 判断是否放充能
- 判断是否开增伤
- 判断攻击哪个敌人

### Stage 2: Score-Based Decision

目标：

- 候选动作统一评分
- 支持“当前收益”和“后续收益”的平衡
- 能减少明显浪费技能行为

### Stage 3: Resource-Aware Strategy

目标：

- 能保留资源到下一面
- 能区分 boss wave 与普通 wave
- 能切换激进/保守策略

### Stage 4: Threat-Aware Survival Logic

目标：

- 能应对敌方宝具威胁
- 能优先保护核心输出
- 能在危险局势下改变节奏

### Stage 5: Advanced Tactical Logic

目标：

- 更精细的卡牌选择
- 更细致的换人逻辑
- 更复杂的特殊机制应对

------

## 17. MVP Scope Recommendation

当前最建议先做的是：

### 17.1 只做 Farming 智能

不要一开始就碰高难。

先聚焦：

- 3 回合附近的周回逻辑
- 单纯的技能/宝具/目标决策
- 不处理复杂特殊机制

### 17.2 MVP Must-Have

第一版至少做到：

- 读取 `BattleState`
- 判断本回合是否能开宝具
- 判断当前是否值得交充能
- 判断当前是否值得交增伤
- 判断当前攻击哪个敌人
- 输出一条决策日志
- 执行后进行结果确认

### 17.3 MVP Should-Not-Have Yet

第一版先不要做：

- 复杂高难机制
- 全盘未来搜索
- 复杂卡序优化
- 高度泛化的从者专属 AI
- 完全自动应对全部队伍组合

------

## 18. Suggested Module Split

```text
battle/
├─ state.py          # BattleState / AllyState / EnemyState
├─ actions.py        # BattleAction definitions
├─ analyzer.py       # threat / resource analysis
├─ generator.py      # candidate action generation
├─ evaluator.py      # scoring logic
├─ policy.py         # farming / challenge / conservative / aggressive
├─ executor.py       # click execution
├─ fallback.py       # downgrade logic
└─ controller.py     # battle loop orchestration
```

------

## 19. Controller Skeleton

```python
class BattleController:
    def run_turn(self):
        state = self.state_builder.build()

        if state.confidence < 0.75:
            action = self.fallback_policy.choose(state)
            self.executor.execute(action)
            return

        threat = self.analyzer.analyze_threat(state)
        resources = self.analyzer.analyze_resources(state)

        candidates = self.generator.generate(state, threat, resources)
        scored = self.evaluator.score_all(state, candidates, threat, resources)

        action = self.policy.choose_best(state, scored, mode="farming")
        self.executor.execute(action)
        self.logger.log_decision(state, threat, scored, action)
```

------

## 20. Key Engineering Principles

### 20.1 State First

先把状态结构定义清楚，再写决策。

### 20.2 Rule Before Model

先做规则和评分，不要急着上重型 AI。

### 20.3 Explain Every Decision

每个动作都必须能解释“为什么”。

### 20.4 Prefer Stability Over Cleverness

宁可保守，也不要做看起来聪明但不稳定的激进行为。

### 20.5 Make It Incremental

智能战斗必须逐阶段迭代，不可一步到位。

------

## 21. Final Definition

本项目中的智能战斗不是“模拟人类思考”，而是：

> 在当前可观察战场状态下，围绕既定目标，对候选动作进行收益、风险和资源消耗评估，并选择当前最合理动作的动态决策系统。

它的价值不在于“全知全能”，而在于：

- 比固定脚本更灵活
- 比纯手写流程更能适应局势变化
- 可解释
- 可调试
- 可逐步增强

------

## 22. Next Step

下一步实现顺序建议为：

1. 先定义 `BattleState`
2. 再定义 `BattleAction`
3. 写 `ThreatAnalyzer`
4. 写 `ActionGenerator`
5. 写 `ActionEvaluator`
6. 写 `FarmingPolicy`
7. 最后接入执行层和日志系统

第一版目标不要贪大，只做：

- 刷本
- 基础技能释放
- 宝具决策
- 目标选择
- 保守 fallback

等这一版稳定后，再考虑：

- 更复杂卡牌逻辑
- 特殊机制
- 高难战斗策略
- 从者个性化策略
