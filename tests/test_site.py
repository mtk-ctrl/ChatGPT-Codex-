import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reset_site", ROOT / "scripts/site.py")
site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site)
PSPEC = importlib.util.spec_from_file_location("primary", ROOT / "scripts/primary.py")
primary = importlib.util.module_from_spec(PSPEC)
PSPEC.loader.exec_module(primary)

class FirstPartyTests(unittest.TestCase):
    def test_only_approved_urls(self):
        self.assertIsNone(site.safe_url("https://codex-reset.com/api/timeline"))
        self.assertIsNone(site.safe_url("https://x.com.evil.test/post"))
        self.assertIsNone(site.safe_url("https://secret@x.com/thsottiaux/status/111111111111"))
        self.assertEqual(site.safe_url("https://x.com/thsottiaux/status/123?s=20"), "https://x.com/thsottiaux/status/123")

    def test_official_detection(self):
        body = "On Sep 3, 2026 and Sep 4, 2026 Plus Pro Business accounts got banked resets. On Sep 7, 2026 we provided an automatic reset."
        self.assertTrue(primary.official_verified(body))
        self.assertFalse(primary.official_verified("Sep 3, 2026 Sep 4, 2026 Sep 7, 2026"))

    def test_current_history_has_only_verified_primary_sources(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 56)
        self.assertTrue(all(primary.trusted(r) for r in rows))
        official = [r for r in rows if r["evidence"] == "official"]
        indexed = [r for r in rows if r["evidence"] == "staff_x"]
        self.assertEqual(len(official), 3)
        self.assertTrue(all(r.get("date_precision") == "day" and "未公表" in site.record_row(r) for r in official))
        self.assertTrue(all(r.get("verification_method", "").startswith("X原投稿の検索結果表示") for r in indexed))
        self.assertTrue(all(r.get("original_url", "").startswith("https://x.com/thsottiaux/status/") for r in indexed))

    def test_x_requires_original_text(self):
        markup = '<meta property="og:description" content="We have now reset usage limits for Codex.">'
        post = primary.x_record("thsottiaux", "2111492738025959922", markup)
        self.assertIsNotNone(post)
        self.assertTrue(primary.trusted(post))
        self.assertFalse(primary.trusted({**post, "original_url": "https://other.example/story"}))
        self.assertIsNone(primary.x_record("thsottiaux", "2111492738025959922", '<meta property="og:description" content="Maybe reset tomorrow.">'))

    def test_failing_x_does_not_replace_source(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            history = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
            site.write_json(data / "events.json", history)
            official = "Sep 3, 2026 and Sep 4, 2026 Plus Pro Business banked reset. Sep 7, 2026 global reset."
            def fake_fetch(url, **kwargs):
                if "help.openai.com" in url:
                    return official
                raise RuntimeError("X blocked")
            result = primary.collect_primary(data, fake_fetch, site.read_json, site.write_json,
                                             lambda: "2026-10-20T07:00:00Z")
            self.assertEqual(result, 0)
            self.assertEqual(site.read_json(data / "health.json")["feed"], "partial")
            self.assertEqual(site.read_json(data / "events.json"), history)

if __name__ == "__main__":
    unittest.main()
