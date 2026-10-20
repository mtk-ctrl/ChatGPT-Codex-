import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("reset_site", Path(__file__).resolve().parents[1] / "scripts/site.py")
site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site)


def fixture(**updates):
    row = {"id": "2111492738025959922", "type": "reset", "confirmed": True,
           "scope": "global", "announced_at": "2026-10-17T20:41:01Z",
           "url": "https://x.com/thsottiaux/status/2111492738025959922",
           "source": "archive", "audience": ["codex", "chatgpt_work"], "reason_tags": []}
    row.update(updates)
    return row


class CollectionTests(unittest.TestCase):
    def normalize(self, *rows, **kwargs):
        return site.normalize_feed({"events": list(rows)}, now=datetime(2026, 10, 20, tzinfo=timezone.utc), **kwargs)

    def test_jst_day_and_month_rollover(self):
        self.assertEqual(site.jst("2026-05-31T15:25:00Z"), "2026/06/01 00:25")
        self.assertEqual(site.jst("2026-10-17T20:41:01Z"), "2026/10/18 05:41")

    def test_timestamp_requires_timezone(self):
        with self.assertRaises(ValueError):
            site.parse_time("2026-10-17T20:41:01")

    def test_upstream_confirmed_is_not_official(self):
        rows, _ = self.normalize(fixture(source="official", confidence="high"))
        self.assertEqual(rows[0]["evidence"], "third_party")
        self.assertFalse(rows[0]["time_officially_verified"])

    def test_official_date_does_not_certify_a_time(self):
        proof = {"post_id": "2111492738025959922", "kind": "global", "official_date": "2026-10-17", "url": site.OFFICIAL_URL, "time_verified": False}
        rows, _ = self.normalize(fixture(), confirmations=[proof])
        self.assertEqual(rows[0]["evidence"], "official")
        self.assertFalse(rows[0]["time_officially_verified"])

    def test_dedupe_and_distinguish_banked_grant(self):
        row = fixture()
        voucher = fixture(type="credits", reset_kind="banked", banked_grant=True)
        delivery = fixture(id="2111492738025959923", type="credits", reset_kind="banked", banked_grant=False)
        rows, _ = self.normalize(row, copy.deepcopy(row), voucher, delivery)
        self.assertEqual({r["kind"] for r in rows}, {"global", "banked"})
        self.assertEqual(len(rows), 2)

    def test_quotation_stays_separate_from_official_confirmation(self):
        proof = {"post_id": "2111492738025959922", "kind": "global", "level": "quoted", "url": "https://community.openai.com/t/example/1"}
        rows, _ = self.normalize(fixture(), confirmations=[proof])
        self.assertEqual(rows[0]["evidence"], "quoted")
        self.assertIsNone(rows[0]["official_confirmation"])
        self.assertEqual(rows[0]["quotation_confirmation"], proof)

    def test_future_and_unsafe_sources_do_not_enter_published_data(self):
        rows, rejected = self.normalize(fixture(), fixture(id="2111492738025959923", announced_at="2099-01-01T00:00:00Z"), fixture(id="2111492738025959924", url="javascript:alert(1)"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rejected, 2)

    def test_unconfirmed_teasers_are_not_published(self):
        rows, _ = self.normalize(fixture(), fixture(id="2111492738025959923", confirmed=False))
        self.assertEqual(len(rows), 1)

    def test_announcement_is_not_labeled_completed(self):
        rows, _ = self.normalize(fixture(time_kind="announcement / preview time"))
        self.assertEqual(rows[0]["state"], "announced")

    def test_upstream_post_text_is_not_republished(self):
        rows, _ = self.normalize(fixture(summary="An upstream full post should never be copied into the public data."))
        self.assertNotIn("upstream full post", json.dumps(rows))

    def test_official_marker_needs_body_date_and_explicit_fact(self):
        self.assertFalse(site.official_marker("Sign in to OpenAI Plus Pro Business"))
        self.assertFalse(site.official_marker("2026年9月7日 Plus Pro Business"))
        self.assertTrue(site.official_marker("2026 年 9 月 7 日、Plus、Pro、Business ユーザーを対象に全世界一斉リセットを実施しました。"))

    def test_network_failure_preserves_saved_history(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            rows, _ = self.normalize(fixture())
            site.write_json(data / "events.json", rows)
            with patch.object(site, "DATA", data), patch.object(site, "fetch", side_effect=RuntimeError("network unavailable")):
                self.assertEqual(site.collect(), 2)
            self.assertEqual(site.read_json(data / "events.json"), rows)
            self.assertEqual(site.read_json(data / "health.json")["feed"], "failed")

    def test_upstream_empty_feed_does_not_erase_history(self):
        with self.assertRaises(ValueError):
            site.normalize_feed({"events": []})
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            old, _ = self.normalize(fixture())
            with patch.object(site, "DATA", data):
                site.save_records(old, [])
                site.save_records([], old)
                self.assertEqual(site.read_json(data / "events.json"), old)

    def test_html_output_escapes_imported_content(self):
        rows, _ = self.normalize(fixture(), editorial={"2111492738025959922": '<script>alert("bad")</script>'})
        rendered = site.record_row(rows[0])
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_safe_url_rejects_auth_and_arbitrary_hosts(self):
        self.assertIsNone(site.safe_url("https://secret@x.com/thsottiaux/status/1"))
        self.assertIsNone(site.safe_url("https://x.com.evil.test/"))
        self.assertIsNone(site.safe_url("https://x.com:443/"))
        self.assertEqual(site.safe_url("https://x.com/thsottiaux/status/1?s=20"), "https://x.com/thsottiaux/status/1")


if __name__ == "__main__":
    unittest.main()
