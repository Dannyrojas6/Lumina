import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skill" / "git-commit"
SKILL_FILE = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"
REFERENCE_FILE = SKILL_DIR / "references" / "project-commit-policy.md"
SCRIPT_FILE = SKILL_DIR / "scripts" / "inspect_commit_scope.py"
CONVENTIONAL_RE = re.compile(r"^(feat|fix|refactor|docs|test|chore): .+")


class GitCommitSkillStructureTest(unittest.TestCase):
    def test_skill_directory_contains_required_files(self) -> None:
        self.assertTrue(SKILL_DIR.is_dir(), "missing skill/git-commit directory")
        self.assertTrue(SKILL_FILE.is_file(), "missing skill/git-commit/SKILL.md")
        self.assertTrue(OPENAI_YAML.is_file(), "missing skill/git-commit/agents/openai.yaml")
        self.assertTrue(
            REFERENCE_FILE.is_file(),
            "missing skill/git-commit/references/project-commit-policy.md",
        )
        self.assertTrue(
            SCRIPT_FILE.is_file(),
            "missing skill/git-commit/scripts/inspect_commit_scope.py",
        )

    def test_skill_mentions_workspace_group_rules(self) -> None:
        content = SKILL_FILE.read_text(encoding="utf-8")
        self.assertIn("whole working tree", content)
        self.assertIn("proposed commit groups", content)
        self.assertIn("suggested verification commands", content)
        self.assertIn("explicit confirmation", content)
        self.assertIn("Do not attempt hunk splitting", content)
        self.assertIn("review_candidates", content)

    def test_openai_yaml_mentions_grouped_workflow(self) -> None:
        content = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn("full working tree", content)
        self.assertIn("commit groups", content)
        self.assertIn("review candidates", content)


class GitCommitScopeInspectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SCRIPT_FILE.is_file():
            raise AssertionError("missing inspect_commit_scope.py")
        spec = importlib.util.spec_from_file_location(
            "git_commit_scope_inspector",
            SCRIPT_FILE,
        )
        if spec is None or spec.loader is None:
            raise AssertionError("failed to load inspect_commit_scope.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.module = module

    def assert_conventional_summary(self, value: str) -> None:
        self.assertRegex(value, CONVENTIONAL_RE)

    def test_blocks_when_workspace_has_no_changes(self) -> None:
        report = self.module.inspect_status_entries([])

        self.assertEqual(report["workspace_files"], [])
        self.assertEqual(report["proposed_groups"], [])
        self.assertIn("no_workspace_changes", report["global_blocking_reasons"])

    def test_ignores_local_note_files_during_grouping(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {"path": "TODO.md", "index_status": " ", "worktree_status": "M"},
                {
                    "path": "Pro项目指导文档.md",
                    "index_status": "?",
                    "worktree_status": "?",
                },
                {
                    "path": "core/device/adb_controller.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
            ]
        )

        self.assertEqual(report["global_blocking_reasons"], [])
        self.assertEqual(len(report["ignored_files"]), 2)
        self.assertEqual(
            [item["path"] for item in report["ignored_files"]],
            ["Pro项目指导文档.md", "TODO.md"],
        )
        self.assertEqual(len(report["proposed_groups"]), 1)
        self.assertEqual(report["proposed_groups"][0]["primary_topic"], "device")

    def test_groups_single_primary_topic_with_related_support_files(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "core/device/adb_controller.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {
                    "path": "tests/test_adb_controller.py",
                    "index_status": "?",
                    "worktree_status": "?",
                },
                {"path": "README.md", "index_status": " ", "worktree_status": "M"},
            ]
        )

        self.assertEqual(report["global_blocking_reasons"], [])
        self.assertEqual(report["unassigned_files"], [])
        self.assertEqual(len(report["proposed_groups"]), 1)
        group = report["proposed_groups"][0]
        self.assertEqual(group["primary_topic"], "device")
        self.assertEqual(group["files"], ["core/device/adb_controller.py"])
        self.assertEqual(
            group["support_files"],
            ["README.md", "tests/test_adb_controller.py"],
        )
        self.assertEqual(group["blocking_reasons"], [])
        self.assertTrue(group["suggested_verification_commands"])
        self.assert_conventional_summary(group["suggested_summary"])

    def test_multiple_primary_topics_produce_multiple_groups(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "core/device/adb_controller.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {
                    "path": "core/command_card_recognition/recognizer.py",
                    "index_status": " ",
                    "worktree_status": "M",
                },
                {
                    "path": "tests/test_adb_controller.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {
                    "path": "tests/test_command_card_recognition.py",
                    "index_status": " ",
                    "worktree_status": "M",
                },
            ]
        )

        self.assertEqual(report["global_blocking_reasons"], [])
        self.assertEqual(report["unassigned_files"], [])
        self.assertEqual(
            [group["primary_topic"] for group in report["proposed_groups"]],
            ["command-card", "device"],
        )
        for group in report["proposed_groups"]:
            self.assert_conventional_summary(group["suggested_summary"])
            self.assertEqual(group["blocking_reasons"], [])

    def test_shared_root_file_enters_review_candidates(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "core/device/adb_controller.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {
                    "path": "core/command_card_recognition/recognizer.py",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {"path": "README.md", "index_status": "M", "worktree_status": " "},
            ]
        )

        self.assertEqual(report["unassigned_files"], [])
        self.assertEqual(
            report["review_candidates"],
            [
                {
                    "path": "README.md",
                    "reason": "shared_support_file",
                    "candidate_topics": ["docs", "command-card", "device"],
                }
            ],
        )
        self.assertEqual(report["global_blocking_reasons"], [])

    def test_skill_files_form_primary_group(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "skill/git-commit/SKILL.md",
                    "index_status": "?",
                    "worktree_status": "?",
                },
                {
                    "path": "tests/test_git_commit_skill.py",
                    "index_status": "?",
                    "worktree_status": "?",
                },
            ]
        )

        self.assertEqual(report["review_candidates"], [])
        self.assertEqual(
            [group["primary_topic"] for group in report["proposed_groups"]],
            ["skill"],
        )
        self.assertEqual(
            report["proposed_groups"][0]["support_files"],
            ["tests/test_git_commit_skill.py"],
        )
        self.assertIn(
            'uv run python -m unittest discover -s tests -p "test_git_commit_skill.py" -v',
            report["proposed_groups"][0]["suggested_verification_commands"],
        )

    def test_docs_only_group_allows_empty_verification_commands(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {"path": "README.md", "index_status": "M", "worktree_status": " "},
                {
                    "path": "docs/current-project-implementation-audit.md",
                    "index_status": " ",
                    "worktree_status": "M",
                },
            ]
        )

        self.assertEqual(report["global_blocking_reasons"], [])
        self.assertEqual(len(report["proposed_groups"]), 1)
        group = report["proposed_groups"][0]
        self.assertEqual(group["primary_topic"], "docs")
        self.assertEqual(group["suggested_verification_commands"], [])
        self.assertEqual(group["blocking_reasons"], [])
        self.assert_conventional_summary(group["suggested_summary"])

    def test_assets_only_group_blocks_without_reliable_verification(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "assets/ui/continue_battle.png",
                    "index_status": "?",
                    "worktree_status": "?",
                }
            ]
        )

        self.assertEqual(len(report["proposed_groups"]), 1)
        group = report["proposed_groups"][0]
        self.assertEqual(group["primary_topic"], "assets")
        self.assertEqual(group["suggested_verification_commands"], [])
        self.assertIn("missing_verification_commands", group["blocking_reasons"])
        self.assertIn("group_missing_verification_commands", report["global_blocking_reasons"])

    def test_test_image_group_uses_full_suite_verification(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "test_image/login_bonus/登录奖励1.png",
                    "index_status": "?",
                    "worktree_status": "?",
                }
            ]
        )

        self.assertEqual(report["global_blocking_reasons"], [])
        self.assertEqual(len(report["proposed_groups"]), 1)
        group = report["proposed_groups"][0]
        self.assertEqual(group["primary_topic"], "test-fixtures")
        self.assertEqual(
            group["suggested_verification_commands"],
            ["uv run python -m unittest discover -s tests -v"],
        )
        self.assertEqual(group["blocking_reasons"], [])
        self.assertRegex(group["suggested_summary"], r"^test: .+")

    def test_test_image_files_form_separate_group_even_with_primary_topic(self) -> None:
        report = self.module.inspect_status_entries(
            [
                {
                    "path": "skill/git-commit/SKILL.md",
                    "index_status": "M",
                    "worktree_status": " ",
                },
                {
                    "path": "test_image/login_bonus/登录奖励1.png",
                    "index_status": "?",
                    "worktree_status": "?",
                },
            ]
        )

        self.assertEqual(
            [group["primary_topic"] for group in report["proposed_groups"]],
            ["skill", "test-fixtures"],
        )
        skill_group, fixture_group = report["proposed_groups"]
        self.assertEqual(skill_group["support_files"], [])
        self.assertEqual(
            fixture_group["files"],
            ["test_image/login_bonus/登录奖励1.png"],
        )

    def test_cli_outputs_workspace_group_json_report(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "status.json"
            status_path.write_text(
                json.dumps(
                    [
                        {
                            "path": "core/device/adb_controller.py",
                            "index_status": "M",
                            "worktree_status": " ",
                        },
                        {
                            "path": "tests/test_adb_controller.py",
                            "index_status": " ",
                            "worktree_status": "M",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_FILE),
                    "--status-json",
                    str(status_path),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("workspace_files", payload)
        self.assertIn("proposed_groups", payload)
        self.assertIn("review_candidates", payload)
        self.assertIn("ignored_files", payload)
        self.assertEqual(payload["unassigned_files"], [])
        self.assertEqual(len(payload["proposed_groups"]), 1)
        self.assertEqual(payload["proposed_groups"][0]["primary_topic"], "device")

    def test_parse_porcelain_z_decodes_unicode_paths_without_quotes(self) -> None:
        entries = self.module.parse_porcelain_z(
            " M test_image/连续出击.png\0?? test_image/fight/指令卡识别失败3.png\0".encode(
                "utf-8"
            )
        )

        self.assertEqual(
            entries,
            [
                {
                    "path": "test_image/连续出击.png",
                    "index_status": " ",
                    "worktree_status": "M",
                },
                {
                    "path": "test_image/fight/指令卡识别失败3.png",
                    "index_status": "?",
                    "worktree_status": "?",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
