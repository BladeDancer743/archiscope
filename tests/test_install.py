import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cli import _install_agent
from src.install import RULE_CONTENT, SKILL_CONTENT


class InstallTests(unittest.TestCase):
    def test_skill_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("src.install.find_project", return_value=root):
                self.assertTrue(_install_agent("codex"))
                self.assertTrue(_install_agent("codex"))

            target = root / ".codex" / "skills" / "archiscope" / "SKILL.md"
            self.assertEqual(target.read_text(encoding="utf-8"), SKILL_CONTENT)

    def test_append_install_preserves_existing_content_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".github" / "copilot-instructions.md"
            target.parent.mkdir(parents=True)
            target.write_text("# Existing instructions\n", encoding="utf-8")

            with patch("src.install.find_project", return_value=root):
                self.assertTrue(_install_agent("copilot"))
                self.assertTrue(_install_agent("copilot"))

            installed = target.read_text(encoding="utf-8")
            self.assertTrue(installed.startswith("# Existing instructions\n"))
            self.assertEqual(installed.count(RULE_CONTENT.rstrip()), 1)

    def test_reference_agent_files_match_generated_content(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "claude-code.md": SKILL_CONTENT,
            "codex.md": SKILL_CONTENT,
            "opencode.md": SKILL_CONTENT,
            "cursor.md": "# Archiscope\n\n" + RULE_CONTENT,
            "copilot.md": "## Archiscope\n\n" + RULE_CONTENT,
        }
        for name, content in expected.items():
            with self.subTest(name=name):
                self.assertEqual(
                    (root / "agents" / name).read_text(encoding="utf-8"),
                    content,
                )


if __name__ == "__main__":
    unittest.main()
