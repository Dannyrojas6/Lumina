# Command Card Chain Design

**目标**

在现有普通指令卡归属识别的基础上，补上色卡类型识别与连携组合判断，让智能战斗可以按固定优先级从五张普通卡中选出更合理的三张。

**范围**

- 识别五张普通卡的颜色类型：`buster` / `arts` / `quick`
- 基于每张卡的 `owner` 和 `color` 枚举全部 `5 选 3` 组合
- 按固定优先级选择一组最优普通卡组合
- 将新规则接入当前 `workflow` 的统一出卡计划入口

**不在本轮范围**

- 不做暴击星、伤害预估、克制关系打分
- 不做更复杂的混合权重排序
- 不做 OCR 主导的色卡识别
- 不处理宝具卡和普通卡的额外联动规则

## 颜色识别

**主方案**

颜色识别优先走固定区域取色，不走 OCR 主判定。

原因：

- 当前唯一主目标环境固定：`MuMu + 1920x1080`
- 色卡下半区域颜色块稳定，远比小字 OCR 更适合固定环境识别
- 颜色识别速度更快，调试成本更低

**备用方案**

OCR 只作为后备验证手段，不在第一版主链路启用。

**识别思路**

- 每张普通卡使用固定矩形区域裁出下半部颜色区
- 对区域做简单裁边，避开边框、高光和按钮装饰
- 统计区域主色分布
- 通过阈值映射到 `buster` / `arts` / `quick`

## 连携组合类型

每组三张卡只归为以下一种类型：

- `support_attacker_same_servant`
- `buster_3`
- `arts_3`
- `tri_color`
- `other_same_servant`
- `quick_3`
- `mixed`

定义：

- `support_attacker_same_servant`
  - 三张卡 `owner` 相同
  - 对应前排槽位 `is_support = true`
  - 且该槽位角色为主打手
- `buster_3`
  - 三张卡颜色全是 `buster`
- `arts_3`
  - 三张卡颜色全是 `arts`
- `tri_color`
  - 三张卡颜色两两不同
  - 顺序不重要
- `other_same_servant`
  - 三张卡 `owner` 相同
  - 但不属于 `support_attacker_same_servant`
- `quick_3`
  - 三张卡颜色全是 `quick`
- `mixed`
  - 以上都不满足

## 固定优先级

按以下顺序选择第一组命中的三张：

1. `support_attacker_same_servant`
2. `buster_3`
3. `arts_3`
4. `tri_color`
5. `other_same_servant`
6. `quick_3`
7. `mixed`

如果同一类型出现多组候选，第一版按以下规则打破平局：

1. 优先包含更高从者优先级的组合
2. 再按卡位从左到右的自然顺序

## 接口变化

### 新增普通卡结构

新增单张普通卡的结构，至少包含：

- `index`
- `owner`
- `color`

### 新增能力

- 普通卡颜色识别器
- 组合分类与优先级选择器

### 主流程接入

`workflow.handle_card_select` 在读取 `owner` 后，再读取 `color`，然后基于 `owner + color + command_card_priority` 生成最终普通卡计划。

## 配置

本轮先不新增复杂配置。

固定优先级直接写入代码：

- 助战打手三同一从者
- 三红
- 三蓝
- 三色连携
- 其他从者三同一从者
- 三绿

当前已有的 `smart_battle.command_card_priority` 继续只承担“从者优先顺序”的职责。

## 验证

至少验证以下内容：

- 颜色识别能把红蓝绿分开
- 三色连携判定只在三张颜色各不相同时触发
- 助战打手三同一从者优先于其他连携
- 多组候选同时命中时，按既定优先级稳定选择
- 若颜色识别失败，主流程仍能保守回退到已有普通卡逻辑
