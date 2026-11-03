"""Check the AI-neutral operations handbook before publishing."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    "README.md",
    "AGENTS.md",
    "handbook/00_START_HERE.md",
    "handbook/10_ARCHITECTURE.md",
    "handbook/20_OPERATIONS.md",
    "handbook/30_HISTORY_AND_DECISIONS.md",
    "handbook/40_ANALYTICS_AND_SECURITY.md",
    "handbook/50_AI_HANDOFF.md",
    "handbook/archive/README_before_reorganization_2026-11-03.md",
    "handbook/archive/AGENTS_before_reorganization_2026-11-03.md",
    "handbook/archive/counter-ingest_README_before_reorganization_2026-11-03.md",
    "counter-ingest/README.md",
]


class HandbookIntegrityTests(unittest.TestCase):
    def test_reorganization_kept_current_documents_and_backups(self):
        for name in REQUIRED:
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file())
                self.assertGreater((ROOT / name).stat().st_size, 100)
        self.assertLess(len((ROOT / "README.md").read_text()), 6000)
        self.assertGreater(
            (ROOT / "handbook/archive/README_before_reorganization_2026-11-03.md").stat().st_size,
            10000,
        )

    def test_relative_markdown_links_resolve(self):
        # Exclude URL anchors. Internal markdown links must be portable
        # to a local Git checkout, not only to a specific AI's connector.
        for filename in REQUIRED:
            source = ROOT / filename
            text = source.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                target = link.split("#", 1)[0].split("?", 1)[0]
                if not target or "://" in target or target.startswith(("mailto:", "#")):
                    continue
                target_path = source.parent / target
                with self.subTest(source=filename, target=target):
                    self.assertTrue(target_path.exists(), "Broken local Markdown link")

    def test_transfer_does_not_depend_on_chat_memory(self):
        start = (ROOT / "handbook/00_START_HERE.md").read_text()
        handoff = (ROOT / "handbook/50_AI_HANDOFF.md").read_text()
        policy = (ROOT / "AGENTS.md").read_text()
        self.assertIn("ChatGPT以外", start)
        self.assertIn("GitHub", handoff)
        self.assertIn("Vercel", handoff)
        self.assertIn("data/source-checks", policy)
        self.assertIn("公開", handoff)

    def test_latest_historical_records_are_preserved(self):
        import json

        shipping = json.loads((ROOT / "data/shipping-28.json").read_text())
        self.assertEqual([entry["day"] for entry in shipping], list(range(1, 29)))
        for day, date in ((27, "2026-11-01"), (28, "2026-11-02")):
            row = shipping[day - 1]
            self.assertEqual(row["evidence_type"], "site_owner_observation")
            self.assertEqual(row["observed_at_jst_approx"][:10], date)
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text())
        self.assertTrue(any(x.get("date") == "2026-10-25" and x.get("outcome_status") == "的中" for x in history))
        self.assertTrue(any(x.get("date") == "2026-10-31" and x.get("outcome_status") == "外れ" for x in history))


if __name__ == "__main__":
    unittest.main()
