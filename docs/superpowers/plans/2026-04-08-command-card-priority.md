# Command Card Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add command card ownership recognition and let battle flow choose normal cards by configured servant priority while keeping Noble Phantasm priority unchanged.

**Architecture:** Reuse the existing embedding-based portrait pipeline, but build a dedicated command-card recognizer that crops the upper half of the five command cards and compares them only against the current frontline servants. Keep card selection policy separate from image recognition so ordering can be tested with small deterministic tests.

**Tech Stack:** Python 3.12, OpenCV, ONNX Runtime embedding pipeline, pytest, YAML config.

---

### Task 1: Add the failing config and planning tests

**Files:**
- Create: `D:\VSCodeRepository\Lumina\tests\test_command_card_priority.py`
- Modify: `D:\VSCodeRepository\Lumina\core\config.py`
- Modify: `D:\VSCodeRepository\Lumina\core\workflow.py`

- [ ] **Step 1: Write the failing test**

```python
from core.config import BattleConfig
from core.workflow import build_command_card_plan


def test_loads_command_card_priority_from_yaml(tmp_path):
    config_path = tmp_path / "battle_config.yaml"
    config_path.write_text(
        """
smart_battle:
  enabled: true
  frontline:
    - slot: 1
      servant: caster/zhuge_liang
      role: support
      is_support: false
    - slot: 2
      servant: caster/altria_caster
      role: support
      is_support: false
    - slot: 3
      servant: berserker/morgan
      role: attacker
      is_support: true
  command_card_priority:
    - berserker/morgan
    - caster/zhuge_liang
    - caster/altria_caster
""",
        encoding="utf-8",
    )

    config = BattleConfig.from_yaml(str(config_path))

    assert config.smart_battle.command_card_priority == [
        "berserker/morgan",
        "caster/zhuge_liang",
        "caster/altria_caster",
    ]


def test_build_command_card_plan_uses_servant_priority_after_nobles():
    card_owners = {
        1: "caster/altria_caster",
        2: "berserker/morgan",
        3: "caster/zhuge_liang",
        4: "berserker/morgan",
        5: "caster/altria_caster",
    }

    plan = build_command_card_plan(
        noble_indices=[3],
        card_owners=card_owners,
        servant_priority=[
            "berserker/morgan",
            "caster/zhuge_liang",
            "caster/altria_caster",
        ],
    )

    assert plan == [
        {"type": "noble", "index": 3},
        {"type": "card", "index": 2},
        {"type": "card", "index": 4},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: FAIL because `command_card_priority` and `build_command_card_plan` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class SmartBattleConfig:
    enabled: bool = False
    frontline: list[SmartBattleFrontlineSlot] = field(default_factory=list)
    wave_plan: list[SmartBattleWavePlan] = field(default_factory=list)
    command_card_priority: list[str] = field(default_factory=list)
```

```python
def build_command_card_plan(
    *,
    noble_indices: list[int],
    card_owners: dict[int, str | None],
    servant_priority: list[str],
) -> list[dict[str, int]]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: PASS


### Task 2: Add command-card recognition

**Files:**
- Create: `D:\VSCodeRepository\Lumina\core\command_card_recognition.py`
- Modify: `D:\VSCodeRepository\Lumina\core\coordinates.py`
- Modify: `D:\VSCodeRepository\Lumina\core\resources.py`
- Test: `D:\VSCodeRepository\Lumina\tests\test_command_card_priority.py`

- [ ] **Step 1: Write the failing recognition test**

```python
from core.command_card_recognition import crop_command_card_face
from core.coordinates import GameCoordinates
import numpy as np


def test_crop_command_card_face_uses_upper_half():
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    crop = crop_command_card_face(screen, GameCoordinates.COMMAND_CARD_REGIONS[1])

    assert crop.shape[0] == GameCoordinates.COMMAND_CARD_FACE_REGIONS[1][3] - GameCoordinates.COMMAND_CARD_FACE_REGIONS[1][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: FAIL because command-card coordinate helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class CommandCardRecognizer:
    def recognize_frontline(self, screen_rgb: np.ndarray, frontline: list[str]) -> dict[int, str | None]:
        ...
```

Implementation notes:
- Use the five command card regions.
- Crop only the upper half region.
- Load positives from `<servant>/atlas/commands/**.png`.
- Build negatives from the other two frontline servants.
- Return `None` for cards that cannot be recognized confidently.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: PASS


### Task 3: Wire card recognition into battle flow

**Files:**
- Modify: `D:\VSCodeRepository\Lumina\core\app.py`
- Modify: `D:\VSCodeRepository\Lumina\core\workflow.py`
- Modify: `D:\VSCodeRepository\Lumina\config\battle_config.yaml`
- Test: `D:\VSCodeRepository\Lumina\tests\test_command_card_priority.py`

- [ ] **Step 1: Extend the failing test for workflow planning**

```python
def test_build_command_card_plan_falls_back_left_to_right_for_unknown_cards():
    plan = build_command_card_plan(
        noble_indices=[],
        card_owners={1: None, 2: "caster/zhuge_liang", 3: None, 4: "berserker/morgan", 5: None},
        servant_priority=["berserker/morgan", "caster/zhuge_liang"],
    )

    assert plan == [
        {"type": "card", "index": 4},
        {"type": "card", "index": 2},
        {"type": "card", "index": 1},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: FAIL until fallback ordering is wired correctly.

- [ ] **Step 3: Write minimal implementation**

```python
def handle_card_select(self) -> None:
    np_statuses = self._read_np_statuses_with_retry()
    card_owners = self._read_command_card_owners()
    card_plan = self.build_card_plan(np_statuses, card_owners)
    self.execute_card_plan(card_plan)
```

Implementation notes:
- Keep Noble Phantasm cards first.
- Use `smart_battle.command_card_priority` when present.
- If recognition is unavailable, fall back to the old left-to-right behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: PASS


### Task 4: Run offline verification with real assets

**Files:**
- Create: `D:\VSCodeRepository\Lumina\scripts\check_command_card_recognition.py`
- Modify: `D:\VSCodeRepository\Lumina\README.md`

- [ ] **Step 1: Add a tiny offline checker**

```python
def main() -> int:
    # load image, config frontline, print five card owners
    ...
```

- [ ] **Step 2: Run offline verification**

Run: `uv run pytest tests/test_command_card_priority.py -q`
Expected: PASS

Run: `uv run python scripts/check_command_card_recognition.py --image "test_image\\指令卡学姐5.png"`
Expected: Prints five card ownership results without crashing.

- [ ] **Step 3: Update the docs**

```markdown
- `smart_battle.command_card_priority`: normal card servant priority after Noble Phantasm cards
- `scripts/check_command_card_recognition.py`: offline command-card owner checker
```
