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
FEED_URL = "https://codex-reset.com/api/timeline"
ARCHIVE_URL = "https://codex-reset.com/ja/timeline/"
DATA_SOURCE_URL = "https://codex-reset.com/"
DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
OFFICIAL_URL = "https://help.openai.com/ja-jp/articles/20001498-how-banked-codex-resets-work"
HEALTH_URL = f"https://raw.githubusercontent.com/{REPO}/main/data/health.json"
JST = timezone(timedelta(hours=9))
KINDS = {"global": "一斉リセット", "banked": "リセット券の配布"}
EVIDENCE = {"official": "公式本文で日付確認", "quoted": "担当者発言の転載", "third_party": "第三者サイトの記録"}
REASONS = {
    "incident": "障害・不具合への対応。",
    "compensation": "利用制限への補償。",
    "launch": "モデル・機能の公開に伴う対応。",
    "milestone": "利用者数の増加を記念。",
    "promotion": "記念・キャンペーンに伴う対応。",
    "promo": "記念・キャンペーンに伴う対応。",
}


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
        if u.hostname not in {"x.com", "twitter.com", "help.openai.com", "community.openai.com", "codex-reset.com"}:
            return None
        if any(ord(c) < 32 for c in value):
            return None
        return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "", ""))
    except ValueError:
        return None


def normalize_feed(payload, confirmations=None, editorial=None, now=None):
    """Keep factual fields only; upstream excerpts/quotes are not republished."""
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("feed must contain an events array")
    if not 1 <= len(payload["events"]) <= 2000:
        raise ValueError("unexpected event count; refusing to replace saved data")
    confirmations = confirmations or []
    editorial = editorial or {}
    by_proof = {(str(c["post_id"]), c["kind"]): c for c in confirmations}
    current = now or datetime.now(timezone.utc)
    records, rejected = {}, 0
    for raw in payload["events"]:
        try:
            if not isinstance(raw, dict) or raw.get("confirmed") is not True or raw.get("preview") is True:
                continue
            if raw.get("type") not in {"reset", "credits"}:
                continue
            banked = raw.get("reset_kind") == "banked" or raw.get("type") == "credits"
            # A delivery observation of an already-announced grant is not a second grant.
            if banked and raw.get("banked_grant") is not True:
                continue
            kind = "banked" if banked else "global"
            post_id = str(raw.get("id", ""))
            if not re.fullmatch(r"[0-9]{12,24}", post_id):
                raise ValueError("invalid id")
            stamp = raw.get("announced_at")
            date = parse_time(stamp)
            if date.year < 2025 or date > current + timedelta(hours=24):
                raise ValueError("implausible date")
            url = safe_url(raw.get("url"))
            if raw.get("url") and not url:
                raise ValueError("untrusted URL")
            proof = by_proof.get((post_id, kind))
            reasons = [t for t in raw.get("reason_tags", []) if t in REASONS]
            upcoming = "preview" in str(raw.get("time_kind", "")).lower()
            state = "announced" if upcoming else ("observed" if raw.get("source") == "observed" else "reported")
            audience = raw.get("audience") if isinstance(raw.get("audience"), list) else []
            products = [p for p in audience if p in {"codex", "chatgpt_work"}]
            note = editorial.get(post_id) or (REASONS[reasons[0]] if reasons else "")
            proof_level = proof.get("level", "official") if proof else "third_party"
            if proof_level not in EVIDENCE:
                proof_level = "third_party"
            record = {
                "id": post_id + ":" + kind,
                "post_id": post_id,
                "kind": kind,
                "state": state,
                "reference_at": date.isoformat().replace("+00:00", "Z"),
                "time_basis": "履歴サイトの参考時刻（発表・報告・観測）",
                "time_officially_verified": False,
                "evidence": proof_level,
                "products": products,
                "note": note,
                "original_url": url,
                "archive_url": ARCHIVE_URL,
                "data_source": DATA_SOURCE_URL,
                "data_license": DATA_LICENSE_URL,
                "official_confirmation": proof if proof_level == "official" else None,
                "quotation_confirmation": proof if proof_level == "quoted" else None,
                "reason_tags": reasons,
            }
            records[record["id"]] = record
        except (ValueError, TypeError, KeyError, OverflowError):
            rejected += 1
    if not records:
        raise ValueError("no usable records; previous data preserved")
    return sorted(records.values(), key=lambda x: (x["reference_at"], x["id"]), reverse=True), rejected


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


def official_marker(text):
    # A source URL or HTTP 200 alone is never evidence of official confirmation.
    flat = html.unescape(re.sub(r"<[^>]+>", " ", text))
    flat = re.sub(r"\s+", " ", flat)
    date = re.search(r"2026\s*年\s*9\s*月\s*7\s*日|September\s+7,?\s+2026", flat, re.I)
    return bool(date and re.search(r"全世界一斉リセットを実施|provided a global reset", flat, re.I)
                and all(p in flat for p in ["Plus", "Pro", "Business"]))


def save_records(records, old):
    # Upstream outages, shorter feeds, and accidental deletions never erase history.
    combined = {r["id"]: r for r in old}
    combined.update({r["id"]: r for r in records})
    result = sorted(combined.values(), key=lambda x: (x["reference_at"], x["id"]), reverse=True)
    return write_json(DATA / "events.json", result)


def collect(input_file=None, github_output=None):
    checked = utcnow()
    old = read_json(DATA / "events.json", [])
    health = read_json(DATA / "health.json", {})
    status = {"checked_at": checked, "last_success_at": health.get("last_success_at"), "feed": "failed", "official_page": "not_checked", "message": "前回の正常データを保持しています。"}
    changed, ok = False, False
    try:
        body = input_file.read_text(encoding="utf-8") if input_file else fetch(FEED_URL)
        payload = json.loads(body)
        proofs = read_json(DATA / "official-confirmations.json", []) + read_json(DATA / "quoted-confirmations.json", [])
        records, rejected = normalize_feed(payload, proofs, read_json(DATA / "editorial.json", {}))
        changed = save_records(records, old)
        status.update(feed="ok", last_success_at=checked, message="公開された履歴データを確認しました。", imported_records=len(records), rejected_records=rejected, upstream_updated_at=payload.get("updated_at"))
        if input_file:
            status["message"] = "初期データを作成しました。定期更新の初回成功はまだ確認していません。"
            status["feed"] = "bootstrap"
            status["last_success_at"] = None
        else:
            ok = True
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        status["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    if not input_file:
        try:
            status["official_page"] = "marker_confirmed" if official_marker(fetch(OFFICIAL_URL)) else "marker_not_found"
        except RuntimeError:
            status["official_page"] = "unavailable"
    write_json(DATA / "health.json", status)
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write("records_changed=" + str(changed).lower() + "\n")
    print(json.dumps({"records_changed": changed, "feed": status["feed"], "official_page": status["official_page"]}, ensure_ascii=False))
    return 0 if ok or input_file else 2


def e(value):
    return html.escape(str(value), quote=True)


def link(url, text, cls=""):
    checked = safe_url(url)
    return f'<a class="{e(cls)}" href="{e(checked)}" target="_blank" rel="noopener noreferrer">{e(text)} ↗</a>' if checked else ""


def shell(title, description, active, content, updated):
    canonical = SITE_URL + ("/" if active == "index" else f"/{active}.html")
    nav = "".join(f'<a href="{href}" {"aria-current=page" if active == key else ""}>{label}</a>' for key, href, label in [("index", "./", "履歴一覧"), ("guide", "guide.html", "リセットの種類"), ("forecast", "forecast.html", "予測の計算方法"), ("about", "about.html", "出典について")])
    website = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "ChatGPT リセット履歴", "url": SITE_URL + "/", "inLanguage": "ja"}, ensure_ascii=False).replace("<", "\\u003c")
    brand_tag = "h1" if active == "index" else "div"
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta name="theme-color" content="#245e9b"><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/style.css"><link rel="alternate" type="application/rss+xml" title="ChatGPT リセット履歴 更新情報" href="feed.xml"><link rel="sitemap" type="application/xml" href="sitemap.xml">
<script type="application/ld+json">{website}</script><script defer src="assets/app.js"></script></head>
<body><a class="skip" href="#main">本文へ移動</a><header class="site-header container"><div class="masthead"><div><div class="brand-line"><{brand_tag} class="brand"><a href="./">ChatGPT リセット履歴</a></{brand_tag}><span class="unofficial">非公式</span></div><p class="site-subtitle">Codex・Workのリセットカレンダーと独自予測</p></div><p class="site-description">ChatGPT Work・Codexの利用枠に関する臨時リセットを、日本時間のカレンダーで確認できます。過去の間隔から独自予測も計算しています。</p></div><nav class="main-nav" aria-label="メインナビゲーション">{nav}</nav></header>
<main id="main" class="container">{content}</main>
<footer class="container site-footer"><p class="footer-title">ChatGPT リセット履歴</p><p>OpenAIとは関係のない非公式サイトです。</p><p>履歴データの出典：Codex Reset（<a href="{DATA_SOURCE_URL}">codex-reset.com</a>）。ライセンス：<a href="{DATA_LICENSE_URL}">CC BY 4.0</a>。日本時間への換算と分類・説明文の編集を行っています。</p><p class="footer-links"><a href="about.html">出典について</a><a href="https://github.com/{REPO}/issues">訂正の連絡</a><a href="data.csv">履歴データ（CSV）</a><a href="feed.xml">RSS</a></p><p class="muted">ページ更新：{e(jst(updated))}（日本時間）</p></footer></body></html>'''


def record_title(record):
    if record["kind"] == "banked":
        return "リセット券の配布予告" if record["state"] == "announced" else "リセット券の配布"
    return {"reported": "一斉リセットの完了報告", "announced": "一斉リセットの実施予告", "observed": "一斉リセットの確認報告"}[record["state"]]


def date_label(value):
    date = parse_time(value).astimezone(JST)
    return f"{date.year}年{date.month}月{date.day}日 {date:%H:%M}ごろ"


def record_row(record):
    proof = record.get("official_confirmation")
    evidence = record["evidence"]
    official = ""
    if proof:
        year, month, day = proof["official_date"].split("-")
        official = f'<p class="proof-note">公式記載日：{e(year)}年{int(month)}月{int(day)}日<br>実施時刻の記載なし</p>'
    quotation = record.get("quotation_confirmation")
    quoted_source = link(quotation["url"], "発言の転載") if quotation else ""
    official_source = link(proof["url"], "公式記事") if proof else ""
    original = link(record.get("original_url"), "元投稿")
    products = "・".join({"codex": "Codex", "chatgpt_work": "Work"}[p] for p in record["products"])
    target = f'<small class="record-target">対象：{e(products)}</small>' if products else ""
    note = f'<p class="record-summary">{e(record["note"])}</p>' if record.get("note") else ""
    date = parse_time(record["reference_at"]).astimezone(JST)
    return f'''<tr id="r-{e(record['id'].replace(':', '-'))}" data-record data-kind="{record['kind']}" data-evidence="{evidence}" data-month="{date:%Y-%m}">
<td class="record-date" data-label="日時（日本時間）"><time datetime="{e(record['reference_at'])}"><span>{date:%Y/%m/%d}</span><span class="record-clock">{date:%H:%M}ごろ</span></time></td>
<td class="record-content" data-label="内容"><strong class="record-title">{e(record_title(record))}</strong>{target}{note}</td>
<td class="record-evidence" data-label="確認状況"><span class="badge {evidence}">{EVIDENCE[evidence]}</span>{official}</td>
<td class="record-source" data-label="出典"><div class="source-links">{official_source}{quoted_source}{original}{link(record['archive_url'], '掲載元')}</div></td></tr>'''


DISCLAIMER = "当サイト独自の予測です。OpenAIの公式発表ではなく、的中を保証しません。予測の利用による損害については、法令で認められる範囲で責任を負いません。"


def calendar_overview(records, forecast):
    today = parse_time(forecast['generated_at']).astimezone(JST).date()
    entries = []
    for r in records:
        date = parse_time(r['reference_at']).astimezone(JST)
        sources = [(r.get('official_confirmation') or {}).get('url'), (r.get('quotation_confirmation') or {}).get('url'), r.get('original_url'), r.get('archive_url')]
        entries.append({'day': date.strftime('%Y-%m-%d'), 'time': date.strftime('%H:%M'),
                        'id': 'r-' + r['id'].replace(':', '-'), 'kind': r['kind'], 'state': r['state'],
                        'title': record_title(r), 'evidence': EVIDENCE[r['evidence']], 'note': r.get('note', ''),
                        'sources': [{'url': safe_url(url), 'label': label} for url, label in zip(sources, ['公式記事', '発言の転載', '元投稿', '掲載元']) if safe_url(url)]})
    selected = next((r['day'] for r in entries if r['kind'] == 'global' and r['state'] != 'announced'), today.isoformat())
    if not selected.startswith(today.strftime('%Y-%m')):
        selected = today.isoformat()
    predicted = forecast.get('reference_date')
    by_day = {}
    for r in entries:
        by_day.setdefault(r['day'], []).append(r)
    def cell(day):
        if not day:
            return '<div class="calendar-empty" aria-hidden="true"></div>'
        key = f'{today.year}-{today.month:02d}-{day:02d}'
        day_records = by_day.get(key, [])
        marks = []
        if any(r['kind'] == 'global' and r['state'] != 'announced' for r in day_records):
            marks.append('<span class="day-mark reset-mark">一斉</span>')
        if any(r['kind'] == 'banked' and r['state'] != 'announced' for r in day_records):
            marks.append('<span class="day-mark banked-mark">配布</span>')
        if any(r['state'] == 'announced' for r in day_records):
            marks.append('<span class="day-mark announced-mark">予告</span>')
        if key == predicted:
            marks.append('<span class="day-mark predicted-mark">独自予測</span>')
        classes = 'calendar-day' + (' is-today' if key == today.isoformat() else '')
        label = f'{today.year}年{today.month}月{day}日、履歴{len(day_records)}件' + ('、独自予測の参考日' if key == predicted else '')
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
    details = ''.join(f'<article class="day-record"><p class="day-record-time">{r["time"]}ごろ <span>{e(r["evidence"])}</span></p><h4>{e(r["title"])}</h4><p>{e(r["note"])}</p><p class="day-source">' + ''.join(link(s['url'], s['label']) for s in r['sources']) + f'<a href="#{e(r["id"])}">履歴の詳細</a></p></article>' for r in by_day.get(selected, [])) or '<p class="empty-day">この日の履歴はありません。</p>'
    payload = json.dumps({'today':today.isoformat(), 'selected':selected, 'first':first, 'last':last, 'predicted':predicted, 'records':entries}, ensure_ascii=False).replace('<', '\\u003c')
    if forecast['status'] == 'ok':
        h24, h48 = forecast['horizons']['24'], forecast['horizons']['48']
        lower, upper = h24['observed_ratio_interval']
        date = datetime.strptime(predicted, '%Y-%m-%d')
        prediction = f'''<div class="forecast-numbers"><div><span>24時間以内</span><strong>{h24['display_percent']}<small>%</small></strong></div><div><span>48時間以内</span><strong>{h48['display_percent']}<small>%</small></strong></div></div>
<p class="forecast-caption">一斉リセットの参考時刻に基づく試算</p>
<p class="reference-date">参考日 <strong>{date.month}月{date.day}日ごろ</strong><span>実施予定日ではありません</span></p>
<details class="forecast-reasons" open><summary>なぜこの予測？</summary><p>前回の完了報告から<strong>{forecast['elapsed_hours']/24:.1f}日</strong>経過しています。直近90日間に始まった実施間隔<strong>{forecast['sample_size']}件</strong>のうち、これより長かったのは<strong>{forecast['eligible_size']}件</strong>でした。</p><p>その{h24['total']}件では、現在と同じ経過時点から24時間以内の報告が{h24['count']}件、48時間以内が{h48['count']}件でした。この比率を補正して上の数値を出しています。</p><p class="sample-note">少数の履歴による試算です。24時間の集計比率の95%参考区間は{lower}〜{upper}%と幅があり、予測精度はまだ検証できていません。</p></details>'''
    else:
        message = '最新の履歴を取得できていないため、予測を休止しています。' if forecast['status'] == 'stale' else '計算に必要な履歴が足りないため、予測値を表示していません。'
        prediction = f'<p class="forecast-unavailable">{message}</p>'
    return f'''<div class="calendar-layout"><section class="calendar-section" aria-labelledby="calendar-title"><div class="calendar-section-heading"><h2 id="calendar-title">リセットカレンダー</h2><span>日本時間</span></div><div class="calendar-controls"><div><button id="calendar-prev" type="button" aria-label="前の月">‹</button><label class="sr-only" for="calendar-month">カレンダーの年月</label><select id="calendar-month">{''.join(month_options)}</select><button id="calendar-next" type="button" aria-label="次の月">›</button></div><button id="calendar-today" type="button">今月</button></div><div class="calendar-weekdays" aria-hidden="true"><span>日</span><span>月</span><span>火</span><span>水</span><span>木</span><span>金</span><span>土</span></div><div id="calendar-grid" class="calendar-grid" role="group" aria-label="{today.year}年{today.month}月">{grid}</div><div class="calendar-legend"><span><i class="legend-reset"></i>一斉リセット</span><span><i class="legend-banked"></i>リセット券の配布</span><span><i class="legend-announced"></i>予告</span><span><i class="legend-predicted"></i>独自予測</span></div><section class="selected-day" aria-live="polite" aria-atomic="true"><h3 id="selected-date">{int(selected[5:7])}月{int(selected[8:])}日の履歴</h3><div id="selected-records">{details}</div></section><noscript><p>月の切り替えにはJavaScriptが必要です。全履歴は下の一覧から確認できます。</p></noscript></section>
<aside class="forecast-panel" aria-labelledby="forecast-title"><div class="forecast-heading"><h2 id="forecast-title">次のリセット予測</h2><span>独自予測・試験公開</span></div><div id="forecast-current" data-generated-at="{forecast['generated_at']}">{prediction}</div><p id="forecast-expired" hidden>表示中の予測は計算から時間が経過しています。最新の計算結果を取得できるまで数値を非表示にしています。</p><p class="forecast-updated">計算：{e(jst(forecast['generated_at']))}（日本時間）</p><a class="method-link" href="forecast.html">計算方法と検証について →</a><p class="forecast-disclaimer">{DISCLAIMER}</p></aside></div><script id="calendar-data" type="application/json">{payload}</script>'''


def forecast_results(history):
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
    return f'<section class="forecast-results" aria-labelledby="forecast-results-title"><div class="section-heading"><h2 id="forecast-results-title">予測と結果</h2><p>{status}</p></div><p class="results-description">毎日最初の予測を保存し、24・48時間後の履歴と照合します。過去の予測値は書き換えません。結果は出典に記録された参考時刻で判定します。</p>{body}<p class="results-note">直近7日分を掲載。判定待ち・取得遅延を含みます。履歴の追加・訂正により結果が変わる場合があります。<a href="https://github.com/{REPO}/blob/main/data/forecast-history.json">すべての予測記録</a></p></section>'


def homepage(records, health, updated, forecast, forecast_history):
    proof_count = sum(r["evidence"] == "official" for r in records)
    months = sorted({parse_time(r["reference_at"]).astimezone(JST).strftime("%Y-%m") for r in records}, reverse=True)
    options = "".join(f'<option value="{m}">{m[:4]}年{int(m[5:])}月</option>' for m in months)
    rows = []
    current_month = None
    for record in records:
        month = parse_time(record["reference_at"]).astimezone(JST).strftime("%Y-%m")
        if month != current_month:
            rows.append(f'<tr class="month-heading" id="month-{month}" data-month-heading="{month}"><th scope="rowgroup" colspan="4">{month[:4]}年{int(month[5:])}月</th></tr>')
            current_month = month
        rows.append(record_row(record))
    check = health.get("checked_at", updated)
    if health.get("feed") == "ok" and health.get("last_success_at"):
        health_text = "最終更新：" + jst(health["last_success_at"]) + "（日本時間）"
    elif health.get("feed") == "failed":
        health_text = "最新情報を取得できません。前回の履歴を表示しています。"
    else:
        health_text = "初期データ掲載：" + jst(check) + "（日本時間）。自動更新は未確認です。"
    evidence_tabs = "".join(f'<button type="button" data-evidence-option="{key}" aria-pressed="{str(key == "all").lower()}">{label}</button>' for key, label in [("all", "すべて"), ("official", "公式本文で確認"), ("quoted", "発言の転載"), ("third_party", "第三者サイト")])
    return f'''{calendar_overview(records, forecast)}
<p class="status-line" data-health-url="{HEALTH_URL}"><span id="health-text">{e(health_text)}</span></p>
<p class="time-note">日時は、発表・報告・観測の時刻を日本時間に換算したものです。実際の反映時刻とは異なる場合があります。<a href="about.html#dates">日時の表記について</a></p>
{forecast_results(forecast_history)}
<section id="history" class="history-section"><div class="section-heading"><h2 class="section-title">過去のリセット</h2><p>{len(records)}件<span class="count-detail"> ／ 公式本文で日付を確認：{proof_count}件</span></p></div>
<form id="filters" aria-label="履歴の絞り込み"><input type="hidden" id="evidence-filter" value="all"><div class="filter-primary"><div class="evidence-tabs" role="group" aria-label="確認状況で絞り込む">{evidence_tabs}</div><label class="search-label"><span class="sr-only">キーワード</span><input id="search-filter" type="search" placeholder="キーワードで検索" autocomplete="off"></label></div><div class="filter-secondary"><label for="kind-filter">種類</label><select id="kind-filter"><option value="all">すべて</option><option value="global">一斉リセット</option><option value="banked">リセット券の配布</option></select><label for="month-filter">年月</label><select id="month-filter"><option value="all">すべての月</option>{options}</select><button class="reset-filter" type="reset">条件を解除</button></div></form>
<p id="result-count" class="result-count" aria-live="polite">{len(records)}件を表示</p><div class="table-wrap"><table><caption class="sr-only">ChatGPT Work・Codexの臨時リセット履歴</caption><thead><tr><th scope="col">日時（日本時間）</th><th scope="col">内容</th><th scope="col">確認状況</th><th scope="col">出典</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p id="no-results" hidden>条件に一致する履歴はありません。</p><noscript><p>絞り込みにはJavaScriptが必要です。以下に全履歴を掲載しています。</p></noscript></section>
<section class="related-guide"><h2>通常の利用枠更新との違い</h2><p>通常の5時間枠・週間枠の更新時刻は、アカウントごとに異なります。この履歴から個人の残り枠や回復時刻を確認することはできません。</p><a href="guide.html">リセットの種類</a></section>'''


FORECAST_METHOD = f'''<article class="article"><h1 class="section-title">予測の計算方法</h1><p class="article-lead">過去のリセット間隔から計算する、当サイト独自の試みです。他サイトの予測値は使っていません。</p>
<h2>何を予測するのか</h2><p>一斉リセットの完了報告・確認報告が、計算時点から24時間・48時間以内に記録される可能性を試算します。判定には出典の参考時刻を使うため、履歴を取得した時刻や実際に利用枠が回復した時刻を予測するものではありません。</p><p>OpenAIの運用方針や内部情報を知るものではありません。リセット券の配布と実施予告は、計算から除外します。</p>
<h2>計算の手順</h2><ol class="method-steps"><li>保存済みの一斉リセットの完了報告・確認報告を、参考時刻の順に並べます。同じ記録ID・同じ時刻の重複と未来の時刻を除外します。</li><li>連続する報告の間隔を求め、その始まりが計算時点から90日以内のものを使います。</li><li>前回の報告から現在までの経過時間を求めます。過去の間隔のうち、この経過時間より長いものだけを選びます。</li><li>選んだ間隔のうち、現在と同じ経過時点から24時間・48時間以内に次の報告があった件数を数えます。</li><li>少数の記録で0%や100%になりにくいよう、次の式で補正します。表示は5ポイント単位に丸めます。</li></ol>
<p class="formula">予測値 ＝（該当件数 ＋ 1）÷（選んだ間隔の件数 ＋ 2）</p><p>これはラプラス補正を加えた条件付きの集計です。例えば、選んだ10件のうち3件が24時間以内なら、（3＋1）÷（10＋2）で約33%、表示は35%になります。</p>
<h2>カレンダーの参考日</h2><p>選んだ間隔の中央値を前回の報告時刻に足し、日本時間の日付に換算します。次回の実施予定日や、最も起こりやすい日を示すものではありません。カレンダーでは履歴とは異なる破線で表示します。</p>
<h2>数値を表示しない場合</h2><p>過去の間隔が6件未満、または経過時間による絞り込み後が5件未満の場合は、集計不足として表示しません。履歴の取得に失敗している場合や、最終成功から24時間以上経過した場合も予測を休止します。閲覧中の予測も、計算から24時間を超えた場合は数値を隠します。</p>
<h2>この方法の限界</h2><p>リセットの間隔が一定だという根拠はありません。障害、モデルの公開、キャンペーン、OpenAIの方針変更などで頻度は変わります。「しばらく来ていないから、そろそろ来る」とは限りません。</p><p>集計には第三者サイトの記録も含みます。記録漏れや時刻のずれは、そのまま予測に影響します。まだ終了していない現在の間隔は過去の標本に含めておらず、長い間隔が集計に入りにくい偏りもあります。90日という期間や最低件数は、実装上の設定であり、精度が実証された値ではありません。</p><p>「95%参考区間」は、集計した比率に対するウィルソン区間です。少数の記録による幅を示すために掲載しており、次回のリセットが95%の確率でその範囲に収まるという意味ではありません。</p>
<h2>予測を保存して結果を確認する</h2><p>日本時間の各日で最初に公開用の処理が成功した予測を保存します。保存済みの予測値と計算時点は変更せず、24・48時間が経過し、その期限以降に履歴の取得が成功してから結果を判定します。期間内に完了報告の参考時刻があれば「記録あり」、なければ「記録なし」です。取得の遅延や後日の訂正で結果が変わる場合があります。</p><p>判定済みの結果がない間は「検証前」と表示します。結果がある場合は、24時間予測の平均二乗誤差（Brierスコア、0〜1）を掲載します。0に近いほど誤差が小さい指標で、正解率ではありません。毎日の予測は互いに独立した試行ではないため、単純な件数だけで精度を判断することもできません。</p><p>導入前の予測や的中実績は作成していません。<a href="https://github.com/{REPO}/blob/main/data/forecast-history.json">保存された予測記録</a>と<a href="forecast.json">現在の計算結果（JSON）</a>を公開します。計算式を変更する場合は、記録に残すモデルIDも変更します。</p>
<h2>出典と費用</h2><p>入力する履歴は<a href="{DATA_SOURCE_URL}">codex-reset.com</a>の公開データ（<a href="{DATA_LICENSE_URL}">CC BY 4.0</a>）を基に、分類・編集したものです。予測はこのサイトのプログラムで計算し、他サイトの予測や有料のAI・X APIは利用していません。</p><p>カレンダーと計算は別の情報源に切り替えても運用できます。ただし、無料の取得経路だけでXの新着投稿を漏れなく収集できることは保証できません。現在の自動更新には、上記の履歴データを使っています。</p>
<h2>予測の利用について</h2><p class="method-disclaimer">{DISCLAIMER}</p><p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''


GUIDE = '''<article class="article"><h1 class="section-title">リセットの種類</h1><p class="article-lead">通常の利用枠の更新、一斉リセット、リセット券の違いを説明します。</p>
<h2>通常の利用枠の更新</h2><p>5時間枠や週間枠は、それぞれの利用期間に応じて回復します。残り枠と回復予定は、利用しているアプリの使用状況で確認してください。</p>
<h2>臨時の一斉リセット</h2><p>障害への対応や記念イベントなどに伴い、OpenAIが対象の利用枠を回復します。対象プランや回復する枠は、発表ごとに異なります。このサイトでは、こうした臨時リセットの履歴を掲載しています。</p>
<h2>リセット券の配布</h2><p>公式に「保存済みリセット」と呼ばれる、後から使用できるリセットです。配布された日時と、使用して利用枠が回復する日時は異なります。このサイトでは「リセット券の配布」と表記しています。利用条件や有効期限は、自分のアカウントで確認してください。</p>
<h2>対象プランと範囲</h2><p>発表で「全員」とされていても、有料プランの利用者やWork・Codexの利用者など、対象が限定される場合があります。ChatGPTの全モデル、画像生成、APIなどの利用枠も回復するとは限りません。</p>
<h2>次回の実施予定と予測</h2><p>当サイトでは過去の実施間隔から独自予測を計算しています。公式の実施予定ではなく、的中を保証するものではありません。<a href="forecast.html">予測の計算方法</a>もご確認ください。</p>
<section class="article-source"><h2>関連情報</h2><ul><li><a href="https://help.openai.com/ja-jp/articles/20001498-how-banked-codex-resets-work">OpenAI：保存済みCodexリセットの仕組み</a></li><li><a href="https://help.openai.com/ja-jp/articles/11369540-using-codex-with-your-chatgpt-plan">OpenAI：ChatGPTプランでCodexを使う</a></li></ul></section><p class="article-back"><a href="./#history">履歴一覧に戻る</a></p></article>'''


ABOUT = f'''<article class="article"><h1 class="section-title">出典について</h1><p class="article-lead">掲載情報の出典、確認状況、日時の表記について説明します。</p>
<h2>このサイトについて</h2><p>ChatGPT リセット履歴は、ChatGPT Work・Codexの臨時リセットを掲載する非公式サイトです。OpenAIとは関係ありません。運営：<a href="https://github.com/mtk-ctrl">mtk-ctrl</a>。</p>
<h2>確認状況の区分</h2><dl class="policy-list"><dt>公式本文で日付確認</dt><dd>OpenAIの公式記事で実施日を確認できた履歴です。実施時刻の記載がない場合は、日付のみの確認です。</dd><dt>担当者発言の転載</dt><dd>OpenAI担当者の発言を、他の投稿に転載・引用された文章で確認した履歴です。元の投稿本文を直接確認したものとは区別しています。公式フォーラムの一般ユーザーによる投稿も、この区分に含みます。</dd><dt>第三者サイトの記録</dt><dd>第三者サイトに掲載された履歴です。元投稿の本文は確認できていません。掲載元が「確認済み」としている場合も、公式確認とは区別します。</dd></dl>
<h2 id="dates">日時の表記</h2><p>日時は出典に記録されたUTC（協定世界時）を日本時間に換算し、分単位で掲載しています。発表・報告・観測の時刻を含むため、実際に利用枠が回復した時刻とは異なる場合があります。</p><p>公式記事で実施日のみ確認できた場合は、その日付を別に記載します。表の日時を公式発表の時刻として扱うものではありません。</p>
<h2>履歴の更新</h2><p>履歴は2時間おきに自動更新します。取得に失敗した場合は、前回の履歴を表示します。サービス側の混雑などにより、更新が遅れる場合があります。</p><p>履歴の取得と、公式本文の確認は別に行います。サイトの制作と文章の整理にはAIを使用しています。</p>
<h2>データの出典</h2><p>履歴データは<a href="{ARCHIVE_URL}">Codex Resetの公開データ</a>を利用しています。掲載元のライセンスは<a href="{DATA_LICENSE_URL}">CC BY 4.0</a>です。日本時間への換算と分類・説明文の編集を行い、各記録に元投稿と掲載元のリンクを付けています。データの取得については、掲載元の<a href="{DATA_SOURCE_URL}developers">API利用条件</a>に基づいています。</p><p>公式確認には<a href="{OFFICIAL_URL}">OpenAI公式ヘルプ</a>を利用しています。確認できた内容は、各記録の「確認状況」に記載しています。</p>
<h2>独自予測について</h2><p>入力には上記の履歴を使いますが、他サイトの予測値は利用しません。当サイトのプログラムで過去の間隔から試算し、根拠と結果を公開します。<a href="forecast.html">計算方法と注意事項</a>をご確認ください。</p>
<h2>訂正の連絡</h2><p>日時、内容、出典に誤りがある場合は、<a href="https://github.com/{REPO}/issues">GitHubの連絡窓口</a>へお知らせください。すべてのリセットを網羅した一覧ではなく、個人のアカウントへの反映を保証するものでもありません。</p>
<h2>プライバシー</h2><p>独自のアクセス解析、広告、Cookie、会員登録は導入していません。更新状況の表示には、GitHub上の公開ファイルを利用しています。ホスティング事業者が取得する接続情報については、各事業者の方針が適用されます。</p><p class="article-back"><a href="./">履歴一覧に戻る</a></p></article>'''


def build():
    records = read_json(DATA / "events.json", [])
    if not records:
        raise ValueError("records are required before building")
    health = read_json(DATA / "health.json", {})
    updated = utcnow()
    now = parse_time(updated)
    fresh = (health.get("feed") == "ok" and health.get("last_success_at")
             and timedelta(0) <= now - parse_time(health["last_success_at"]) <= timedelta(hours=24))
    forecast = predict(records, now, bool(fresh))
    history = update_history(read_json(DATA / "forecast-history.json", []), forecast, records, now, health.get("last_success_at"))
    write_json(DATA / "forecast-history.json", history)
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {
        "index": ("ChatGPT リセット履歴｜Codex・Workの臨時リセット", "ChatGPT Work・Codexの一斉リセットとリセット券の配布履歴。日時は日本時間で表記し、内容、確認状況、出典を掲載しています。", homepage(records, health, updated, forecast, history)),
        "guide": ("リセットの種類｜ChatGPT リセット履歴", "通常の利用枠更新、一斉リセット、リセット券の違いと、自分の残り枠・回復予定の確認先を説明します。", GUIDE),
        "forecast": ("予測の計算方法｜ChatGPT リセット履歴", "独自予測の計算式、集計対象、検証方法と注意事項を掲載しています。", FORECAST_METHOD),
        "about": ("出典について｜ChatGPT リセット履歴", "公式本文の確認、担当者発言の転載、第三者サイトの記録の区分と、日時の表記、出典、訂正の連絡先を掲載しています。", ABOUT),
    }
    for key, (title, description, content) in pages.items():
        (OUT / f"{key}.html").write_text(shell(title, description, key, content, updated), encoding="utf-8")
    write_json(OUT / "forecast.json", {**forecast, "scores": scores(history), "historical_data_source": DATA_SOURCE_URL, "historical_data_license": DATA_LICENSE_URL, "disclaimer": DISCLAIMER})
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    urls = [SITE_URL + "/", SITE_URL + "/guide.html", SITE_URL + "/about.html", SITE_URL + "/forecast.html"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{e(u)}</loc><lastmod>{updated}</lastmod></url>" for u in urls) + "</urlset>"
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["記録ID", "参考日時_JST", "日時の根拠", "種類", "根拠区分", "公式記載日", "時刻の公式確認", "元投稿", "掲載元", "データ出典", "データライセンス", "編集内容"])
    for r in records:
        writer.writerow([r["id"], jst(r["reference_at"]), r["time_basis"], KINDS[r["kind"]], EVIDENCE[r["evidence"]], (r.get("official_confirmation") or {}).get("official_date", ""), "いいえ", r.get("original_url") or "", r["archive_url"], DATA_SOURCE_URL, DATA_LICENSE_URL, "日本時間への換算・分類・説明文の編集"])
    (OUT / "data.csv").write_text("\ufeff" + stream.getvalue(), encoding="utf-8")
    credit = f" データ出典：codex-reset.com ({DATA_SOURCE_URL})。ライセンス：CC BY 4.0 ({DATA_LICENSE_URL})。日本時間への換算・分類・説明文の編集を行っています。"
    items = "".join(f'<item><title>{e(jst(r["reference_at"]))} JST・{KINDS[r["kind"]]}</title><link>{SITE_URL}/#r-{r["id"].replace(":", "-")}</link><guid isPermaLink="false">{e(r["id"])}</guid><description>{e(EVIDENCE[r["evidence"]] + "。" + r["note"] + credit)}</description></item>' for r in records[:30])
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>ChatGPT リセット履歴</title><link>{SITE_URL}/</link><description>ChatGPT Work・Codexの臨時リセット履歴</description><language>ja</language>{items}</channel></rss>', encoding="utf-8")
    (OUT / "404.html").write_text(shell("ページが見つかりません｜ChatGPT リセット履歴", "履歴一覧からご確認ください。", "404", '<article class="article"><h1 class="section-title">ページが見つかりません</h1><p><a href="' + SITE_URL + '/">履歴一覧へ</a></p></article>', updated), encoding="utf-8")
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
