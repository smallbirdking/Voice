"""Contract tests for repeatable learning checkpoint records."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REQUIRED_SECTIONS = (
    "元数据",
    "目标",
    "核心概念",
    "入口命令",
    "预期结果",
    "实际输出",
    "结果解释",
    "遇到的问题",
    "进入下一步的条件",
)


def read_sections(path: Path) -> dict[str, str]:
    """Return level-two Markdown sections and their body text."""

    content = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## (?P<name>.+)$", content, re.MULTILINE))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group("name")] = content[body_start:body_end].strip()

    return sections


class CheckpointTemplateTests(unittest.TestCase):
    checkpoint_dir = Path(__file__).parents[1] / "checkpoints"

    def test_template_contains_every_required_section(self) -> None:
        sections = read_sections(self.checkpoint_dir / "TEMPLATE.md")

        self.assertEqual(tuple(sections), REQUIRED_SECTIONS)
        for name in REQUIRED_SECTIONS:
            self.assertTrue(sections[name], f"template section is empty: {name}")

    def test_numbered_checkpoints_are_filled_and_reproducible(self) -> None:
        checkpoints = sorted(self.checkpoint_dir.glob("[0-9][0-9][0-9]-*.md"))
        self.assertTrue(checkpoints)

        for checkpoint in checkpoints:
            with self.subTest(checkpoint=checkpoint.name):
                content = checkpoint.read_text(encoding="utf-8")
                sections = read_sections(checkpoint)

                self.assertEqual(tuple(sections), REQUIRED_SECTIONS)
                for name in REQUIRED_SECTIONS:
                    self.assertTrue(sections[name], f"checkpoint section is empty: {name}")

                self.assertNotIn("<command>", content)
                self.assertNotIn("<output>", content)
                self.assertIn("status`: `complete", sections["元数据"])


if __name__ == "__main__":
    unittest.main()
