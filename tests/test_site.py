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
        self.assertIsNone(site.safe_url("https://unapproved.example/api/timeline"))
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
        self.assertTrue(all(r.get("date_precision") == "day" and "時刻の記載なし" in site.record_row(r) for r in official))
        self.assertTrue(all(r.get("verification_method", "").startswith("X原投稿の検索結果表示") for r in indexed))
        self.assertTrue(all(r.get("original_url", "").startswith("https://x.com/thsottiaux/status/") for r in indexed))
        self.assertTrue(all("Tibo氏のX投稿" in site.record_row(r) for r in indexed))
        self.assertTrue(all("全文未確認" not in site.record_row(r) for r in indexed))
        self.assertIn("Thibault Sottiaux", site.ABOUT)
        self.assertNotIn("OpenAI関係者のX原投稿", site.ABOUT)
        self.assertIn("Codex責任者Tibo氏", site.shell("確認", "説明", "about", "本文", "2026-10-20T12:00:00Z"))
        self.assertIn("情報の確かめ方", site.ABOUT)
        self.assertIn("掲載件数はリセットが行われた回数ではありません", site.ABOUT)
        self.assertIn("通常の利用枠", site.GUIDE)
        self.assertNotIn("一斉リセット", site.KINDS["global"])
        self.assertIn("臨時リセット", site.KINDS["global"])
        self.assertNotIn("対象サービス：", site.record_row(indexed[0]))
        self.assertNotIn("ページ更新：", site.shell("test", "desc", "index", "", "2026-10-20T12:00:00Z"))
        self.assertIn("予告を含む発表記録", site.homepage(rows, "2026-10-20T12:00:00Z", {"status":"stale","generated_at":"2026-10-20T12:00:00Z","horizons":{}}, []))

        self.assertNotIn("原投稿の検索表示で確認", site.record_row(indexed[0]))

    def test_unavailable_forecast_is_not_shown_to_visitors(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        states = [
            {"status": "stale", "generated_at": "2026-10-20T12:00:00Z", "horizons": {}},
            {"status": "insufficient", "generated_at": "2026-10-20T12:00:00Z", "horizons": {}},
        ]
        for forecast in states:
            with self.subTest(status=forecast["status"]):
                calendar = site.calendar_overview(rows, forecast)
                homepage = site.homepage(rows, "2026-10-20T12:00:00Z", forecast, [])
                self.assertIn("calendar-layout--full", calendar)
                self.assertNotIn('class="forecast-panel"', calendar)
                self.assertNotIn("次のリセット予測", homepage)
                self.assertNotIn("予測と結果", homepage)
                self.assertNotIn("data-health-url", homepage)
                self.assertNotIn("自動確認が一時的にできません", homepage)
                self.assertNotIn("予測の計算方法", site.shell("test", "test", "index", "text", "2026-10-20T12:00:00Z", show_forecast=False))
        self.assertEqual(site.forecast_results([]), "")
        self.assertEqual(site.forecast_results([{"outcomes": {}}]), "")

    def test_published_forecast_is_visible(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        forecast = {
            "status": "ok", "generated_at": "2026-10-20T12:00:00Z",
            "elapsed_hours": 24, "sample_size": 10, "eligible_size": 8,
            "reference_date": "2026-10-21",
            "horizons": {"24": {"display_percent": 40, "total": 8, "count": 3, "observed_ratio_interval": [10, 70]},
                         "48": {"display_percent": 65, "total": 8, "count": 5}}
        }
        view = site.calendar_overview(rows, forecast)
        self.assertIn('class="forecast-panel"', view)
        self.assertIn("24時間以内", view)
        self.assertIn("40<small>%</small>", view)
        self.assertNotIn("calendar-layout--full", view)

    def test_ticket_wording_for_public_readers(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        ticket_records = [r for r in rows if r["kind"] == "banked"]
        self.assertGreater(len(ticket_records), 0)
        self.assertEqual(site.KINDS["banked"], "リセットチケットの配布")
        self.assertEqual(site.record_title({"kind": "banked", "state": "announced"}), "リセットチケットの配布予告")
        self.assertEqual(site.record_title({"kind": "banked", "state": "reported"}), "リセットチケットを配布")
        self.assertEqual(site.record_title({"kind": "global", "state": "announced"}), "利用枠リセットを予告")
        self.assertEqual(site.record_title({"kind": "global", "state": "reported"}), "利用枠をリセット")

        self.assertIn("チケット", site.GUIDE)
        self.assertIn("有効期限", site.GUIDE)
        self.assertIn("チケット", site.calendar_overview(rows, {"status": "stale", "generated_at": "2026-10-20T12:00:00Z", "horizons": {}}))
        self.assertNotIn("保存型", site.GUIDE)
        self.assertNotIn("保存型", site.KINDS["banked"])
        self.assertTrue(all("保存型" not in (r.get("note") or "") for r in rows))
        forecast = {"status": "stale", "generated_at": "2026-10-20T12:00:00Z", "horizons": {}}
        overview = site.calendar_overview(rows, forecast)
        self.assertIn("リセットカレンダー", overview)
        self.assertIn("リセット</span>", overview)


    def test_calendar_does_not_mark_completed_reset_as_still_pending(self):
        import re
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        forecast = {"status": "stale", "generated_at": "2026-10-20T12:00:00Z", "horizons": {}}
        html = site.calendar_overview(rows, forecast)
        # On 18 October JST, both a reset announcement and completion were posted.
        day = re.search(r'data-calendar-day="2026-10-18".*?</button>', html)
        self.assertIsNotNone(day)
        self.assertIn("リセット</span>", day.group(0))
        self.assertNotIn(">予告</span>", day.group(0))
        self.assertIn("投稿時刻は日本時間", html)
        self.assertIn("臨時リセット", html)
        self.assertNotIn('>一斉</span>', html)

    def test_october_25_editorial_prediction(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        config = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        now = site.parse_time("2026-10-23T22:00:00Z")
        editorial = site.active_editorial_forecast(rows, now, config)
        self.assertIsNotNone(editorial)
        forecast = {"status": "stale", "generated_at": "2026-10-20T14:00:00Z", "horizons": {}}
        view = site.homepage(rows, "2026-10-20T14:00:00Z", forecast, [], editorial)
        self.assertIn("2026年10月25日（日）", view)
        self.assertIn("サイトで予想を公開：", view)
        self.assertIn("公開時刻を確認中", view)
        self.assertIn("10月24日に改めて", view)
        self.assertIn("前回の同じ予想日とは別の予想", view)
        self.assertIn("1～3日間隔", view)
        self.assertIn('data-calendar-day="2026-10-25"', view)
        self.assertIn("当サイトの予想・非公式", view)
        self.assertIn("OpenAIの正式な予定", view)
        self.assertNotIn("24時間以内", view)

    def test_editorial_prediction_auto_expires(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        config = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-25T15:00:00Z"), config))
        baseline = next(r for r in rows if r["id"] == config["last_report_id"])
        newer = {**baseline, "id": "new-reset:global", "reference_at": "2026-10-25T01:00:00Z", "state": "reported"}
        self.assertIsNone(site.active_editorial_forecast([*rows, newer], site.parse_time("2026-10-25T02:00:00Z"), config))
        prior_cycle_completion = {**baseline, "id": "day17-done:global", "reference_at": "2026-10-23T08:00:00Z", "state": "reported"}
        previous_config = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))[-1]
        prior_rows = [r for r in rows if r.get("post_id") not in {"2113492187770175603", "2113492502355562875"}]
        self.assertIsNotNone(site.active_editorial_forecast([*prior_rows, prior_cycle_completion], site.parse_time("2026-10-23T09:00:00Z"), previous_config))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-23T10:00:00Z"), config))

    def test_archived_october_23_prediction_shows_original_publication_time(self):
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        archived = site.previous_editorial_predictions(history)
        self.assertIn("過去のリセット予想", archived)
        self.assertIn("2026年10月23日（金）", archived)
        self.assertIn("2026/10/20 23:17", archived)
        self.assertIn("39437667124", archived)
        self.assertIn("2～3日間隔", archived)
        self.assertNotIn("リセット実施が確定しました", archived)
        self.assertEqual(site.previous_editorial_predictions([]), "")
        self.assertEqual(site.publication_timestamp_markup({}), "")

    def test_full_page_includes_prior_prediction_as_an_audit_trail(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        cfg = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        editorial = site.active_editorial_forecast(rows, site.parse_time("2026-10-23T22:00:00Z"), cfg)
        forecast = {"status":"stale", "generated_at":"2026-10-23T22:00:00Z", "horizons":{}}
        page = site.homepage(rows, "2026-10-23T22:00:00Z", forecast, [], editorial, history)
        self.assertIn("2026/10/20 23:17", page)
        self.assertIn("2026/10/23 07:07", page)
        self.assertIn("公開時刻を確認中", page)
        self.assertIn("過去のリセット予想", page)

    def test_new_day18_announcement_and_forecast_history(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        ids = {r.get("post_id") for r in rows}
        self.assertIn("2113492187770175603", ids)
        self.assertIn("2113492502355562875", ids)
        day18 = [r for r in rows if r.get("post_id") in {"2113492187770175603", "2113492502355562875"}]
        self.assertTrue(all(r["state"] == "announced" for r in day18))
        self.assertTrue(all(site.record_day(r) == "2026-10-23" for r in day18))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        self.assertEqual({r["date"] for r in history}, {"2026-10-23", "2026-10-25"})
        output = site.previous_editorial_predictions(history)
        self.assertIn("2026/10/23 07:07", output)
        self.assertIn("2026/10/20 23:17", output)
        self.assertIn("その後：", output)
        proposal = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-23T19:00:00Z"), proposal))

    def test_new_distinct_reset_notice_retires_prediction_without_losing_original_day(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        proposal = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))[-1]
        self.assertEqual(proposal["date"], "2026-10-25")
        self.assertIsNotNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-23T00:00:00Z"), proposal))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-23T05:00:00Z"), proposal))


    def test_separate_october_25_forecasts_have_distinct_issue_dates(self):
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        old = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))[-1]
        self.assertEqual(current["date"], old["date"])
        self.assertNotEqual(current["created_at"], old["created_at"])
        self.assertEqual(old["published_at"], "2026-10-23T07:07:47+09:00")
        self.assertTrue(old["retired_at"])
        self.assertEqual(current["last_report_id"], "2113492502355562875:global")
        self.assertNotIn("published_at", current)
        self.assertIsNotNone(site.active_editorial_forecast(
            json.loads((ROOT / "data/events.json").read_text(encoding="utf-8")),
            site.parse_time("2026-10-23T22:00:00Z"), current))

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
