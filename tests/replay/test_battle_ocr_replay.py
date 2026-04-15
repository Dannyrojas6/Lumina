import unittest
from pathlib import Path

from core.battle_runtime import BattleSnapshotReader
from core.perception import BattleOcrReader
from core.shared import BattleOcrConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


class BattleOcrReplayTest(unittest.TestCase):
    def test_snapshot_reader_replays_known_card_select_sample(self) -> None:
        image_path = REPO_ROOT / "test_image" / "fight" / "指令卡选择界面.png"
        reader = BattleSnapshotReader(
            battle_ocr=BattleOcrReader(config=BattleOcrConfig(save_ocr_crops=False))
        )

        snapshot = reader.read_snapshot_from_path(image_path)

        self.assertEqual(snapshot.wave_index, 1)
        self.assertEqual(snapshot.enemy_count, 2)
        self.assertEqual(snapshot.current_turn, 1)
        self.assertEqual(
            [status.np_value for status in snapshot.frontline_np],
            [40, 40, 80],
        )
        self.assertEqual(
            [status.hp_value for status in snapshot.enemy_hp],
            [None, 384508, 372216],
        )


if __name__ == "__main__":
    unittest.main()
