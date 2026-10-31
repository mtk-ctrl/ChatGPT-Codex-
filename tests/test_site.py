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

    def test_28_day_publication_tab_is_listed_and_html_safe(self):
        rows = json.loads((ROOT / "data/shipping-28.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 25)
        self.assertEqual([r["day"] for r in rows], list(range(1, 25)))
        self.assertEqual(rows[0]["date_pt"], "2026-10-05")
        self.assertEqual(rows[-1]["date_pt"], "2026-10-28")
        self.assertTrue(all(r["sources"] for r in rows))
        self.assertTrue(all(all(site.shipping_source(url) for url in r["sources"]) for r in rows))
        markup = site.shipping_28_view(rows)
        self.assertEqual(markup.count('class="shipping-summary"'), 25)
        self.assertIn("Day 1", markup)
        self.assertIn("Day 20", markup)
        self.assertIn("Day 21", markup)
        self.assertIn("Day 24", markup)
        self.assertIn("Day 25", markup)
        self.assertIn("Business Premium", markup)
        self.assertIn("米国のChatGPT Pro利用者", markup)
        self.assertIn('href="https://learn.chatgpt.com/docs/dots/channels"', markup)
        notices = json.loads((ROOT / "data/shipping-notices.json").read_text())
        with_notice = site.shipping_28_view(rows, notices)
        self.assertIn("ChatとWorkの統合は開発中", with_notice)
        self.assertIn("2026/10/29 08:35", with_notice)
        with self.assertRaises(ValueError):
            site.shipping_28_view(rows, [dict(notices[0], source="https://unapproved.example/news")])
        self.assertIn("OpenAIの28日間企画", markup)
        self.assertIn("新機能・改善・利用枠リセットの発表一覧", markup)
        self.assertIn("保存型リセット", markup)
        self.assertNotIn("全体への反映完了は本人の投稿で未確認", markup)
        for page in ("index", "about", "ship28"):
            html = site.shell("確認", "説明", page, "本文", "2026-10-25T00:00:00Z")
            self.assertIn('href="ship28.html"', html)
            self.assertIn("新機能・リセット", html)
            self.assertNotIn(">28日間の発表</a>", html)
        self.assertIn('<a href="ship28.html" aria-current=page>', site.shell("確認", "説明", "ship28", "本文", "2026-10-25T00:00:00Z"))
        bad = dict(rows[0], summary='<script>alert("x")</script>')
        safe = site.shipping_28_view([bad])
        self.assertNotIn('<script>alert', safe)
        self.assertIn('&lt;script&gt;', safe)

    def test_search_result_favicon_is_png_and_accessible_from_all_pages(self):
        import struct
        icon = ROOT / "docs/assets/favicon-96.png"
        data = icon.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (96, 96))
        for page in ("index", "about", "guide"):
            markup = site.shell("title", "description", page, "content", "2026-10-24T00:00:00Z")
            self.assertIn('<link rel="icon" href="assets/favicon-96.png" type="image/png" sizes="96x96">', markup)
            self.assertIn('<meta property="og:site_name" content="ChatGPT リセット履歴">', markup)
            self.assertNotIn('href="assets/icon.svg" type="image/svg+xml"', markup)

    def test_official_detection(self):
        body = "On Sep 3, 2026 and Sep 4, 2026 Plus Pro Business accounts got banked resets. On Sep 7, 2026 we provided an automatic reset."
        self.assertTrue(primary.official_verified(body))
        self.assertFalse(primary.official_verified("Sep 3, 2026 Sep 4, 2026 Sep 7, 2026"))

    def test_current_history_has_only_verified_primary_sources(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 56)
        self.assertTrue(all(primary.trusted(r) for r in rows))
        official = [r for r in rows if r["evidence"] == "official" and r["kind"] != "improvement"]
        indexed = [r for r in rows if r["evidence"] == "staff_x"]
        self.assertEqual(len(official), 3)
        self.assertTrue(all(r.get("date_precision") == "day" and "時刻の記載なし" in site.record_row(r) for r in official))
        self.assertTrue(all(r.get("verification_method", "").startswith(("X原投稿の検索結果表示", "X原投稿の埋め込み表示")) for r in indexed))
        self.assertTrue(all(r.get("original_url", "").startswith("https://x.com/thsottiaux/status/") for r in indexed))
        self.assertTrue(all("Tibo氏のX投稿" in site.record_row(r) for r in indexed))
        self.assertTrue(all(("全文未確認" in site.record_row(r)) == ("全文未確認" in r.get("verification_method", "")) for r in indexed))
        self.assertIn("Thibault Sottiaux", site.ABOUT)
        self.assertNotIn("OpenAI関係者のX原投稿", site.ABOUT)
        self.assertIn("Codex責任者Tibo氏", site.shell("確認", "説明", "about", "本文", "2026-10-20T12:00:00Z"))
        self.assertIn("リセットの記録", site.ABOUT)
        self.assertIn("実施の発表があれば、リセットとして掲載", site.ABOUT)
        self.assertIn("通常の回復予定", site.GUIDE)
        self.assertNotIn("一斉リセット", site.KINDS["global"])
        self.assertIn("臨時リセット", site.KINDS["global"])
        self.assertNotIn("対象サービス：", site.record_row(indexed[0]))
        self.assertNotIn("ページ更新：", site.shell("test", "desc", "index", "", "2026-10-20T12:00:00Z"))
        self.assertIn("これまでのリセット情報", site.homepage(rows, "2026-10-20T12:00:00Z", {"status":"stale","generated_at":"2026-10-20T12:00:00Z","horizons":{}}, []))

        self.assertNotIn("原投稿の検索表示で確認", site.record_row(indexed[0]))

    def test_site_title_and_public_labels_are_clear_to_searchers(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        output = site.shell("ChatGPT リセット履歴｜Codex・Workの利用枠リセット日と次回予想",
                            "ChatGPT Work・Codexの利用枠リセット履歴をカレンダーで確認。",
                            "index", "本文", "2026-10-24T00:00:00Z", show_forecast=False)
        self.assertIn("<title>ChatGPT リセット履歴｜", output)
        self.assertIn("canonical", output)
        self.assertNotIn("非公式", output)
        self.assertNotIn("unofficial", output)
        self.assertIn("ChatGPT リセット履歴", output)
        self.assertIn("利用枠リセット", output)
        self.assertNotIn("非公式", site.ABOUT)
        self.assertNotIn("非公式", site.GUIDE)
        self.assertNotIn("非公式", site.homepage(rows, "2026-10-24T00:00:00Z",
            {"status":"stale", "generated_at":"2026-10-24T00:00:00Z", "horizons":{}}, []))

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
                self.assertIn("forecast-unavailable", calendar)
                self.assertIn("次のリセット予想", homepage)
                self.assertNotIn('class="forecast-panel"', calendar)
                self.assertNotIn("次のリセット予測", homepage)
                self.assertNotIn("予測と結果", homepage)
                self.assertNotIn("data-health-url", homepage)
                self.assertNotIn("予想日</span>", calendar)
                self.assertIn("新しい予想日を掲載していません", homepage)
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
        self.assertEqual(site.record_title({"kind": "banked", "state": "announced"}), "リセットチケット")
        self.assertEqual(site.record_title({"kind": "banked", "state": "reported"}), "リセットチケット")
        self.assertEqual(site.record_title({"kind": "global", "state": "announced"}), "リセット")
        self.assertEqual(site.record_title({"kind": "global", "state": "reported"}), "リセット")

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
        self.assertIn("カレンダーの「リセット」は確認済みの発表日です", html)
        self.assertNotIn("リセット発表</span>", html)
        self.assertNotIn('>一斉</span>', html)

    def test_all_reset_days_have_the_same_label(self):
        import re
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        forecast = {"status":"stale","generated_at":"2026-10-24T01:00:00Z","horizons":{}}
        html = site.calendar_overview(rows, forecast)
        for date in ("2026-10-18", "2026-10-20", "2026-10-22", "2026-10-23"):
            cell = re.search(r'data-calendar-day="' + date + r'".*?</button>', html)
            self.assertIsNotNone(cell)
            self.assertIn('class="day-mark reset-mark">リセット</span>', cell.group(0))
            self.assertNotIn("announced-mark", cell.group(0))
        self.assertIn("カレンダーの「リセット」は確認済みの発表日です", html)
        self.assertIn('id="selected-date">10月28日の情報', html)
        self.assertIn("3件の投稿", html)
        self.assertNotIn("未実施という意味ではありません", html)
        self.assertIn("11:42｜リセットの発表", html)
        self.assertNotIn("14:21｜反映完了の報告", html)
        self.assertIn("実施の発表があれば、リセットとして掲載", site.ABOUT)
        self.assertNotIn("リセット完了報告", site.ABOUT)
        ticket = re.search(r'data-calendar-day="2026-10-08".*?</button>', html)
        self.assertIsNotNone(ticket)
        self.assertIn('class="day-mark banked-mark">チケット</span>', ticket.group(0))
        self.assertNotIn("配布予告", html)
        self.assertNotIn(">リセット発表</span>", html)

    def test_day21_announcement_is_confirmed_without_completion_condition(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        event = next(r for r in rows if r.get("post_id") == "2114588174249071102")
        self.assertEqual(event["state"], "announced")
        self.assertEqual(event["kind"], "global")
        self.assertEqual(site.jst(event["reference_at"]), "2026/10/26 14:21")
        self.assertIn("全文未確認", site.record_row(event))
        self.assertTrue(event["reset_confirmed"])
        self.assertNotIn("完了の報告ではありません", event["note"])
        self.assertEqual(event["original_url"], "https://x.com/thsottiaux/status/2114588174249071102")
        self.assertEqual(len(rows), len({r["id"] for r in rows}))
        shipping = json.loads((ROOT / "data/shipping-28.json").read_text(encoding="utf-8"))
        self.assertEqual(shipping[-1]["day"], 25)
        self.assertIn("Day 21", site.shipping_28_view(shipping))

    def test_day20_announcement_deadline_completion(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        ids = ["2114200152701575656", "2114200291319124163", "2114237083652882932"]
        matched = [next(r for r in rows if r.get("post_id") == x) for x in ids]
        self.assertEqual([r["state"] for r in matched], ["announced", "announced", "reported"])
        self.assertEqual([site.jst(r["reference_at"]) for r in matched],
                         ["2026/10/25 12:39", "2026/10/25 12:40", "2026/10/25 15:06"])
        self.assertTrue(all(site.record_day(r) == "2026-10-25" for r in matched))
        config = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))[0]
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-25T06:07:00Z"), config))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        archived = next(r for r in history if r.get("publication_run_id") == 40029830544)
        self.assertEqual(archived["published_at"], "2026-10-24T06:52:32+09:00")
        visible = site.previous_editorial_predictions(history)
        self.assertIn("判定：", visible)
        self.assertIn("15:06", visible)

    def test_october_28_editorial_prediction(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        config = next(r for r in json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8")) if r.get("forecast_id") == "2026-10-28-forecast-28")
        now = site.parse_time("2026-10-28T00:00:00Z")
        editorial = site.active_editorial_forecast(rows, now, config)
        self.assertIsNotNone(editorial)
        forecast = {"status": "stale", "generated_at": "2026-10-28T00:00:00Z", "horizons": {}}
        view = site.homepage(rows, "2026-10-28T00:00:00Z", forecast, [], editorial)
        self.assertIn("2026年10月28日（水）", view)
        self.assertIn('data-calendar-day="2026-10-28"', view)
        self.assertIn("当サイト独自", view)

    def test_editorial_prediction_auto_expires(self):
        from datetime import timedelta
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        config = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time(config["expires_at"]), config))
        moment = site.parse_time(config["created_at"]) + timedelta(hours=7)
        baseline = next(r for r in rows if r["id"] == config["last_report_id"])
        newer = {**baseline, "id": "new-reset:global", "reference_at": moment.isoformat(), "state": "announced"}
        self.assertIsNone(site.active_editorial_forecast([*rows, newer], moment, config))

    def test_expired_october_30_prediction_has_a_visible_status(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        previous = next(r for r in json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8")) if r.get("date") == "2026-10-30")
        now = site.parse_time("2026-10-31T00:00:00+09:00")
        forecast = {"status": "stale", "generated_at": now.isoformat(), "horizons": {}}
        self.assertIsNone(site.active_editorial_forecast(rows, now, previous))
        page = site.calendar_overview(rows, forecast, previous_editorial=previous)
        self.assertIn("次のリセット予想", page)
        self.assertIn("前回の予想：2026年10月30日", page)
        self.assertIn("新しい予想日を掲載していません", page)
        self.assertNotIn("予想日</span>", page)

    def test_expired_forecast_is_stored_without_falsely_declaring_a_miss(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        old = next(r for r in json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8")) if r.get("date") == "2026-10-30")
        health = {"feed": "failed", "x_status": "unavailable", "last_success_at": None}
        now = site.parse_time("2026-10-31T09:10:00+09:00")
        status, detail = site.editorial_result(old, rows, health, now)
        self.assertEqual(status, "確認中")
        self.assertIn("不十分", detail)
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        records = site.sync_editorial_history([old], current, rows, health, now, current)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["date"], "2026-10-30")
        self.assertEqual(records[0]["published_at"], old["published_at"])
        self.assertEqual(records[1]["date"], "2026-10-31")
        view = site.previous_editorial_predictions(records, current["forecast_id"])
        self.assertIn("2026年10月30日（金）", view)
        self.assertNotIn("2026年10月31日（土）", view)
        expired = site.sync_editorial_history(records, current, rows, health,
                    site.parse_time(current["expires_at"]), None)
        entry = next(x for x in expired if x.get("forecast_id") == current["forecast_id"])
        self.assertIn("retired_at", entry)
        self.assertIn("2026年10月31日（土）", site.previous_editorial_predictions(expired))

    def test_calendar_and_history_explain_apparent_reset_forecast_conflicts(self):
        import re
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        generated = current["created_at"]
        forecast = {"status": "stale", "generated_at": generated, "horizons": {}}
        page = site.homepage(rows, generated, forecast, [], None, history)
        self.assertIn("予想した10月23日にTibo氏がリセットを発表したため的中です", page)
        self.assertIn("10月22日にも別のリセット発表", page)
        self.assertIn("予想日の10月30日にはカレンダーに登録されたリセット発表がありません", page)
        self.assertIn("外れは運営者の確認による判定", page)
        self.assertIn('data-calendar-jump="2026-10-23"', page)
        self.assertIn('data-calendar-jump="2026-10-30"', page)
        self.assertNotIn('旧予想2', page)  # Oct 25 has only the hit, no duplicate prediction.
        self.assertIn("2026年10月25日（日）を予想", page)
        self.assertNotIn("2026/10/23 07:07", page)
        self.assertNotIn("2026年11月1日（日）を予想", page)
        serialized = re.search(r'<script id="calendar-data" type="application/json">(.*?)</script>', page, re.S)
        self.assertIsNotNone(serialized)
        data = json.loads(serialized.group(1))
        self.assertEqual(data["past_predictions"]["2026-10-23"][0]["status"], "的中")
        self.assertIn("10月22日", data["past_predictions"]["2026-10-23"][0]["note"])
        self.assertEqual(data["past_predictions"]["2026-10-30"][0]["status"], "外れ")
        self.assertIn("一次情報", data["past_predictions"]["2026-10-30"][0]["note"])
        self.assertEqual(len(data["past_predictions"]["2026-10-25"]), 1)
        self.assertEqual(data["past_predictions"]["2026-10-25"][0]["status"], "的中")
        self.assertNotIn("2026-11-01", data["past_predictions"])
        js = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("pastPredictions", js)
        self.assertIn("data-calendar-jump", js)
        self.assertIn("calendar-past-predictions", js)

    def test_calendar_prediction_marks_show_hit_miss_and_pending(self):
        import re
        records = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        now = site.parse_time(current["created_at"])
        live = site.active_editorial_forecast(records, now, current)
        self.assertIsNotNone(live)
        self.assertEqual(site.forecast_badge("的中"), ("予想◯", "forecast-hit-mark"))
        self.assertEqual(site.forecast_badge("外れ"), ("予想✕", "forecast-miss-mark"))
        self.assertEqual(site.forecast_badge("確認中"), ("予想？", "forecast-pending-mark"))
        forecast = {"status":"stale", "generated_at":now.isoformat(), "horizons":{}}
        output = site.calendar_overview(records, forecast, live, editorial_history=history)
        def date_cell(date):
            match = re.search(r'data-calendar-day="' + date + r'".*?</button>', output, re.S)
            self.assertIsNotNone(match)
            return match.group(0)
        self.assertIn('class="day-mark forecast-hit-mark">予想◯</span>', date_cell("2026-10-25"))
        self.assertIn('class="day-mark forecast-hit-mark">予想◯</span>', date_cell("2026-10-28"))
        self.assertIn('class="day-mark forecast-hit-mark">予想◯</span>', date_cell("2026-10-23"))
        self.assertIn('class="day-mark forecast-miss-mark">予想✕</span>', date_cell("2026-10-27"))
        self.assertIn('class="day-mark forecast-miss-mark">予想✕</span>', date_cell("2026-10-30"))
        self.assertIn('class="day-mark predicted-mark">予想中</span>', date_cell("2026-10-31"))
        self.assertNotIn("予想✕", date_cell("2026-10-25"))
        self.assertNotIn("予想◯", date_cell("2026-11-01") if 'data-calendar-day="2026-11-01"' in output else "")
        self.assertIn("予想◯：的中", output)
        self.assertIn("予想✕：外れ", output)
        self.assertIn("予想中：次回候補", output)
        self.assertIn('class="day-mark reset-mark">リセット</span>', date_cell("2026-10-23"))
        payload = re.search(r'<script id="calendar-data" type="application/json">(.*?)</script>', output, re.S)
        self.assertIsNotNone(payload)
        data = json.loads(payload.group(1))
        self.assertEqual(data["past_predictions"]["2026-10-25"][0]["mark"], "予想◯")
        self.assertEqual(data["past_predictions"]["2026-10-30"][0]["mark"], "予想✕")
        self.assertEqual(data["past_predictions"]["2026-10-23"][0]["mark_class"], "forecast-hit-mark")
        self.assertEqual(len(data["past_predictions"]["2026-10-25"]), 1)
        self.assertNotIn("2026-11-01", data["past_predictions"])
        js = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("item.mark_class", js)
        self.assertIn("item.mark", js)
        style = (ROOT / "docs/assets/style.css").read_text(encoding="utf-8")
        self.assertIn(".day-mark.forecast-hit-mark", style)
        self.assertIn(".day-mark.forecast-miss-mark", style)

    def test_october_25_retains_only_the_successful_prediction(self):
        entries = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        predicted = [r for r in entries if r.get("date") == "2026-10-25"]
        self.assertEqual(len(predicted), 1)
        self.assertEqual(predicted[0]["outcome_status"], "的中")
        self.assertEqual(predicted[0]["published_at"], "2026-10-24T06:52:32+09:00")
        self.assertNotIn("previous_same_day_forecast_id", predicted[0])
        self.assertFalse(any(r.get("published_at") == "2026-10-23T07:07:47+09:00" for r in entries))
        html = site.previous_editorial_predictions(entries)
        self.assertEqual(html.count("2026年10月25日（日）を予想"), 1)

    def test_owner_miss_and_october_31_forecast_have_no_unapproved_november_prediction(self):
        entries = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        oct30 = next(x for x in entries if x.get("forecast_id") == "2026-10-28-forecast-30")
        self.assertEqual(oct30["outcome_status"], "外れ")
        self.assertEqual(oct30["outcome_evidence"], "site_owner_report_2026-10-31")
        self.assertFalse(any(x.get("forecast_id") == "2026-10-31-forecast-1101" for x in entries))
        self.assertFalse(any(x.get("date") == "2026-11-01" for x in entries))
        html = site.previous_editorial_predictions(entries)
        self.assertIn("判定：<strong>外れ</strong>", html)
        self.assertNotIn("2026年11月1日", html)
        cfg = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["date"], "2026-10-31")
        self.assertEqual(cfg["published_at"], "2026-10-31T09:19:47+09:00")
        self.assertEqual(cfg["publication_run_id"], 41149540862)
        refreshed = site.sync_editorial_history(entries, cfg,
                   json.loads((ROOT / "data/events.json").read_text(encoding="utf-8")),
                   {"feed":"failed","x_status":"unavailable"}, site.parse_time(cfg["created_at"]), cfg)
        self.assertEqual(next(x for x in refreshed if x.get("forecast_id") == oct30["forecast_id"])["outcome_status"], "外れ")
        self.assertEqual(len(refreshed), len(entries))
        self.assertEqual(sum(x.get("forecast_id") == cfg["forecast_id"] for x in refreshed), 1)
        self.assertFalse(any(x.get("date") == "2026-11-01" for x in refreshed))

    def test_october_23_hit_keeps_original_prediction_and_verification_proof(self):
        entries = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        entry = next(item for item in entries if item.get("date") == "2026-10-23")
        self.assertEqual(entry["outcome_status"], "的中")
        self.assertEqual(entry["published_at"], "2026-10-20T23:17:07+09:00")
        self.assertIn("2113492187770175603", entry["verification_post_ids"])
        self.assertEqual(entry["previous_verdict"]["outcome_status"], "外れ")
        records = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        # The October 22 reset must not invalidate the predicted date.
        result, rationale = site.editorial_result(entry, records, {}, site.parse_time("2026-10-24T12:00:00+09:00"))
        self.assertEqual(result, "的中")
        self.assertIn("一致", rationale)

    def test_forecast_hit_and_miss_are_recorded_after_a_new_announcement(self):
        old = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        current = dict(old, published_at="2026-10-31T09:30:00+09:00")
        event = {"id": "new:global", "kind": "global", "state": "announced",
                 "evidence": "staff_x", "reference_at": "2026-10-31T12:00:00+09:00",
                 "date_precision": "minute"}
        now = site.parse_time("2026-11-01T12:00:00+09:00")
        status, detail = site.editorial_result(current, [event], {}, now)
        self.assertEqual(status, "的中")
        self.assertIn("一致", detail)
        # A reset announced before the prediction date must not prematurely fail it.
        event["reference_at"] = "2026-10-30T18:00:00+09:00"
        status, detail = site.editorial_result(current, [event], {}, site.parse_time("2026-10-31T18:00:00+09:00"))
        self.assertEqual(status, "予想中")
        # Even if an earlier reset happened, a reset on the target day still counts.
        same_day = dict(event, id="another:global", reference_at="2026-10-31T15:00:00+09:00")
        status, detail = site.editorial_result(current, [event, same_day], {}, now)
        self.assertEqual(status, "的中")
        # After the target day and with sufficient fresh source coverage, no target-day
        # event means a miss, even when another reset occurred on a different date.
        later = dict(event, reference_at="2026-11-01T12:00:00+09:00")
        health = {"last_success_at": "2026-11-02T12:00:00+09:00",
                  "feed": "ok", "x_status": "checked"}
        status, detail = site.editorial_result(current, [later], health, now)
        self.assertEqual(status, "外れ")
        self.assertIn("ありませんでした", detail)

    def test_browser_never_silently_hides_an_expired_editorial_prediction(self):
        script = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("forecastPanel.hidden = false", script)
        self.assertIn("前回の予想（結果を確認中）", script)

    def test_archived_october_23_prediction_shows_original_publication_time(self):
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        archived = site.previous_editorial_predictions(history)
        self.assertIn("以前の予想とその結果", archived)
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
        editorial = site.active_editorial_forecast(rows, site.parse_time("2026-10-26T00:00:00Z"), cfg)
        forecast = {"status":"stale", "generated_at":"2026-10-23T22:00:00Z", "horizons":{}}
        page = site.homepage(rows, "2026-10-23T22:00:00Z", forecast, [], editorial, history)
        self.assertIn("2026/10/20 23:17", page)
        self.assertNotIn("2026/10/23 07:07", page)
        self.assertIn("2026/10/24 06:52", page)
        self.assertIn("40029830544", page)
        self.assertIn("以前の予想とその結果", page)

    def test_new_day18_announcement_and_forecast_history(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        ids = {r.get("post_id") for r in rows}
        self.assertIn("2113492187770175603", ids)
        self.assertIn("2113492502355562875", ids)
        day18 = [r for r in rows if r.get("post_id") in {"2113492187770175603", "2113492502355562875"}]
        self.assertTrue(all(r["state"] == "announced" for r in day18))
        self.assertTrue(all(site.record_day(r) == "2026-10-23" for r in day18))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        self.assertTrue({"2026-10-23", "2026-10-25", "2026-10-27", "2026-10-28"}.issubset({r["date"] for r in history}))
        output = site.previous_editorial_predictions(history)
        self.assertNotIn("2026/10/23 07:07", output)
        self.assertIn("2026/10/20 23:17", output)
        self.assertIn("予想した理由", output)
        proposal = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-23T19:00:00Z"), proposal))

    def test_new_distinct_reset_notice_retires_prediction_without_losing_original_day(self):
        rows = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
        proposal = next(r for r in json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8")) if r.get("published_at") == "2026-10-20T23:17:07+09:00")
        self.assertEqual(proposal["date"], "2026-10-23")
        self.assertIsNotNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-21T00:00:00+09:00"), proposal))
        self.assertIsNone(site.active_editorial_forecast(rows, site.parse_time("2026-10-22T16:00:00+09:00"), proposal))


    def test_next_prediction_follows_october_28_reset_announcement(self):
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text(encoding="utf-8"))
        history = json.loads((ROOT / "data/editorial-forecast-history.json").read_text(encoding="utf-8"))
        self.assertEqual(current["date"], "2026-10-31")
        self.assertEqual(current["last_report_id"], "2115273064481218829:global")
        self.assertTrue(any(r["date"] == "2026-10-25" for r in history))
        self.assertIsNotNone(site.active_editorial_forecast(
            json.loads((ROOT / "data/events.json").read_text(encoding="utf-8")),
            site.parse_time(current["created_at"]), current))

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

class ResetEditorialPolicyTests(unittest.TestCase):
    def test_public_pages_and_exports_do_not_cast_announcements_as_uncertain(self):
        import re
        from unittest.mock import patch
        current = json.loads((ROOT / "data/editorial-forecast.json").read_text())
        with patch.object(site, "utcnow", return_value=current["created_at"]):
            site.build()
        bad = re.compile(r"(?:完了報告|反映完了)[^。<\n]{0,50}(?:未確認|未確定|ありません|限りません)|予告にすぎ")
        for path in (ROOT / 'docs').iterdir():
            if path.suffix in {'.html', '.xml', '.csv'}:
                self.assertIsNone(bad.search(path.read_text(encoding='utf-8-sig')), path.name)
        index = (ROOT / 'docs/index.html').read_text()
        self.assertIn('2026年10月31日（土）', index)
        self.assertIn('"predicted": "2026-10-31"', index)
        self.assertNotIn('2026年11月1日（日）を予想', index)
        self.assertNotIn('2026-10-31-forecast-1101', index)
        self.assertNotIn('新モデル提供', index)
        shipping = (ROOT / 'docs/ship28.html').read_text()
        self.assertIn('Day 22', shipping)
        self.assertIn('GPT-6.1 Terra', shipping)

class Day23Tests(unittest.TestCase):
    def test_day23_retires_published_prediction_and_keeps_original_publication(self):
        rows = json.loads((ROOT / 'data/events.json').read_text())
        config = next(r for r in json.loads((ROOT / 'data/editorial-forecast-history.json').read_text()) if r.get('forecast_id') == '2026-10-28-forecast-28')
        notices = [r for r in rows if r.get('post_id') in {'2115273064481218829', '2115273253711409208'}]
        self.assertEqual(len(notices), 2)
        self.assertTrue(all(r['reset_confirmed'] for r in notices))
        self.assertTrue(all(site.record_day(r) == '2026-10-28' for r in notices))
        now = site.parse_time('2026-10-28T05:00:00Z')
        self.assertIsNone(site.active_editorial_forecast(rows, now, config))
        self.assertEqual(config['published_at'], '2026-10-28T08:09:09+09:00')
        self.assertEqual(config['publication_run_id'], 40600057487)
        history = json.loads((ROOT / 'data/editorial-forecast-history.json').read_text())
        archived = next(r for r in history if r.get('forecast_id') == config['forecast_id'])
        self.assertIn('予想日と発表日が一致', archived['outcome'])
        self.assertEqual(archived['published_at'], config['published_at'])
