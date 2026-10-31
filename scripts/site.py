#!/usr/bin/env python3
"""Free, dependency-free collection and static publishing for Reset Log.

Upstream text is untrusted data. Never execute it, interpolate it into shell
commands, or treat its 'confirmed' flag as our own official verification.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import predict, update_history, scores

DATA = ROOT / "data"
OUT = ROOT / "docs"
REPO = "mtk-ctrl/ChatGPT-Codex-"
SITE_URL = os.environ.get("SITE_URL", "https://mtk-ctrl.github.io/ChatGPT-Codex-").rstrip("/")
OFFICIAL_URL = "https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex"
JST = timezone(timedelta(hours=9))
# 「チケット」は閲覧者向け表記。種類コード banked は変更しない。
KINDS = {"global": "臨時リセット", "banked": "リセットチケットの配布", "improvement": "新機能・改善"}
EVIDENCE = {"official": "OpenAI公式", "staff_x": "Tibo氏のX投稿"}


def source_name(record):
    """Reader-facing label based on the account named in the original URL."""
    if record["evidence"] == "official":
        return "OpenAI公式"
    original = record.get("original_url") or ""
    if re.search(r"https://(?:x\.com|twitter\.com)/OpenAI/status/", original, re.I):
        return "OpenAI公式X"
    if re.search(r"https://(?:x\.com|twitter\.com)/thsottiaux/status/", original, re.I):
        return "Tibo氏のX投稿"
    return "OpenAI担当者のX投稿"


def source_link_text(record):
    return "公式発表を見る" if record["evidence"] == "official" else "Xの投稿を見る"

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError("missing or invalid timestamp")
    value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed.astimezone(timezone.utc)


def jst(value, short=False):
    dt = parse_time(value).astimezone(JST)
    return dt.strftime("%m/%d %H:%M" if short else "%Y/%m/%d %H:%M")


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)
    return True


def safe_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return None
    try:
        u = urllib.parse.urlsplit(value)
        if u.scheme != "https" or u.username or u.password or u.port:
            return None
        if u.hostname not in {"x.com", "twitter.com", "help.openai.com", "openai.com", "learn.chatgpt.com"}:
            return None
        if any(ord(c) < 32 for c in value):
            return None
        return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "", ""))
    except ValueError:
        return None


def record_day(record):
    if record.get("date_precision") == "day":
        return record["official_date"]
    return parse_time(record["reference_at"]).astimezone(JST).strftime("%Y-%m-%d")


def record_clock(record):
    if record.get("date_precision") == "day":
        return "時刻の記載なし"
    return "投稿 " + jst(record["reference_at"], short=True)[-5:]

def fetch(url, max_bytes=2_000_000):
    error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": f"ResetLog/1.0 (+https://github.com/{REPO})",
                "Accept": "application/json,text/html;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=18) as response:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("response too large")
                return body.decode("utf-8")
        except (urllib.error.URLError, TimeoutError, UnicodeError, ValueError, OSError) as exc:
            error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {429, 500, 502, 503, 504}:
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"source fetch failed: {type(error).__name__}") from error


def collect(input_file=None, github_output=None):
    from primary import collect_primary
    return collect_primary(DATA, fetch, read_json, write_json, utcnow,
                           github_output=github_output, input_file=input_file)

def e(value):
    return html.escape(str(value), quote=True)


def link(url, text, cls=""):
    checked = safe_url(url)
    return f'<a class="{e(cls)}" href="{e(checked)}" target="_blank" rel="noopener noreferrer">{e(text)} ↗</a>' if checked else ""


def shell(title, description, active, content, updated, show_forecast=True):
    canonical = SITE_URL + ("/" if active == "index" else f"/{active}.html")
    nav = "".join(f'<a href="{href}" {"aria-current=page" if active == key else ""}>{label}</a>' for key, href, label in [("index", "./", "リセット履歴"), ("ship28", "ship28.html", "新機能・リセット"), ("guide", "guide.html", "リセットの種類"), ("forecast", "forecast.html", "予想の考え方"), ("about", "about.html", "このサイトについて")] if key != "forecast" or show_forecast)
    website = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "ChatGPT リセット履歴", "url": SITE_URL + "/", "inLanguage": "ja"}, ensure_ascii=False).replace("<", "\\u003c")
    brand_tag = "h1" if active == "index" else "div"
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="google-site-verification" content="QsHiUSX9S7lXfH6K66Zll2IPVzwI-QLe--FDzPFsWpE">
<title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta name="theme-color" content="#245e9b"><meta property="og:site_name" content="ChatGPT リセット履歴"><link rel="icon" href="assets/favicon-96.png" type="image/png" sizes="96x96"><link rel="stylesheet" href="assets/style.css"><link rel="alternate" type="application/rss+xml" title="ChatGPT リセット履歴 更新情報" href="feed.xml"><link rel="sitemap" type="application/xml" href="sitemap.xml">
<script type="application/ld+json">{website}</script><script defer src="assets/app.js"></script><script defer src="assets/counter.js"></script></head>
<body><a class="skip" href="#main">本文へ移動</a><header class="site-header container"><div class="masthead"><div><div class="brand-line"><{brand_tag} class="brand"><a href="./">ChatGPT リセット履歴</a></{brand_tag}></div><p class="site-subtitle">Codex・ChatGPT Workの利用枠リセット・次回予想</p></div><p class="site-description">Codex・ChatGPT Workの利用枠が特別に回復した日や、次回の予想を確認できます。Tibo氏やOpenAIが実施を発表したリセットを掲載しています。</p></div><nav class="main-nav" aria-label="メインナビゲーション">{nav}</nav></header>
<main id="main" class="container">{content}</main>
<footer class="container site-footer"><p class="footer-title">ChatGPT リセット履歴</p><p>情報源：OpenAIの発表と、Codex責任者Tibo氏などのX投稿。</p><p class="footer-links"><a href="about.html">掲載情報について</a><a href="https://github.com/{REPO}/issues">訂正の連絡</a><a href="data.csv">履歴データ（CSV）</a><a href="feed.xml">RSS</a></p></footer></body></html>'''


def record_title(record):
    # Show the same name for a reset whether the source post was a notice or a completion.
    return {"global": "リセット", "banked": "リセットチケット", "improvement": "新機能・改善"}[record["kind"]]


def date_label(value):
    date = parse_time(value).astimezone(JST)
    return f"{date.year}年{date.month}月{date.day}日 {date:%H:%M}"


def record_row(record):
    proof = record.get("official_confirmation")
    source_url = proof["url"] if proof else record.get("original_url")
    source = link(source_url, source_link_text(record))
    # Broad product tags classify the archive; they do not verify every post's eligibility.
    # Leave the exact target to the announcement text and original source.
    target = ""
    note = f'<details class="record-more"><summary>発表内容を詳しく読む</summary><p>{e(record["note"])}</p></details>' if record.get("note") else ""
    verification_notice = '<small class="source-unverified">全文未確認</small>' if "全文未確認" in record.get("verification_method", "") else ""
    day = record_day(record)
    stamp = day if record.get("date_precision") == "day" else record["reference_at"]
    clock = record_clock(record)
    return f'''<tr id="r-{e(record['id'].replace(':', '-'))}" data-record data-kind="{record['kind']}" data-evidence="{record['evidence']}" data-month="{day[:7]}">
<td class="record-date" data-label="日時"><time datetime="{e(stamp)}"><span>{e(day.replace("-", "/"))}</span><span class="record-clock">{e(clock)}</span></time></td>
<td class="record-content" data-label="発表内容"><strong class="record-title">{e(record_title(record))}</strong>{target}{note}</td>
<td class="record-evidence" data-label="発表した人・組織"><span class="badge {record['evidence']}">{e(source_name(record))}</span>{verification_notice}</td>
<td class="record-source" data-label="発表を確認"><div class="source-links">{source}</div></td></tr>'''


DISCLAIMER = ("この予測は当サイト独自の試算であり、OpenAIが発表した予定ではありません。"
              "的中を保証するものではなく、予測に基づく判断について責任を負いません"
              "（法令上、免責が認められない場合を除きます）。")



def active_editorial_forecast(records, now, proposal):
    """A clearly labelled opinion. Remove it when a new reset is reported or it expires."""
    if not isinstance(proposal, dict) or not proposal.get("date") or not proposal.get("expires_at"):
        return None
    baseline = next((r for r in records if r.get("id") == proposal.get("last_report_id")
                     and r.get("kind") == "global" and r.get("state") in {"announced", "reported", "observed"}), None)
    if (baseline is None or now >= parse_time(proposal["expires_at"])
            or (proposal.get("created_at") and now < parse_time(proposal["created_at"]))):
        return None
    reference_time = parse_time(baseline["reference_at"])
    baseline_time = max(reference_time, parse_time(proposal.get("ignore_reports_before", baseline["reference_at"])))
    for r in records:
        if r.get("id") == baseline["id"] or r.get("kind") != "global":
            continue
        if r.get("state") == "announced":
            if r.get("date_precision") != "day":
                notice_time = parse_time(r["reference_at"])
                # A separate announcement, not an immediate correction in the same thread.
                if reference_time + timedelta(hours=6) < notice_time <= now:
                    return None
            continue
        if r.get("state") not in {"reported", "observed"}:
            continue
        if r.get("date_precision") == "day":
            if r.get("official_date", "") > record_day(baseline):
                return None
        elif baseline_time < parse_time(r["reference_at"]) <= now:
            return None
    return proposal



def publication_timestamp_markup(record):
    """A website deployment completion time, not the time an opinion was discussed."""
    value = record.get("published_at")
    if not value:
        return ""
    # The URL is constructed only from the fixed owner/repository and a numeric run ID.
    run_id = record.get("publication_run_id")
    proof = (
        f'<a href="https://github.com/{REPO}/actions/runs/{run_id}" target="_blank" rel="noopener noreferrer">公開記録を見る ↗</a>'
        if isinstance(run_id, int) and not isinstance(run_id, bool) and 0 < run_id < 10**18 else ""
    )
    return f'<span class="prediction-publication"><time datetime="{e(value)}">{e(jst(value))}</time>（日本時間） {proof}</span>'


def editorial_result(entry, records, health, now):
    """Compare with the first independent, verified reset announcement after publication."""
    if not entry.get("published_at"):
        return "確認中", "初回のサイト公開日時を確認中です。"
    try:
        published = parse_time(entry["published_at"])
        cutoff = parse_time(entry["expires_at"])
        target = entry["date"]
    except (ValueError, KeyError, TypeError):
        return "確認中", "予想日と公開日時を確認中です。"
    baseline = next((r for r in records if r.get("id") == entry.get("last_report_id")), None)
    if baseline:
        published = max(published, parse_time(baseline["reference_at"]) + timedelta(hours=6))
    later = []
    for event in records:
        if (event.get("kind") != "global" or event.get("state") not in {"announced", "reported", "observed"}
                or event.get("evidence") not in {"official", "staff_x"}
                or event.get("date_precision") == "day"):
            continue
        try:
            stamp = parse_time(event["reference_at"])
        except (ValueError, KeyError, TypeError):
            continue
        if published < stamp <= now:
            later.append(stamp)
    if later:
        first_day = min(later).astimezone(JST).date().isoformat()
        label = f"{int(first_day[5:7])}月{int(first_day[8:])}日"
        if first_day == target:
            return "的中", f"次のリセット発表日（{label}）と予想日が一致しました。"
        return "外れ", f"次のリセット発表は{label}で、予想日とは異なりました。"
    if now < cutoff:
        return "予想中", "予想日がまだ終了していません。"
    try:
        checked = parse_time(health["last_success_at"])
    except (ValueError, KeyError, TypeError):
        checked = None
    if (checked and checked >= cutoff and health.get("feed") == "ok"
            and health.get("x_status") == "checked"):
        return "外れ", "確認できた一次情報では、予想日までに次のリセット発表はありませんでした。"
    return "確認中", "予想日は終了しましたが、一次情報が不十分なため結果を判定できません。"


def sync_editorial_history(history, proposal, records, health, now, active):
    """Save every forecast at first build, then update its result without erasing evidence."""
    items = [dict(item) for item in history]
    if isinstance(proposal, dict) and proposal.get("forecast_id"):
        current = next((item for item in items if item.get("forecast_id") == proposal["forecast_id"]), None)
        if current is None:
            current = dict(proposal)
            items.append(current)
        elif proposal.get("published_at") and not current.get("published_at"):
            current["published_at"] = proposal["published_at"]
            if proposal.get("publication_run_id"):
                current["publication_run_id"] = proposal["publication_run_id"]
    for item in items:
        if item.get("outcome"):
            continue
        state, detail = editorial_result(item, records, health, now)
        if state != "予想中" or item.get("outcome_status"):
            item["outcome_status"] = state
            item["outcome_detail"] = detail
        if (isinstance(proposal, dict) and active is None
                and item.get("forecast_id") == proposal.get("forecast_id")
                and not item.get("retired_at")):
            item["retired_at"] = now.isoformat(timespec="seconds")
            item["retired_reason"] = "予想終了後も結果検証のため履歴に保存。"
    return items


def previous_editorial_predictions(history, current_forecast_id=None):
    """Display an immutable public audit trail of old editorial dates."""
    if not history:
        return ""
    items = []
    for record in sorted(history, key=lambda r: r.get("published_at") or r.get("created_at", ""), reverse=True):
        if not record.get("date") or (current_forecast_id and record.get("forecast_id") == current_forecast_id):
            continue
        date = datetime.strptime(record["date"], "%Y-%m-%d")
        weekday = "月火水木金土日"[date.weekday()]
        rationale = f'<details class="previous-prediction-reason"><summary>予想した理由</summary><p>{e(record["rationale"])}</p></details>' if record.get("rationale") else ""
        label = "事後確認" if record.get("outcome") else record.get("outcome_status", "確認中")
        detail = record.get("outcome") or record.get("outcome_detail") or record.get("retired_reason") or "一次情報を確認中です。"
        outcome = f'<p>判定：<strong>{e(label)}</strong> — {e(detail)}</p>'
        publication = publication_timestamp_markup(record) or "公開日時を確認中"
        items.append(f'''<li><strong>{date.year}年{date.month}月{date.day}日（{weekday}）を予想</strong>
<p>サイト公開：{publication}</p>{outcome}{rationale}</li>''')
    if not items:
        return ""
    return f'''<section class="previous-predictions" aria-labelledby="previous-predictions-title"><h2 id="previous-predictions-title">以前の予想とその結果</h2>
<p class="previous-predictions-intro">予想した日と公開した時刻を記録しています。</p>
<ol>{"".join(items)}</ol></section>'''


def calendar_overview(records, forecast, editorial=None, previous_editorial=None):
    records = [r for r in records if r["kind"] in {"global", "banked"}]
    today = parse_time(forecast['generated_at']).astimezone(JST).date()
    entries = []
    for r in records:
        day = record_day(r)
        sources = [(r.get('official_confirmation') or {}).get('url'), r.get('original_url')]
        entries.append({'day': day, 'time': record_clock(r),
                        'id': 'r-' + r['id'].replace(':', '-'), 'kind': r['kind'], 'state': r['state'],
                        'title': record_title(r), 'evidence': source_name(r), 'note': r.get('note', ''),
                        'sources': [{'url': safe_url(url), 'label': label} for url, label in zip(sources, ['公式発表を見る', 'Xの投稿を見る']) if safe_url(url)]})
    selected = next((r['day'] for r in entries if r['kind'] == 'global'), today.isoformat())
    if not selected.startswith(today.strftime('%Y-%m')):
        selected = today.isoformat()
    predicted = editorial["date"] if editorial else (forecast.get("reference_date") if forecast["status"] == "ok" else None)
    by_day = {}
    for r in entries:
        by_day.setdefault(r['day'], []).append(r)
    def cell(day):
        if not day:
            return '<div class="calendar-empty" aria-hidden="true"></div>'
        key = f'{today.year}-{today.month:02d}-{day:02d}'
        day_records = by_day.get(key, [])
        marks = []
        if any(r['kind'] == 'global' for r in day_records):
            marks.append('<span class="day-mark reset-mark">リセット</span>')
        if any(r['kind'] == 'banked' for r in day_records):
            marks.append('<span class="day-mark banked-mark">チケット</span>')
        if key == predicted:
            marks.append('<span class="day-mark predicted-mark">予想</span>')
        classes = 'calendar-day' + (' is-today' if key == today.isoformat() else '')
        label = f'{today.year}年{today.month}月{day}日、発表記録{len(day_records)}件' + ('、予想日' if key == predicted else '')
        return f'<button type="button" class="{classes}" data-calendar-day="{key}" aria-label="{e(label)}" aria-pressed="{str(key == selected).lower()}"><span class="day-number">{day}</span><span class="day-marks">{"".join(marks)}</span></button>'
    grid = ''.join(cell(day) for week in calendar.Calendar(firstweekday=6).monthdayscalendar(today.year, today.month) for day in week)
    first = min(r['day'] for r in entries)[:7]
    end_month = today.year * 12 + today.month - 1 + 3
    last = f'{end_month // 12}-{end_month % 12 + 1:02d}'
    month_options = []
    for index in range(int(first[:4])*12 + int(first[5:])-1, end_month + 1):
        year, month = index // 12, index % 12 + 1
        value = f'{year}-{month:02d}'
        month_options.append(f'<option value="{value}" {"selected" if value == today.strftime("%Y-%m") else ""}>{year}年{month}月</option>')
    day_records = by_day.get(selected, [])
    cards = []
    for kind in ("global", "banked"):
        posted = [r for r in day_records if r["kind"] == kind]
        if not posted:
            continue
        title = "リセット" if kind == "global" else "リセットチケット"
        urls = []
        for r in posted:
            for source in r["sources"]:
                if source["url"] not in urls:
                    urls.append(source["url"])
        buttons = "".join(link(src["url"], f'{r["time"]}｜' + ("リセットの発表" if kind == "global" else "チケット配布の発表") + "（Xの投稿）") for r in sorted(posted, key=lambda item: item["time"]) for src in r["sources"] if src["url"] == r["sources"][-1]["url"])
        cards.append(f'<article class="day-record"><h4>{title}</h4><p class="day-posts">{len(posted)}件の投稿</p><p class="day-source">{buttons}</p></article>')
    details = "".join(cards) or '<p class="empty-day">この日の情報はありません。</p>'
    payload = json.dumps({'today':today.isoformat(), 'selected':selected, 'first':first, 'last':last, 'predicted':predicted, 'records':entries}, ensure_ascii=False).replace('<', '\\u003c')
    if forecast['status'] == 'ok':
        h24, h48 = forecast['horizons']['24'], forecast['horizons']['48']
        lower, upper = h24['observed_ratio_interval']
        date = datetime.strptime(forecast["reference_date"], "%Y-%m-%d")
        prediction = f'''<div class="forecast-numbers"><div><span>24時間以内</span><strong>{h24['display_percent']}<small>%</small></strong></div><div><span>48時間以内</span><strong>{h48['display_percent']}<small>%</small></strong></div></div>
<p class="forecast-caption">過去のリセット発表の間隔から計算</p>
<p class="reference-date">参考日 <strong>{date.month}月{date.day}日ごろ</strong><span>実施予定日ではありません</span></p>
<details class="forecast-reasons" open><summary>なぜこの予測？</summary><p>前回のリセット発表から<strong>{forecast['elapsed_hours']/24:.1f}日</strong>経過しています。直近90日間に始まった実施間隔<strong>{forecast['sample_size']}件</strong>のうち、これより長かったのは<strong>{forecast['eligible_size']}件</strong>でした。</p><p>その{h24['total']}件では、現在と同じ経過時点から24時間以内の報告が{h24['count']}件、48時間以内が{h48['count']}件でした。この比率を補正して上の数値を出しています。</p><p class="sample-note">少数の履歴による試算です。24時間の集計比率の95%参考区間は{lower}〜{upper}%と幅があり、予測精度はまだ検証できていません。</p></details>'''
    else:
        prediction = ""
    if editorial:
        target_day = datetime.strptime(editorial["date"], "%Y-%m-%d")
        weekday = "月火水木金土日"[target_day.weekday()]
        basis = "・".join(f"{int(d[-2:])}日" for d in editorial.get("supporting_event_dates", editorial.get("supporting_report_dates", [])))
        forecast_panel = f'''<aside class="forecast-panel forecast-editorial" aria-labelledby="forecast-title" data-editorial-expires-at="{e(editorial["expires_at"])}"><div class="forecast-heading"><h2 id="forecast-title">次のリセット予想</h2><span>独自予想</span></div>
<p class="editorial-date">{target_day.year}年{target_day.month}月{target_day.day}日（{weekday}）</p>
<p class="editorial-reason-title">{target_day.month}月{target_day.day}日と予想する理由</p>
<p class="editorial-reason">{e(editorial["rationale"])}</p>
<p class="editorial-caution">{e(editorial["caution"])}</p>
<p class="editorial-written">予想の公開日時：{publication_timestamp_markup(editorial) or "確認中"}</p></aside>'''
    elif forecast["status"] == "ok":
        forecast_panel = f'''<aside class="forecast-panel" aria-labelledby="forecast-title"><div class="forecast-heading"><h2 id="forecast-title">次のリセット予測</h2><span>当サイト独自の試算</span></div><div id="forecast-current" data-generated-at="{forecast['generated_at']}">{prediction}</div><p class="forecast-updated">予測の計算日時：{e(jst(forecast["generated_at"]))}（日本時間）</p><a class="method-link" href="forecast.html">計算方法と検証について →</a><p class="forecast-disclaimer">{DISCLAIMER}</p></aside>'''
    else:
        reason = ("一次情報の自動確認ができていないため" if forecast.get("status") == "stale"
                  else "予想に使える確認済みの履歴が十分でないため")
        previous_label = ""
        if previous_editorial and previous_editorial.get("date"):
            date = datetime.strptime(previous_editorial["date"], "%Y-%m-%d")
            previous_label = f'<p class="editorial-reason">前回の予想：{date.year}年{date.month}月{date.day}日。予想期限を過ぎたため、次回予想としての表示は終了しました。公開時の記録は下の「以前の予想とその結果」に残しています。</p>'
        forecast_panel = f'''<aside class="forecast-panel forecast-unavailable" aria-labelledby="forecast-title"><div class="forecast-heading"><h2 id="forecast-title">次のリセット予想</h2><span>更新を確認中</span></div>
<p class="editorial-reason">{reason}、新しい予想日を掲載していません。未確認を「リセットなし」とは判断していません。</p>{previous_label}
<p class="editorial-caution">当サイトの予想はOpenAIの発表予定ではありません。一次情報を確認してから更新します。</p></aside>'''
    layout_class = "calendar-layout" if forecast_panel else "calendar-layout calendar-layout--full"
    prediction_legend = '<span><i class="legend-predicted"></i>予想日</span>' if editorial or forecast["status"] == "ok" else ""
    return f'''<div class="{layout_class}"><section class="calendar-section" aria-labelledby="calendar-title"><div class="calendar-section-heading"><h2 id="calendar-title">リセットカレンダー</h2></div><div class="calendar-controls"><div><button id="calendar-prev" type="button" aria-label="前の月">‹</button><label class="sr-only" for="calendar-month">カレンダーの年月</label><select id="calendar-month">{''.join(month_options)}</select><button id="calendar-next" type="button" aria-label="次の月">›</button></div><button id="calendar-today" type="button">今月</button></div><div class="calendar-weekdays" aria-hidden="true"><span>日</span><span>月</span><span>火</span><span>水</span><span>木</span><span>金</span><span>土</span></div><div id="calendar-grid" class="calendar-grid" role="group" aria-label="{today.year}年{today.month}月">{grid}</div><div class="calendar-legend"><span><i class="legend-reset"></i>リセット</span><span><i class="legend-banked"></i>リセットチケット</span>{prediction_legend}</div><p class="calendar-status-explainer">※リセット実施の発表があった日を、日本時間で表示しています。</p><section class="selected-day" aria-live="polite" aria-atomic="true"><h3 id="selected-date">{int(selected[5:7])}月{int(selected[8:])}日の情報</h3><div id="selected-records">{details}</div></section><noscript><p>月の切り替えにはJavaScriptが必要です。全履歴は下の一覧から確認できます。</p></noscript></section>
{forecast_panel}</div><script id="calendar-data" type="application/json">{payload}</script>'''


def forecast_results(history):
    if not any(any(outcome is not None for outcome in record.get("outcomes", {}).values()) for record in history):
        return ""
    score = scores(history)['24']
    judged = score['judged']
    status = f'{judged}件を判定済み ／ 24時間予測の誤差スコア {score["brier"]:.3f}' if judged else '検証前'
    rows = []
    for entry in reversed(history[-7:]):
        outcomes = []
        for h in ['24', '48']:
            value = entry.get('outcomes', {}).get(h)
            outcomes.append('判定待ち' if value is None else ('記録あり' if value else '記録なし'))
        percentages = [int((entry['probabilities'][h]*20 + 0.5)//1)*5 for h in ['24','48']]
        rows.append(f'<tr><th scope="row">{e(jst(entry["issued_at"]))}</th><td>{percentages[0]}% <span>{outcomes[0]}</span></td><td>{percentages[1]}% <span>{outcomes[1]}</span></td></tr>')
    body = '<div class="forecast-table-wrap"><table class="forecast-table"><thead><tr><th scope="col">予測の保存日時（日本時間）</th><th scope="col">24時間以内</th><th scope="col">48時間以内</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>' if rows else '<p>最初の予測を保存してから、結果を掲載します。</p>'
    return f'<section class="forecast-results" aria-labelledby="forecast-results-title"><div class="section-heading"><h2 id="forecast-results-title">予測と結果</h2><p>{status}</p></div><p class="results-description">予測を公開したあと、24時間・48時間以内に次のリセット報告があったかを確認します。公開済みの予測値はあとから変更しません。</p>{body}<p class="results-note">直近7日分を掲載。判定待ち・取得遅延を含みます。履歴の追加・訂正により結果が変わる場合があります。<a href="https://github.com/{REPO}/blob/main/data/forecast-history.json">すべての予測記録</a></p></section>'


def homepage(records, updated, forecast, forecast_history, editorial=None, editorial_history=None, previous_editorial=None):
    records = [r for r in records if r["kind"] in {"global", "banked"}]
    months = sorted({record_day(r)[:7] for r in records}, reverse=True)
    options = "".join(f'<option value="{m}">{m[:4]}年{int(m[5:])}月</option>' for m in months)
    rows = []
    current_month = None
    for record in records:
        month = record_day(record)[:7]
        if month != current_month:
            rows.append(f'<tr class="month-heading" id="month-{month}" data-month-heading="{month}"><th scope="rowgroup" colspan="4">{month[:4]}年{int(month[5:])}月</th></tr>')
            current_month = month
        rows.append(record_row(record))
    evidence_tabs = "".join(f'<button type="button" data-evidence-option="{key}" aria-pressed="{str(key == "all").lower()}">{label}</button>' for key, label in [("all", "すべて"), ("official", "公式サイト"), ("staff_x", "Xの投稿")])
    return f'''{calendar_overview(records, forecast, editorial, previous_editorial)}
{previous_editorial_predictions(editorial_history, editorial.get("forecast_id") if editorial else None)}
{forecast_results(forecast_history)}
<section id="history" class="history-section"><div class="section-heading"><h2 class="section-title">これまでのリセット情報</h2><p>{len(records)}件</p></div>
<form id="filters" aria-label="履歴の絞り込み"><input type="hidden" id="evidence-filter" value="all"><div class="filter-primary"><div class="evidence-tabs" role="group" aria-label="発表元で絞り込む">{evidence_tabs}</div><label class="search-label"><span class="sr-only">キーワード</span><input id="search-filter" type="search" placeholder="キーワードで検索" autocomplete="off"></label></div><div class="filter-secondary"><label for="kind-filter">種類</label><select id="kind-filter"><option value="all">すべて</option><option value="global">臨時リセット</option><option value="banked">リセットチケット</option></select><label for="month-filter">年月</label><select id="month-filter"><option value="all">すべての月</option>{options}</select><button class="reset-filter" type="reset">条件を解除</button></div></form>
<p class="archive-explainer">発表を1件ずつ記録しています。同じ日に複数の発表がある場合もあります。</p>
<p id="result-count" class="result-count" aria-live="polite">{len(records)}件の記録を表示</p><div class="table-wrap"><table><caption class="sr-only">ChatGPT Work・Codexの臨時リセット履歴</caption><thead><tr><th scope="col">発表日時（日本時間）</th><th scope="col">どんな発表？</th><th scope="col">発表した人・組織</th><th scope="col">詳しく見る</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p id="no-results" hidden>条件に一致する履歴はありません。</p><noscript><p>絞り込みにはJavaScriptが必要です。以下に全履歴を掲載しています。</p></noscript></section>
<section class="related-guide"><h2>自分の利用枠は？</h2><p>残りの利用枠や通常の回復予定はChatGPTの「使用状況」で確認できます。</p><a href="guide.html">リセットの種類を見る →</a></section>'''


FORECAST_METHOD = f'''<article class="article"><h1 class="section-title">次回予想の考え方</h1><p class="article-lead">過去のリセット間隔に基づく、当サイト独自の試算です。</p>
<h2>何を予測するのか</h2><p>臨時リセットの発表が、計算時点から24時間・48時間以内に記録される可能性を試算します。判定には出典の参考時刻を使うため、履歴を取得した時刻や実際に利用枠が回復した時刻を予測するものではありません。</p><p>OpenAIの運用方針や内部情報を知るものではありません。実施の発表も集計し、同じリセットについて6時間以内に続く補足・完了報告はまとめます。リセットチケットの配布は別に扱います。</p>
<h2>計算の手順</h2><ol class="method-steps"><li>保存済みの臨時リセットの実施発表を、参考時刻の順に並べます。同じ記録ID・同じ時刻の重複と未来の時刻を除外します。</li><li>連続する報告の間隔を求め、その始まりが計算時点から90日以内のものを使います。</li><li>前回の報告から現在までの経過時間を求めます。過去の間隔のうち、この経過時間より長いものだけを選びます。</li><li>選んだ間隔のうち、現在と同じ経過時点から24時間・48時間以内に次の報告があった件数を数えます。</li><li>少数の記録で0%や100%になりにくいよう、次の式で補正します。表示は5ポイント単位に丸めます。</li></ol>
<p class="formula">予測値 ＝（該当件数 ＋ 1）÷（選んだ間隔の件数 ＋ 2）</p><p>これはラプラス補正を加えた条件付きの集計です。例えば、選んだ10件のうち3件が24時間以内なら、（3＋1）÷（10＋2）で約33%、表示は35%になります。</p>
<h2>カレンダーの参考日</h2><p>選んだ間隔の中央値を前回の報告時刻に足し、日本時間の日付に換算します。次回の実施予定日や、最も起こりやすい日を示すものではありません。カレンダーでは履歴とは異なる破線で表示します。</p>
<h2>数値を表示しない場合</h2><p>過去の間隔が6件未満、または経過時間による絞り込み後が5件未満の場合は、集計不足として表示しません。履歴の取得に失敗している場合や、最終成功から24時間以上経過した場合も予測を休止します。閲覧中の予測も、計算から24時間を超えた場合は数値を隠します。</p>
<h2>この方法の限界</h2><p>リセットの間隔が一定だという根拠はありません。障害、モデルの公開、キャンペーン、OpenAIの方針変更などで頻度は変わります。「しばらく来ていないから、そろそろ来る」とは限りません。</p><p>集計にはOpenAIの公式発表や担当者本人の投稿から確認した記録のみを使い、日付しかない記録は時間間隔の予測から除きます。Xの取得制限による記録漏れも予測に影響します。まだ終了していない現在の間隔は過去の標本に含めておらず、長い間隔が集計に入りにくい偏りもあります。90日という期間や最低件数は、実装上の設定であり、精度が実証された値ではありません。</p><p>「95%参考区間」は、集計した比率に対するウィルソン区間です。少数の記録による幅を示すために掲載しており、次回のリセットが95%の確率でその範囲に収まるという意味ではありません。</p>
<h2>予測を保存して結果を確認する</h2><p>日本時間の各日で最初に公開用の処理が成功した予測を保存します。保存済みの予測値と計算時点は変更せず、24・48時間が経過し、その期限以降に履歴の取得が成功してから結果を判定します。期間内にリセット発表の参考時刻があれば「記録あり」、なければ「記録なし」です。取得の遅延や後日の訂正で結果が変わる場合があります。</p><p>判定済みの結果がない間は「検証前」と表示します。結果がある場合は、24時間予測の平均二乗誤差（Brierスコア、0〜1）を掲載します。0に近いほど誤差が小さい指標で、正解率ではありません。毎日の予測は互いに独立した試行ではないため、単純な件数だけで精度を判断することもできません。</p><p>導入前の予測や的中実績は作成していません。<a href="https://github.com/{REPO}/blob/main/data/forecast-history.json">保存された予測記録</a>と<a href="forecast.json">現在の計算結果（JSON）</a>を公開します。計算式を変更する場合は、記録に残すモデルIDも変更します。</p>
<h2>情報源について</h2><p>計算にはOpenAIの公式発表と、Codex責任者Tibo氏などのX投稿を使用します。新しい発表を十分に確認できない場合は、予測を表示しません。<a href="about.html">掲載情報について</a>もご覧ください。</p>

<h2>予測を見る際の注意</h2><p class="method-disclaimer">{DISCLAIMER}</p><p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''


def shipping_source(url):
    return bool(re.fullmatch(r"https://x\.com/(?:thsottiaux|OpenAI|ChatGPT)/status/\d{12,24}", url)
                or url == "https://learn.chatgpt.com/docs/dots/channels")


def shipping_28_view(rows, notices=()):
    """A dated editorial digest of Tibo's 28-day series, separate from reset records."""
    seen = set()
    table_rows = []
    for record in sorted(rows, key=lambda item: item["day"]):
        day = record["day"]
        if not isinstance(day, int) or isinstance(day, bool) or day < 1 or day > 28 or day in seen:
            raise ValueError("Invalid or repeated shipping day")
        seen.add(day)
        date_pt = datetime.strptime(record["date_pt"], "%Y-%m-%d")
        if date_pt.date() != (datetime(2026, 10, 5) + timedelta(days=day - 1)).date():
            raise ValueError("Shipping date is inconsistent with day number")
        sources = record["sources"]
        if not sources or not all(shipping_source(url) for url in sources):
            raise ValueError("Every day needs a first-party source")
        labels = record.get("source_labels") or [f"Xの投稿{i+1}を見る" for i in range(len(sources))]
        if len(labels) != len(sources):
            raise ValueError("Source labels must match sources")
        links = " ".join(link(url, label) for url, label in zip(sources, labels))
        date_display = f"{date_pt.month}/{date_pt.day}"
        table_rows.append(f'<tr id="day-{day}"><th scope="row">Day {day}</th>'
                          f'<td class="shipping-date" data-label="日付">{date_display}</td>'
                          f'<td class="shipping-type" data-label="区分">{e(record["category"])}</td>'
                          f'<td class="shipping-summary" data-label="発表内容">{e(record["summary"])}</td>'
                          f'<td class="shipping-sources" data-label="発表者の投稿">{links}</td></tr>')
    updates = []
    for notice in sorted(notices, key=lambda item: parse_time(item["published_at"]), reverse=True):
        if not shipping_source(notice["source"]):
            raise ValueError("Notices need an original first-party source")
        updates.append(f'<section><h3>{e(notice["title"])}</h3>'
                       f'<p class="shipping-note">{e(jst(notice["published_at"]))}（日本時間）の投稿</p>'
                       f'<p>{e(notice["summary"])}</p><p>{link(notice["source"], "Tibo氏の説明を読む（X）")}</p></section>')
    supplemental = '<section class="shipping-updates"><h2>関連するお知らせ</h2>' + ''.join(updates) + '</section>' if updates else ''
    return (f'''<article class="shipping-page"><div class="shipping-heading">
<h1 class="section-title">OpenAIの28日間企画</h1>
<h2 class="shipping-subtitle">新機能・改善・利用枠リセットの発表一覧</h2>
<p class="article-lead">2026年10月5日から28日間、OpenAIの担当者Tibo氏がCodex・ChatGPT Workなどの新機能や改善、利用枠の臨時リセットを発表している企画です。Day 1〜{len(rows)}の内容を日付順にまとめています。</p>
<p class="shipping-note">日付は企画上の米国太平洋時間です。日本時間では発表が翌日になることがあります。Tibo氏が実施を発表したリセットを掲載しています。「チケット」は後から使える保存型リセットです。</p>
</div><div class="shipping-table-wrap"><table class="shipping-table">
<thead><tr><th scope="col">何日目？</th><th scope="col">日付</th><th scope="col">種類</th><th scope="col">発表されたこと</th><th scope="col">発表者の投稿</th></tr></thead>
<tbody>''' + "".join(table_rows) + '''</tbody></table></div>
<p class="shipping-note">この一覧はOpenAI公式と担当者本人の投稿を基にした要約です。個々の機能の提供対象・提供時期はプランや地域などによって異なる場合があります。新たな日程の発表は確認後に追記します。</p>
''' + supplemental + '''<p class="article-back"><a href="./">リセットカレンダーに戻る</a></p></article>''')


GUIDE = '''<article class="article"><h1 class="section-title">リセットの種類</h1><p class="article-lead">リセットには主に2つの種類があります。</p>
<h2>臨時リセット</h2><p>OpenAIが利用枠を特別に回復することです。対象のプランや機能は発表によって異なります。</p>
<h2>リセットチケット</h2><p>もらっておき、必要なときに自分で使えるリセットです。有効期限などの条件があります。</p>
<h2>残りの利用枠を調べるには</h2><p>ChatGPTの「使用状況」で、自分の残りの利用枠と通常の回復予定を確認できます。</p>
<p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''

ABOUT = f'''<article class="article"><h1 class="section-title">このサイトについて</h1>
<p class="article-lead">Codex・ChatGPT Workのリセット日と予想をカレンダーにまとめています。</p>
<h2>リセットの記録</h2><p>カレンダーには、OpenAIの発表やTibo氏のX投稿があった日を「リセット」として掲載しています。実施の発表があれば、リセットとして掲載します。</p>
<h2>情報の確認方法</h2><p><a href="{OFFICIAL_URL}">OpenAIの公式案内</a>と、Codexの責任者<strong>Tibo氏</strong>（Thibault Sottiaux／<a href="https://x.com/thsottiaux">X</a>）などの発信を確認しています。各記録の「公式発表を見る」「Xの投稿を見る」から、発表者本人の文章を確認できます。</p>
<h2 id="dates">表示日時の見方</h2><p>表示日時は日本時間の投稿日時です。実際に利用枠が回復した時刻とは限りません。</p>
<h2>アクセスの集計</h2><p>閲覧回数などを匿名で集計しています。氏名・メールアドレス・IPアドレスは集計データに保存しません。</p>
<h2>お問い合わせ</h2><p><a href="https://github.com/{REPO}/issues">ご意見・訂正の連絡</a></p>
<p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''

def build():
    records = read_json(DATA / "events.json", [])
    if not records:
        raise ValueError("records are required before building")
    health = read_json(DATA / "health.json", {})
    updated = utcnow()
    now = parse_time(updated)
    fresh = (health.get("feed") == "ok" and health.get("last_success_at")
             and timedelta(0) <= now - parse_time(health["last_success_at"]) <= timedelta(hours=24))
    forecast = predict(records, now, bool(fresh and health.get("x_status") == "checked"))
    proposal = read_json(DATA / "editorial-forecast.json", None)
    editorial = active_editorial_forecast(records, now, proposal)
    editorial_history = read_json(DATA / "editorial-forecast-history.json", [])
    # Snapshot a forecast even while active. Expiry or replacement never deletes its audit trail.
    editorial_history = sync_editorial_history(editorial_history, proposal, records, health, now, editorial)
    write_json(DATA / "editorial-forecast-history.json", editorial_history)
    history = update_history(read_json(DATA / "forecast-history.json", []), forecast, records, now, health.get("last_success_at"))
    write_json(DATA / "forecast-history.json", history)
    OUT.mkdir(parents=True, exist_ok=True)
    shipping = read_json(DATA / "shipping-28.json", [])
    shipping_end = max((row["day"] for row in shipping), default=0)
    notices = read_json(DATA / "shipping-notices.json", [])
    pages = {
        "index": ("ChatGPT リセット履歴｜Codex・Workの利用枠リセット日と次回予想", "ChatGPT Work・Codexの利用枠リセット履歴をカレンダーで確認。OpenAIの発表やTibo氏の投稿をもとに、これまでのリセット日・次回予想・リセットチケットの情報をまとめています。", homepage(records, updated, forecast, history, editorial, editorial_history, proposal)),
        "ship28": ("OpenAIの28日間企画｜Codex・Workの新機能・リセット一覧", f"OpenAI担当者の28日間企画。Day 1〜{shipping_end}のCodex・ChatGPT Workの新機能・速度改善・利用枠リセットを日別に紹介。Tibo氏とOpenAI公式の発表へのリンク付き。", shipping_28_view(shipping, notices)),
        "guide": ("リセットの種類｜ChatGPT リセット履歴", "通常の利用枠の回復と、臨時リセット・リセットチケットの違いを説明します。", GUIDE),
        "forecast": ("予測の計算方法｜ChatGPT リセット履歴", "独自予測の計算式、集計対象、検証方法と注意事項を掲載しています。", FORECAST_METHOD),
        "about": ("このサイトについて｜ChatGPT リセット履歴", "サイトの情報源、日時の見方、更新方法をご案内します。", ABOUT),
    }
    for key, (title, description, content) in pages.items():
        (OUT / f"{key}.html").write_text(shell(title, description, key, content, updated, show_forecast=forecast["status"] == "ok"), encoding="utf-8")
    write_json(OUT / "forecast.json", {**forecast, "scores": scores(history), "source_policy": "OpenAI公式発表・Codex責任者らのX投稿", "disclaimer": DISCLAIMER})
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    urls = [SITE_URL + "/", SITE_URL + "/ship28.html", SITE_URL + "/guide.html", SITE_URL + "/about.html", SITE_URL + "/forecast.html"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{e(u)}</loc><lastmod>{updated}</lastmod></url>" for u in urls) + "</urlset>"
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["記録ID", "掲載日付・投稿日時", "時刻の意味", "種類", "発表内容", "発信元", "発表の確認先URL", "内容"])
    for r in records:
        when = r["official_date"] if r.get("date_precision") == "day" else jst(r["reference_at"])
        source = (r.get("official_confirmation") or {}).get("url") or r.get("original_url") or ""
        writer.writerow([r["id"], when, r["time_basis"], KINDS[r["kind"]], record_title(r), source_name(r), source, r.get("note", "")])
    (OUT / "data.csv").write_text("\ufeff" + stream.getvalue(), encoding="utf-8")
    items = "".join(f'<item><title>{e(record_day(r))}・{e(record_title(r))}</title><link>{SITE_URL}/#r-{r["id"].replace(":", "-")}</link><guid isPermaLink="false">{e(r["id"])}</guid><description>{e(source_name(r) + "。" + r["note"])}</description></item>' for r in records[:30])
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>ChatGPT リセット履歴</title><link>{SITE_URL}/</link><description>OpenAIの一次資料で確認した臨時リセット</description><language>ja</language>{items}</channel></rss>', encoding="utf-8")

    (OUT / "404.html").write_text(shell("ページが見つかりません｜ChatGPT リセット履歴", "履歴一覧からご確認ください。", "404", '<article class="article"><h1 class="section-title">ページが見つかりません</h1><p><a href="' + SITE_URL + '/">履歴一覧へ</a></p></article>', updated, show_forecast=forecast["status"] == "ok"), encoding="utf-8")
    print(f"Built {len(records)} records and 4 public pages in docs/")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    refresh = sub.add_parser("refresh")
    refresh.add_argument("--input", type=Path)
    refresh.add_argument("--github-output")
    sub.add_parser("build")
    args = parser.parse_args()
    if args.command == "refresh":
        return collect(args.input, args.github_output)
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
