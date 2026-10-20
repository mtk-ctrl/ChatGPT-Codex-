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
KINDS = {"global": "一斉リセット", "banked": "リセットチケットの配布"}
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
        if u.hostname not in {"x.com", "twitter.com", "help.openai.com", "openai.com"}:
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
    nav = "".join(f'<a href="{href}" {"aria-current=page" if active == key else ""}>{label}</a>' for key, href, label in [("index", "./", "履歴一覧"), ("guide", "guide.html", "リセットの種類"), ("forecast", "forecast.html", "予測の計算方法"), ("about", "about.html", "このサイトについて")] if key != "forecast" or show_forecast)
    website = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "ChatGPT リセット履歴", "url": SITE_URL + "/", "inLanguage": "ja"}, ensure_ascii=False).replace("<", "\\u003c")
    brand_tag = "h1" if active == "index" else "div"
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta name="theme-color" content="#245e9b"><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/style.css"><link rel="alternate" type="application/rss+xml" title="ChatGPT リセット履歴 更新情報" href="feed.xml"><link rel="sitemap" type="application/xml" href="sitemap.xml">
<script type="application/ld+json">{website}</script><script defer src="assets/app.js"></script></head>
<body><a class="skip" href="#main">本文へ移動</a><header class="site-header container"><div class="masthead"><div><div class="brand-line"><{brand_tag} class="brand"><a href="./">ChatGPT リセット履歴</a></{brand_tag}><span class="unofficial">非公式</span></div><p class="site-subtitle">Codex・ChatGPT Workの臨時リセット情報</p></div><p class="site-description">OpenAIの公式発表とCodex責任者Tibo氏の投稿をもとに、Codex・ChatGPT Workの臨時リセットや今後の予告をまとめています。</p></div><nav class="main-nav" aria-label="メインナビゲーション">{nav}</nav></header>
<main id="main" class="container">{content}</main>
<footer class="container site-footer"><p class="footer-title">ChatGPT リセット履歴</p><p>個人が運営する非公式サイトです。OpenAIの公式サイトではありません。</p><p>情報源：OpenAIの公式発表と、Codex責任者Tibo氏などのX投稿。</p><p class="footer-links"><a href="about.html">掲載情報について</a><a href="https://github.com/{REPO}/issues">訂正の連絡</a><a href="data.csv">履歴データ（CSV）</a><a href="feed.xml">RSS</a></p><p class="muted">ページ更新：{e(jst(updated))}（日本時間）</p></footer></body></html>'''


def record_title(record):
    if record["kind"] == "banked":
        return "リセットチケットの配布予告" if record["state"] == "announced" else "リセットチケットを配布"
    return {"reported": "一斉リセットを実施", "announced": "一斉リセットを予告",
            "observed": "一斉リセットを確認"}[record["state"]]


def date_label(value):
    date = parse_time(value).astimezone(JST)
    return f"{date.year}年{date.month}月{date.day}日 {date:%H:%M}"


def record_row(record):
    proof = record.get("official_confirmation")
    source_url = proof["url"] if proof else record.get("original_url")
    source = link(source_url, source_link_text(record))
    products = "・".join({"codex": "Codex", "chatgpt_work": "ChatGPT Work"}[p] for p in record["products"])
    target = f'<small class="record-target">対象サービス：{e(products)}</small>' if products else ""
    note = f'<p class="record-summary">{e(record["note"])}</p>' if record.get("note") else ""
    day = record_day(record)
    stamp = day if record.get("date_precision") == "day" else record["reference_at"]
    clock = record_clock(record)
    return f'''<tr id="r-{e(record['id'].replace(':', '-'))}" data-record data-kind="{record['kind']}" data-evidence="{record['evidence']}" data-month="{day[:7]}">
<td class="record-date" data-label="日時"><time datetime="{e(stamp)}"><span>{e(day.replace("-", "/"))}</span><span class="record-clock">{e(clock)}</span></time></td>
<td class="record-content" data-label="発表内容"><strong class="record-title">{e(record_title(record))}</strong>{target}{note}</td>
<td class="record-evidence" data-label="発信元"><span class="badge {record['evidence']}">{e(source_name(record))}</span></td>
<td class="record-source" data-label="元の発表"><div class="source-links">{source}</div></td></tr>'''


DISCLAIMER = ("この予測は当サイト独自の試算であり、OpenAIが発表した予定ではありません。"
              "的中を保証するものではなく、予測に基づく判断について責任を負いません"
              "（法令上、免責が認められない場合を除きます）。")


def calendar_overview(records, forecast):
    today = parse_time(forecast['generated_at']).astimezone(JST).date()
    entries = []
    for r in records:
        day = record_day(r)
        sources = [(r.get('official_confirmation') or {}).get('url'), r.get('original_url')]
        entries.append({'day': day, 'time': record_clock(r),
                        'id': 'r-' + r['id'].replace(':', '-'), 'kind': r['kind'], 'state': r['state'],
                        'title': record_title(r), 'evidence': source_name(r), 'note': r.get('note', ''),
                        'sources': [{'url': safe_url(url), 'label': label} for url, label in zip(sources, ['公式発表を見る', 'Xの投稿を見る']) if safe_url(url)]})
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
            marks.append('<span class="day-mark banked-mark">チケット</span>')
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
    details = ''.join(f'<article class="day-record"><p class="day-record-time">{e(r["time"])} <span>{e(r["evidence"])}</span></p><h4>{e(r["title"])}</h4><p>{e(r["note"])}</p><p class="day-source">' + ''.join(link(s['url'], s['label']) for s in r['sources']) + f'<a href="#{e(r["id"])}">履歴の詳細</a></p></article>' for r in by_day.get(selected, [])) or '<p class="empty-day">この日の履歴はありません。</p>'
    payload = json.dumps({'today':today.isoformat(), 'selected':selected, 'first':first, 'last':last, 'predicted':predicted, 'records':entries}, ensure_ascii=False).replace('<', '\\u003c')
    if forecast['status'] == 'ok':
        h24, h48 = forecast['horizons']['24'], forecast['horizons']['48']
        lower, upper = h24['observed_ratio_interval']
        date = datetime.strptime(predicted, '%Y-%m-%d')
        prediction = f'''<div class="forecast-numbers"><div><span>24時間以内</span><strong>{h24['display_percent']}<small>%</small></strong></div><div><span>48時間以内</span><strong>{h48['display_percent']}<small>%</small></strong></div></div>
<p class="forecast-caption">過去のリセット報告の間隔から計算</p>
<p class="reference-date">参考日 <strong>{date.month}月{date.day}日ごろ</strong><span>実施予定日ではありません</span></p>
<details class="forecast-reasons" open><summary>なぜこの予測？</summary><p>前回の完了報告から<strong>{forecast['elapsed_hours']/24:.1f}日</strong>経過しています。直近90日間に始まった実施間隔<strong>{forecast['sample_size']}件</strong>のうち、これより長かったのは<strong>{forecast['eligible_size']}件</strong>でした。</p><p>その{h24['total']}件では、現在と同じ経過時点から24時間以内の報告が{h24['count']}件、48時間以内が{h48['count']}件でした。この比率を補正して上の数値を出しています。</p><p class="sample-note">少数の履歴による試算です。24時間の集計比率の95%参考区間は{lower}〜{upper}%と幅があり、予測精度はまだ検証できていません。</p></details>'''
    else:
        prediction = ""
    if forecast["status"] == "ok":
        forecast_panel = f'''<aside class="forecast-panel" aria-labelledby="forecast-title"><div class="forecast-heading"><h2 id="forecast-title">次のリセット予測</h2><span>当サイト独自の試算</span></div><div id="forecast-current" data-generated-at="{forecast['generated_at']}">{prediction}</div><p class="forecast-updated">予測の計算日時：{e(jst(forecast["generated_at"]))}（日本時間）</p><a class="method-link" href="forecast.html">計算方法と検証について →</a><p class="forecast-disclaimer">{DISCLAIMER}</p></aside>'''
    else:
        forecast_panel = ""
    layout_class = "calendar-layout" if forecast_panel else "calendar-layout calendar-layout--full"
    prediction_legend = '<span><i class="legend-predicted"></i>独自予測</span>' if forecast_panel else ""
    return f'''<div class="{layout_class}"><section class="calendar-section" aria-labelledby="calendar-title"><div class="calendar-section-heading"><h2 id="calendar-title">リセットカレンダー</h2><span>日本時間</span></div><div class="calendar-controls"><div><button id="calendar-prev" type="button" aria-label="前の月">‹</button><label class="sr-only" for="calendar-month">カレンダーの年月</label><select id="calendar-month">{''.join(month_options)}</select><button id="calendar-next" type="button" aria-label="次の月">›</button></div><button id="calendar-today" type="button">今月</button></div><div class="calendar-weekdays" aria-hidden="true"><span>日</span><span>月</span><span>火</span><span>水</span><span>木</span><span>金</span><span>土</span></div><div id="calendar-grid" class="calendar-grid" role="group" aria-label="{today.year}年{today.month}月">{grid}</div><div class="calendar-legend"><span><i class="legend-reset"></i>一斉リセット</span><span><i class="legend-banked"></i>リセットチケット</span><span><i class="legend-announced"></i>予告</span>{prediction_legend}</div><section class="selected-day" aria-live="polite" aria-atomic="true"><h3 id="selected-date">{int(selected[5:7])}月{int(selected[8:])}日の履歴</h3><div id="selected-records">{details}</div></section><noscript><p>月の切り替えにはJavaScriptが必要です。全履歴は下の一覧から確認できます。</p></noscript></section>
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


def homepage(records, updated, forecast, forecast_history):
    proof_count = sum(r["evidence"] == "official" for r in records)
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
    evidence_tabs = "".join(f'<button type="button" data-evidence-option="{key}" aria-pressed="{str(key == "all").lower()}">{label}</button>' for key, label in [("all", "すべて"), ("official", "OpenAI公式"), ("staff_x", "Tibo氏の投稿")])
    return f'''{calendar_overview(records, forecast)}
<p class="time-note">掲載した時刻は発表・投稿の時刻です。実際に各アカウントの利用枠が回復した時刻とは異なる場合があります。<a href="about.html#dates">日時の表記について</a></p>
{forecast_results(forecast_history)}
<section id="history" class="history-section"><div class="section-heading"><h2 class="section-title">過去のリセット</h2><p>{len(records)}件<span class="count-detail"> ／ 公式サイトで発表：{proof_count}件</span></p></div>
<form id="filters" aria-label="履歴の絞り込み"><input type="hidden" id="evidence-filter" value="all"><div class="filter-primary"><div class="evidence-tabs" role="group" aria-label="確認状況で絞り込む">{evidence_tabs}</div><label class="search-label"><span class="sr-only">キーワード</span><input id="search-filter" type="search" placeholder="キーワードで検索" autocomplete="off"></label></div><div class="filter-secondary"><label for="kind-filter">種類</label><select id="kind-filter"><option value="all">すべて</option><option value="global">一斉リセット</option><option value="banked">リセットチケット</option></select><label for="month-filter">年月</label><select id="month-filter"><option value="all">すべての月</option>{options}</select><button class="reset-filter" type="reset">条件を解除</button></div></form>
<p id="result-count" class="result-count" aria-live="polite">{len(records)}件を表示</p><div class="table-wrap"><table><caption class="sr-only">ChatGPT Work・Codexの臨時リセット履歴</caption><thead><tr><th scope="col">日時</th><th scope="col">発表内容</th><th scope="col">発信元</th><th scope="col">元の発表</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p id="no-results" hidden>条件に一致する履歴はありません。</p><noscript><p>絞り込みにはJavaScriptが必要です。以下に全履歴を掲載しています。</p></noscript></section>
<section class="related-guide"><h2>通常の利用枠の更新との違い</h2><p>通常の5時間枠・週間枠の更新時刻は、アカウントごとに異なります。この履歴から個人の残り枠や回復時刻を確認することはできません。</p><a href="guide.html">リセットの種類</a></section>'''


FORECAST_METHOD = f'''<article class="article"><h1 class="section-title">予測の計算方法</h1><p class="article-lead">過去のリセット間隔に基づく、当サイト独自の試算です。</p>
<h2>何を予測するのか</h2><p>一斉リセットの完了報告・確認報告が、計算時点から24時間・48時間以内に記録される可能性を試算します。判定には出典の参考時刻を使うため、履歴を取得した時刻や実際に利用枠が回復した時刻を予測するものではありません。</p><p>OpenAIの運用方針や内部情報を知るものではありません。リセットチケットの配布と実施予告は、計算から除外します。</p>
<h2>計算の手順</h2><ol class="method-steps"><li>保存済みの一斉リセットの完了報告・確認報告を、参考時刻の順に並べます。同じ記録ID・同じ時刻の重複と未来の時刻を除外します。</li><li>連続する報告の間隔を求め、その始まりが計算時点から90日以内のものを使います。</li><li>前回の報告から現在までの経過時間を求めます。過去の間隔のうち、この経過時間より長いものだけを選びます。</li><li>選んだ間隔のうち、現在と同じ経過時点から24時間・48時間以内に次の報告があった件数を数えます。</li><li>少数の記録で0%や100%になりにくいよう、次の式で補正します。表示は5ポイント単位に丸めます。</li></ol>
<p class="formula">予測値 ＝（該当件数 ＋ 1）÷（選んだ間隔の件数 ＋ 2）</p><p>これはラプラス補正を加えた条件付きの集計です。例えば、選んだ10件のうち3件が24時間以内なら、（3＋1）÷（10＋2）で約33%、表示は35%になります。</p>
<h2>カレンダーの参考日</h2><p>選んだ間隔の中央値を前回の報告時刻に足し、日本時間の日付に換算します。次回の実施予定日や、最も起こりやすい日を示すものではありません。カレンダーでは履歴とは異なる破線で表示します。</p>
<h2>数値を表示しない場合</h2><p>過去の間隔が6件未満、または経過時間による絞り込み後が5件未満の場合は、集計不足として表示しません。履歴の取得に失敗している場合や、最終成功から24時間以上経過した場合も予測を休止します。閲覧中の予測も、計算から24時間を超えた場合は数値を隠します。</p>
<h2>この方法の限界</h2><p>リセットの間隔が一定だという根拠はありません。障害、モデルの公開、キャンペーン、OpenAIの方針変更などで頻度は変わります。「しばらく来ていないから、そろそろ来る」とは限りません。</p><p>集計にはOpenAIの公式発表や担当者本人の投稿から確認した記録のみを使い、日付しかない記録は時間間隔の予測から除きます。Xの取得制限による記録漏れも予測に影響します。まだ終了していない現在の間隔は過去の標本に含めておらず、長い間隔が集計に入りにくい偏りもあります。90日という期間や最低件数は、実装上の設定であり、精度が実証された値ではありません。</p><p>「95%参考区間」は、集計した比率に対するウィルソン区間です。少数の記録による幅を示すために掲載しており、次回のリセットが95%の確率でその範囲に収まるという意味ではありません。</p>
<h2>予測を保存して結果を確認する</h2><p>日本時間の各日で最初に公開用の処理が成功した予測を保存します。保存済みの予測値と計算時点は変更せず、24・48時間が経過し、その期限以降に履歴の取得が成功してから結果を判定します。期間内に完了報告の参考時刻があれば「記録あり」、なければ「記録なし」です。取得の遅延や後日の訂正で結果が変わる場合があります。</p><p>判定済みの結果がない間は「検証前」と表示します。結果がある場合は、24時間予測の平均二乗誤差（Brierスコア、0〜1）を掲載します。0に近いほど誤差が小さい指標で、正解率ではありません。毎日の予測は互いに独立した試行ではないため、単純な件数だけで精度を判断することもできません。</p><p>導入前の予測や的中実績は作成していません。<a href="https://github.com/{REPO}/blob/main/data/forecast-history.json">保存された予測記録</a>と<a href="forecast.json">現在の計算結果（JSON）</a>を公開します。計算式を変更する場合は、記録に残すモデルIDも変更します。</p>
<h2>情報源について</h2><p>計算にはOpenAIの公式発表と、Codex責任者Tibo氏などのX投稿を使用します。新しい発表を十分に確認できない場合は、予測を表示しません。<a href="about.html">掲載情報について</a>もご覧ください。</p>

<h2>予測を見る際の注意</h2><p class="method-disclaimer">{DISCLAIMER}</p><p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''


GUIDE = '''<article class="article"><h1 class="section-title">リセットの種類</h1><p class="article-lead">通常の利用枠の更新、臨時リセット、好きなときに使えるリセットチケットの違いを説明します。</p>
<h2>通常の利用枠の更新</h2><p>5時間枠や週間枠は、それぞれの利用期間に応じて回復します。残り枠と回復予定は、利用しているアプリの使用状況で確認してください。</p>
<h2>臨時の一斉リセット</h2><p>障害への対応や記念イベントなどに伴い、OpenAIが対象の利用枠を回復します。対象プランや回復する枠は、発表ごとに異なります。このサイトでは、こうした臨時リセットの履歴を掲載しています。</p>
<h2>あとから使える「リセットチケット」</h2><p>リセットチケットは、対象者に付与されたリセットを、利用者自身が必要なときに適用できる仕組みです。利用は1回限りで、有効期限や対象プランなどの条件があります。OpenAIの公式案内では「保存済みリセット」（banked reset）と呼ばれています。チケットが使える場合は、設定の「使用状況」で残り回数と有効期限を確認できます。</p>
<h2>対象プランと範囲</h2><p>発表で「全員」とされていても、有料プランの利用者やWork・Codexの利用者など、対象が限定される場合があります。ChatGPTの全モデル、画像生成、APIなどの利用枠も回復するとは限りません。</p>
<h2>次回の実施予定と予測</h2><p>当サイトでは過去のリセット報告をもとに次回の可能性を試算しています。OpenAIによる実施予定の発表ではありません。<a href="forecast.html">予測の計算方法</a>もご確認ください。</p>
<section class="article-source"><h2>関連情報</h2><ul><li><a href="https://help.openai.com/ja-jp/articles/20001498-how-banked-codex-resets-work">OpenAI：保存済みCodexリセットの仕組み</a></li><li><a href="https://help.openai.com/ja-jp/articles/11369540-using-codex-with-your-chatgpt-plan">OpenAI：ChatGPTプランでCodexを使う</a></li></ul></section><p class="article-back"><a href="./#history">履歴一覧に戻る</a></p></article>'''


ABOUT = f'''<article class="article"><h1 class="section-title">このサイトについて</h1><p class="article-lead">Codex・ChatGPT Workの臨時リセット情報をまとめた、非公式の情報サイトです。</p>
<h2>掲載している情報</h2><p>OpenAIによる臨時の利用枠リセットと、あとから使えるリセットチケットの配布について、発表日・対象・内容を時系列で紹介しています。通常の5時間枠・週間枠がいつ回復するかは、個々の利用状況によって異なるため、このサイトでは分かりません。</p>
<h2>情報の出典</h2><p>情報は<a href="{OFFICIAL_URL}">OpenAIの公式ヘルプ</a>などの公式発表と、OpenAIでCodexを率いる<strong>Tibo（ティボ）氏</strong>（Thibault Sottiaux／<a href="https://x.com/thsottiaux">@thsottiaux</a>）などのX投稿をもとにまとめています。各履歴から、元の発表や投稿に移動できます。</p>
<h2>情報の確かめ方</h2><p>投稿の内容を日本語で要約しているため、原文と表現が異なる場合があります。また、Xの一部の投稿は検索結果で確認できる文章をもとにしており、投稿全文を確認できていないものもあります。確認できない内容を推測で補わず、「予告」と「実施済み」の報告は分けて掲載します。</p>
<h2 id="dates">日時について</h2><p>掲載日時は原則として日本時間です。Xの投稿は投稿日時を表示しており、利用枠のリセットが実際に反映された時刻ではありません。OpenAIの公式記事に日付しか書かれていないときは、時刻を表示しません。</p>
<h2>更新について</h2><p>定期的に新しい発表を確認し、掲載内容を更新しています。Xの閲覧制限などによって情報の確認が遅れる場合があり、すべての発表を網羅できるとは限りません。</p>
<h2>次回リセットの予測</h2><p>過去の報告間隔から次回のリセットの可能性を試算する機能があります。ただし、予測はOpenAIの公式予定ではありません。新しい発表を十分に確認できない場合は数値を表示しません。詳しくは<a href="forecast.html">予測の計算方法</a>をご覧ください。</p>
<h2>運営・お問い合わせ</h2><p>このサイトは個人（<a href="https://github.com/mtk-ctrl">mtk-ctrl</a>）が運営しており、OpenAIとは提携していません。情報の訂正やご意見は<a href="https://github.com/{REPO}/issues">GitHubの問い合わせページ</a>からお寄せください。</p>
<h2>プライバシー</h2><p>独自のアクセス解析・広告・Cookie・会員登録は設けていません。</p><p class="article-back"><a href="./">カレンダーに戻る</a></p></article>'''


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
    history = update_history(read_json(DATA / "forecast-history.json", []), forecast, records, now, health.get("last_success_at"))
    write_json(DATA / "forecast-history.json", history)
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {
        "index": ("ChatGPT リセット履歴｜Codex・Workの臨時リセット", "Codex・ChatGPT Workの臨時リセットを一覧とカレンダーで紹介。OpenAIの公式発表やCodex責任者の投稿をもとに最新情報をまとめます。", homepage(records, updated, forecast, history)),
        "guide": ("リセットの種類｜ChatGPT リセット履歴", "通常の利用枠更新、一斉リセット、リセットチケットの違いを分かりやすく説明します。", GUIDE),
        "forecast": ("予測の計算方法｜ChatGPT リセット履歴", "独自予測の計算式、集計対象、検証方法と注意事項を掲載しています。", FORECAST_METHOD),
        "about": ("このサイトについて｜ChatGPT リセット履歴", "サイトの情報源、日時の見方、更新方法をご案内します。", ABOUT),
    }
    for key, (title, description, content) in pages.items():
        (OUT / f"{key}.html").write_text(shell(title, description, key, content, updated, show_forecast=forecast["status"] == "ok"), encoding="utf-8")
    write_json(OUT / "forecast.json", {**forecast, "scores": scores(history), "source_policy": "OpenAI公式発表・Codex責任者らのX投稿", "disclaimer": DISCLAIMER})
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    urls = [SITE_URL + "/", SITE_URL + "/guide.html", SITE_URL + "/about.html", SITE_URL + "/forecast.html"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{e(u)}</loc><lastmod>{updated}</lastmod></url>" for u in urls) + "</urlset>"
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["記録ID", "公式日付または参考日時", "日時の根拠", "種類", "根拠区分", "一次資料URL", "説明"])
    for r in records:
        when = r["official_date"] if r.get("date_precision") == "day" else jst(r["reference_at"])
        source = (r.get("official_confirmation") or {}).get("url") or r.get("original_url") or ""
        writer.writerow([r["id"], when, r["time_basis"], KINDS[r["kind"]], source_name(r), source, r.get("note", "")])
    (OUT / "data.csv").write_text("\ufeff" + stream.getvalue(), encoding="utf-8")
    items = "".join(f'<item><title>{e(record_day(r))}・{KINDS[r["kind"]]}</title><link>{SITE_URL}/#r-{r["id"].replace(":", "-")}</link><guid isPermaLink="false">{e(r["id"])}</guid><description>{e(source_name(r) + "。" + r["note"])}</description></item>' for r in records[:30])
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
