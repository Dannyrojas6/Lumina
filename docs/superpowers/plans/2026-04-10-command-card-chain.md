# Command Card Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为五张普通指令卡补上颜色识别和连携组合判断，并按固定优先级输出最终普通卡计划。

**Architecture:** 保持当前“宝具优先 + 普通卡补位”的总入口不变，在普通卡侧新增两个独立能力：颜色识别器和组合选择器。主流程只负责收集 `owner` 与 `color`，再将三张最优普通卡结果交给现有执行入口。

**Tech Stack:** Python 3.12, numpy, OpenCV, unittest

---

### File Map

- Modify: `D:\VSCodeRepository\Lumina\core\coordinates.py`
  - 增加色卡颜色识别使用的固定区域常量
- Modify: `D:\VSCodeRepository\Lumina\core\command_card_recognition.py`
  - 增加普通卡颜色识别与统一读取结果结构
- Modify: `D:\VSCodeRepository\Lumina\core\workflow.py`
  - 接入颜色识别和连携优先级选牌
- Create: `D:\VSCodeRepository\Lumina\tests\test_command_card_chain.py`
  - 覆盖颜色分类、连携类型分类和优先级选择

### Task 1: 写连携选择测试

**Files:**
- Create: `D:\VSCodeRepository\Lumina\tests\test_command_card_chain.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from core.command_card_recognition import CommandCardInfo, classify_card_chain, choose_best_card_chain


class CommandCardChainTest(unittest.TestCase):
    def test_support_attacker_same_servant_beats_buster_chain(self) -> None:
        cards = [
            CommandCardInfo(index=1, owner=\"caster/merlin\", color=\"buster\"),
            CommandCardInfo(index=2, owner=\"caster/merlin\", color=\"arts\"),
            CommandCardInfo(index=3, owner=\"caster/merlin\", color=\"quick\"),
            CommandCardInfo(index=4, owner=\"berserker/morgan\", color=\"buster\"),
            CommandCardInfo(index=5, owner=\"berserker/morgan\", color=\"buster\"),
        ]

        best = choose_best_card_chain(
            cards=cards,
            servant_priority=[\"caster/merlin\", \"berserker/morgan\"],
            support_attacker=\"caster/merlin\",
        )

        self.assertEqual([item.index for item in best], [1, 2, 3])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests\\test_command_card_chain.py`
Expected: FAIL because `CommandCardInfo` / `choose_best_card_chain` are missing

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class CommandCardInfo:
    index: int
    owner: str | None
    color: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests\\test_command_card_chain.py`
Expected: PASS

### Task 2: 写颜色识别测试

**Files:**
- Modify: `D:\VSCodeRepository\Lumina\tests\test_command_card_chain.py`
- Modify: `D:\VSCodeRepository\Lumina\core\coordinates.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_detect_command_card_color_recognizes_primary_rgb_groups(self) -> None:
        self.assertEqual(detect_command_card_color(make_color_block(\"buster\")), \"buster\")
        self.assertEqual(detect_command_card_color(make_color_block(\"arts\")), \"arts\")
        self.assertEqual(detect_command_card_color(make_color_block(\"quick\")), \"quick\")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests\\test_command_card_chain.py`
Expected: FAIL because `detect_command_card_color` is missing

- [ ] **Step 3: Write minimal implementation**

```python
def detect_command_card_color(card_crop: np.ndarray) -> str | None:
    sample = crop_command_card_color_zone(card_crop)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests\\test_command_card_chain.py`
Expected: PASS

### Task 3: 接入主流程

**Files:**
- Modify: `D:\VSCodeRepository\Lumina\core\command_card_recognition.py`
- Modify: `D:\VSCodeRepository\Lumina\core\workflow.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_build_command_card_plan_uses_chain_priority_before_servant_fallback(self) -> None:
        ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests\\test_command_card_chain.py`
Expected: FAIL because workflow still ignores color chains

- [ ] **Step 3: Write minimal implementation**

```python
def recognize_frontline_cards(...) -> list[CommandCardInfo]:
    ...

def build_command_card_plan(..., cards: list[CommandCardInfo] | None = None):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests\\test_command_card_chain.py`
Expected: PASS

### Task 4: 实际验证

**Files:**
- Verify: `D:\VSCodeRepository\Lumina\core\command_card_recognition.py`
- Verify: `D:\VSCodeRepository\Lumina\core\workflow.py`
- Verify: `D:\VSCodeRepository\Lumina\tests\test_command_card_chain.py`

- [ ] **Step 1: Run automated verification**

Run: `python tests\\test_command_card_chain.py`
Expected: PASS

- [ ] **Step 2: Run regression verification**

Run: `python tests\\test_mask_region_picker.py`
Expected: PASS

- [ ] **Step 3: Run project-specific smoke verification**

Run: `python scripts\\mask_region_picker.py`
Expected: 新脚本仍可正常启动，不受本轮改动影响
