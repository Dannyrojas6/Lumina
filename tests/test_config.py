from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import BattleConfig


def test_loads_command_card_priority_from_yaml():
    with TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "battle_config.yaml"
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
