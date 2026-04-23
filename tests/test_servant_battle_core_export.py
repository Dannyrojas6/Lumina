import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assets.servants._meta.scripts.build_servant_battle_core import (
    ACTIVE_SKILL_FIELDS,
    BASIC_INFO_FIELDS,
    EXCLUDED_FIELDS,
    NOBLE_PHANTASM_FIELDS,
    build_servant_battle_core,
    classify_top_level_fields,
    render_servant_battle_core_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MORGAN_PATH = PROJECT_ROOT / "local_data" / "servants" / "berserker" / "morgan" / "_meta" / "704000.json"
SCRIPT_PATH = PROJECT_ROOT / "assets" / "servants" / "_meta" / "scripts" / "build_servant_battle_core.py"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ServantBattleCoreExportTest(unittest.TestCase):
    def test_top_level_classification_covers_all_fields(self) -> None:
        payload = _load_json(MORGAN_PATH)

        classification = classify_top_level_fields(payload)

        self.assertEqual(len(payload), 61)
        self.assertEqual(len(classification), len(payload))
        self.assertEqual(
            {key for key, value in classification.items() if value == "basic_info"},
            BASIC_INFO_FIELDS,
        )
        self.assertEqual(
            {key for key, value in classification.items() if value == "active_skills"},
            {"skills"},
        )
        self.assertEqual(
            {key for key, value in classification.items() if value == "noble_phantasms"},
            {"noblePhantasms"},
        )
        self.assertEqual(
            {key for key, value in classification.items() if value == "excluded"},
            EXCLUDED_FIELDS,
        )

    def test_output_has_only_three_top_level_sections(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        self.assertEqual(set(result), {"basicInfo", "activeSkills", "noblePhantasm"})
        self.assertNotIn("core", result)
        self.assertNotIn("extensions", result)
        self.assertNotIn("noblePhantasms", result)

    def test_basic_info_keeps_only_minimal_display_fields_and_cards(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        self.assertEqual(set(result["basicInfo"]), BASIC_INFO_FIELDS)
        self.assertEqual(len(result["basicInfo"]), 18)
        self.assertEqual(result["basicInfo"]["cards"], payload["cards"])
        self.assertNotIn("traits", result["basicInfo"])
        self.assertNotIn("cardDetails", result["basicInfo"])
        self.assertNotIn("atkBase", result["basicInfo"])
        self.assertNotIn("hpMax", result["basicInfo"])

    def test_active_skills_keep_display_effect_tables_only(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        self.assertEqual(len(result["activeSkills"]), 3)
        for skill in result["activeSkills"]:
            self.assertEqual(set(skill), ACTIVE_SKILL_FIELDS)
            self.assertNotIn("id", skill)
            self.assertNotIn("detail", skill)
            self.assertNotIn("unmodifiedDetail", skill)
            self.assertNotIn("functions", skill)
            self.assertNotIn("icon", skill)
            self.assertNotIn("script", skill)
            self.assertNotIn("extraPassive", skill)

    def test_morgan_active_skill_effect_values_match_display_tables(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        self.assertEqual(
            result["activeSkills"],
            [
                {
                    "num": 1,
                    "name": "渴望的魅力 B",
                    "coolDown": [8, 8, 8, 8, 8, 7, 7, 7, 7, 6],
                    "effects": [
                        {
                            "label": "己方全体攻击力提升",
                            "scale": "level",
                            "values": ["10%", "11%", "12%", "13%", "14%", "15%", "16%", "17%", "18%", "20%"],
                        },
                        {
                            "label": "自身 NP 增加",
                            "scale": "level",
                            "values": ["20%", "21%", "22%", "23%", "24%", "25%", "26%", "27%", "28%", "30%"],
                        },
                        {
                            "label": "敌方全体防御力下降",
                            "scale": "level",
                            "values": ["20%", "21%", "22%", "23%", "24%", "25%", "26%", "27%", "28%", "30%"],
                        },
                    ],
                },
                {
                    "num": 2,
                    "name": "湖之加护 C",
                    "coolDown": [7, 7, 7, 7, 7, 6, 6, 6, 6, 5],
                    "effects": [
                        {
                            "label": "己方单体 NP 增加",
                            "scale": "level",
                            "values": ["10%", "11%", "12%", "13%", "14%", "15%", "16%", "17%", "18%", "20%"],
                        },
                        {
                            "label": "己方全体 NP 获得量提升",
                            "scale": "level",
                            "values": ["15%", "16%", "17%", "18%", "19%", "20%", "21%", "22%", "23%", "25%"],
                        },
                    ],
                },
                {
                    "num": 3,
                    "name": "来自止境 A",
                    "coolDown": [9, 9, 9, 9, 9, 8, 8, 8, 8, 7],
                    "effects": [
                        {
                            "label": "毅力回复",
                            "scale": "level",
                            "values": ["1000", "1200", "1400", "1600", "1800", "2000", "2200", "2400", "2600", "3000"],
                        },
                        {
                            "label": "暴击星集中度提升",
                            "scale": "level",
                            "values": ["3000%", "3200%", "3400%", "3600%", "3800%", "4000%", "4200%", "4400%", "4600%", "5000%"],
                        },
                        {
                            "label": "暴击威力提升",
                            "scale": "level",
                            "values": ["20%", "21%", "22%", "23%", "24%", "25%", "26%", "27%", "28%", "30%"],
                        },
                        {
                            "label": "每回合敌方全体攻击力下降",
                            "scale": "level",
                            "values": ["10%", "11%", "12%", "13%", "14%", "15%", "16%", "17%", "18%", "20%"],
                        },
                        {
                            "label": "暴击发生率下降",
                            "scale": "level",
                            "values": ["10%", "11%", "12%", "13%", "14%", "15%", "16%", "17%", "18%", "20%"],
                        },
                        {
                            "label": "获得暴击星",
                            "scale": "level",
                            "values": ["5", "6", "7", "8", "9", "10", "11", "12", "13", "15"],
                        },
                    ],
                },
            ],
        )

    def test_noble_phantasms_keep_display_effect_tables_only(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        noble_phantasm = result["noblePhantasm"]
        self.assertEqual(set(noble_phantasm), NOBLE_PHANTASM_FIELDS)
        self.assertNotIn("id", noble_phantasm)
        self.assertNotIn("detail", noble_phantasm)
        self.assertNotIn("unmodifiedDetail", noble_phantasm)
        self.assertNotIn("functions", noble_phantasm)
        self.assertNotIn("icon", noble_phantasm)
        self.assertNotIn("script", noble_phantasm)
        self.assertNotIn("releaseConditions", noble_phantasm)
        self.assertEqual(noble_phantasm.get("card"), "2")

    def test_morgan_noble_phantasm_effect_values_match_display_table(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)

        self.assertEqual(
            result["noblePhantasm"],
            {
                "name": "业已无法抵达的理想乡",
                "ruby": "Roadless Camelot",
                "rank": "EX",
                "type": "对城宝具",
                "card": "2",
                "effects": [
                    {
                        "label": "对圆桌骑士或妖精特攻状态",
                        "scale": "fixed",
                        "values": ["50%"],
                    },
                    {
                        "label": "宝具倍率",
                        "scale": "npLevel",
                        "values": ["300%", "400%", "450%", "475%", "500%"],
                    },
                    {
                        "label": "对拥有人之力敌人特攻",
                        "scale": "overCharge",
                        "values": ["150%", "162.5%", "175%", "187.5%", "200%"],
                    },
                    {
                        "label": "诅咒",
                        "scale": "fixed",
                        "values": ["1000"],
                    },
                    {
                        "label": "己方全体宝具 OC 上升状态",
                        "scale": "none",
                        "values": ["Ø"],
                    },
                ],
            },
        )

    def test_markdown_renderer_matches_human_readable_preview(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)
        markdown = render_servant_battle_core_markdown(
            result,
            source_path="local_data\\servants\\berserker\\morgan\\_meta\\704000.json",
            json_path=".superpowers\\notes\\morgan_704000_battle_core_v1.json",
        )

        self.assertIn("## 基本信息", markdown)
        self.assertIn("## 主动技能", markdown)
        self.assertIn("### 宝具：业已无法抵达的理想乡", markdown)
        self.assertNotIn("# Morgan 战斗核心筛选结果说明 v3", markdown)
        self.assertNotIn("## 概览", markdown)
        self.assertIn("| 己方全体攻击力提升 | level | 10% / 11%", markdown)
        self.assertIn("| 对拥有人之力敌人特攻 | overCharge | 150% / 162.5%", markdown)
        self.assertIn("`ruby`：Roadless Camelot", markdown)
        self.assertIn("`card`：2", markdown)
        self.assertIn("`coolDown`：8 / 7 / 6", markdown)
        self.assertNotIn("`coolDown`：8 / 8 / 8", markdown)
        self.assertIn("`Ø`", markdown)
        self.assertNotIn("## 宝具\n", markdown)
        self.assertNotIn("已移除内容", markdown)

    def test_removed_blocks_do_not_appear_in_output(self) -> None:
        payload = _load_json(MORGAN_PATH)

        result = build_servant_battle_core(payload)
        serialized = json.dumps(result, ensure_ascii=False)

        for field_name in (
            "classPassive",
            "appendPassive",
            "cardDetails",
            "limits",
            "ascensionAdd",
            "traitAdd",
            "svtChange",
            "overwrites",
            "extraAssets",
            "skillMaterials",
            "extraPassive",
        ):
            self.assertNotIn(field_name, serialized)

    def test_cli_writes_json_and_markdown_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            json_output = output_dir / "battle_core.json"
            markdown_output = output_dir / "battle_core.md"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(MORGAN_PATH),
                    "--output",
                    str(json_output),
                    "--markdown-output",
                    str(markdown_output),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.stdout, "")
            self.assertEqual(completed.stderr, "")
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())

            json_payload = _load_json(json_output)
            markdown = markdown_output.read_text(encoding="utf-8")
            self.assertEqual(set(json_payload), {"basicInfo", "activeSkills", "noblePhantasm"})
            self.assertEqual(json_payload["noblePhantasm"]["card"], "2")
            self.assertEqual(
                json_payload["activeSkills"][0]["coolDown"],
                [8, 8, 8, 8, 8, 7, 7, 7, 7, 6],
            )
            self.assertTrue(markdown.startswith("## 基本信息"))
            self.assertIn("`coolDown`：8 / 7 / 6", markdown)


if __name__ == "__main__":
    unittest.main()
