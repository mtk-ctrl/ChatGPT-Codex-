#!/usr/bin/env python3
"""Free, dependency-free collection and static publishing for Reset Log.

Upstream text is untrusted data. Never execute it, interpolate it into shell
commands, or treat its 'confirmed' flag as our own official verification.
"""
from __future__ import annotations

import argparse
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
DATA = ROOT / "data"
OUT = ROOT / "docs"
REPO = "mtk-ctrl/ChatGPT-Codex-"
SITE_URL = os.environ.get("SITE_URL", "https://mtk-ctrl.github.io/ChatGPT-Codex-").rstrip("/")
FEED_URL = "https://codex-reset.com/api/timeline"
ARCHIVE_URL = "https://codex-reset.com/ja/timeline/"
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
    nav = "".join(f'<a href="{href}" {"aria-current=page" if active == key else ""}>{label}</a>' for key, href, label in [("index", "./", "履歴一覧"), ("guide", "guide.html", "リセットの種類"), ("about", "about.html", "出典について")])
    website = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "ChatGPT リセット履歴", "url": SITE_URL + "/", "inLanguage": "ja"}, ensure_ascii=False).replace("<", "\\u003c")
    brand_tag = "h1" if active == "index" else "div"
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta name="theme-color" content="#a22c29"><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/style.css"><link rel="alternate" type="application/rss+xml" title="ChatGPT リセット履歴 更新情報" href="feed.xml"><link rel="sitemap" type="application/xml" href="sitemap.xml">
<script type="application/ld+json">{website}</script><script defer src="assets/app.js"></script></head>
<body><a class="skip" href="#main">本文へ移動</a><header class="site-header container"><div class="masthead"><div><div class="brand-line"><{brand_tag} class="brand"><a href="./">ChatGPT リセット履歴</a></{brand_tag}><span class="unofficial">非公式</span></div><p class="site-subtitle">Codex・Workの臨時リセットを掲載</p></div><p class="site-description">ChatGPT Work・Codexの利用枠に関する臨時リセットを、日時・内容・出典とともに掲載しています。</p></div><nav class="main-nav" aria-label="メインナビゲーション">{nav}</nav></header>
<main id="main" class="container">{content}</main>
<footer class="container site-footer"><p class="footer-title">ChatGPT リセット履歴</p><p>OpenAIとは関係のない非公式サイトです。</p><p>履歴データの出典：<a href="{ARCHIVE_URL}">Codex Reset</a>（掲載元のライセンス：CC BY 4.0）。日本時間への換算と分類・説明文の編集を行っています。</p><p class="footer-links"><a href="about.html">出典について</a><a href="https://github.com/{REPO}/issues">訂正の連絡</a><a href="data.csv">履歴データ（CSV）</a><a href="feed.xml">RSS</a></p><p class="muted">ページ更新：{e(jst(updated))}（日本時間）</p></footer></body></html>'''


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


def homepage(records, health, updated):
    globals_ = [r for r in records if r["kind"] == "global" and r["state"] != "announced"]
    latest = globals_[0] if globals_ else records[0]
    proof_count = sum(r["evidence"] == "official" for r in records)
    months = sorted({parse_time(r["reference_at"]).astimezone(JST).strftime("%Y-%m") for r in records}, reverse=True)
    options = "".join(f'<option value="{m}">{m[:4]}年{int(m[5:])}月</option>' for m in months)
    years = sorted({m[:4] for m in months}, reverse=True)
    month_index = '<a href="#history" class="month-all" data-month-link="all" aria-current="true">すべて</a>'
    for year in years:
        month_index += f'<h3>{year}年</h3><ul>' + "".join(f'<li><a href="#month-{m}" data-month-link="{m}">{int(m[5:])}月</a></li>' for m in months if m.startswith(year)) + '</ul>'
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
    return f'''<div class="archive-layout"><aside class="month-index"><nav aria-label="年月別の履歴"><h2>年月別</h2>{month_index}</nav></aside><div class="archive-main">
<section class="latest-record" aria-labelledby="latest-heading"><h2 id="latest-heading" class="section-title">直近のリセット</h2><div class="latest-grid"><div><p class="latest-time"><time datetime="{e(latest['reference_at'])}">{e(date_label(latest['reference_at']))}</time></p><p class="date-caption">日本時間・掲載元の参考時刻</p></div><div class="latest-description"><h3>{e(record_title(latest))}</h3><span class="badge {latest['evidence']}">{EVIDENCE[latest['evidence']]}</span><p>{e(latest['note'])}</p><a href="#r-{latest['id'].replace(':', '-')}">詳細・出典</a></div></div></section>
<p class="status-line" data-health-url="{HEALTH_URL}"><span id="health-text">{e(health_text)}</span></p>
<p class="time-note">日時は、発表・報告・観測の時刻を日本時間に換算したものです。実際の反映時刻とは異なる場合があります。<a href="about.html#dates">日時の表記について</a></p>
<section id="history" class="history-section"><div class="section-heading"><h2 class="section-title">過去のリセット</h2><p>{len(records)}件<span class="count-detail"> ／ 公式本文で日付を確認：{proof_count}件</span></p></div>
<form id="filters" aria-label="履歴の絞り込み"><input type="hidden" id="evidence-filter" value="all"><div class="filter-primary"><div class="evidence-tabs" role="group" aria-label="確認状況で絞り込む">{evidence_tabs}</div><label class="search-label"><span class="sr-only">キーワード</span><input id="search-filter" type="search" placeholder="キーワードで検索" autocomplete="off"></label></div><div class="filter-secondary"><label for="kind-filter">種類</label><select id="kind-filter"><option value="all">すべて</option><option value="global">一斉リセット</option><option value="banked">リセット券の配布</option></select><label for="month-filter">年月</label><select id="month-filter"><option value="all">すべての月</option>{options}</select><button class="reset-filter" type="reset">条件を解除</button></div></form>
<p id="result-count" class="result-count" aria-live="polite">{len(records)}件を表示</p><div class="table-wrap"><table><caption class="sr-only">ChatGPT Work・Codexの臨時リセット履歴</caption><thead><tr><th scope="col">日時（日本時間）</th><th scope="col">内容</th><th scope="col">確認状況</th><th scope="col">出典</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p id="no-results" hidden>条件に一致する履歴はありません。</p><noscript><p>絞り込みにはJavaScriptが必要です。以下に全履歴を掲載しています。</p></noscript></section>
<section class="related-guide"><h2>通常の利用枠更新との違い</h2><p>通常の5時間枠・週間枠の更新時刻は、アカウントごとに異なります。この履歴から個人の残り枠や回復時刻を確認することはできません。</p><a href="guide.html">リセットの種類</a></section></div></div>'''


GUIDE = '''<article class="article"><h1 class="section-title">リセットの種類</h1><p class="article-lead">通常の利用枠の更新、一斉リセット、リセット券の違いを説明します。</p>
<h2>通常の利用枠の更新</h2><p>5時間枠や週間枠は、それぞれの利用期間に応じて回復します。残り枠と回復予定は、利用しているアプリの使用状況で確認してください。</p>
<h2>臨時の一斉リセット</h2><p>障害への対応や記念イベントなどに伴い、OpenAIが対象の利用枠を回復します。対象プランや回復する枠は、発表ごとに異なります。このサイトでは、こうした臨時リセットの履歴を掲載しています。</p>
<h2>リセット券の配布</h2><p>公式に「保存済みリセット」と呼ばれる、後から使用できるリセットです。配布された日時と、使用して利用枠が回復する日時は異なります。このサイトでは「リセット券の配布」と表記しています。利用条件や有効期限は、自分のアカウントで確認してください。</p>
<h2>対象プランと範囲</h2><p>発表で「全員」とされていても、有料プランの利用者やWork・Codexの利用者など、対象が限定される場合があります。ChatGPTの全モデル、画像生成、APIなどの利用枠も回復するとは限りません。</p>
<h2>次回の実施予定</h2><p>過去の実施間隔から、次回の日時を確定することはできません。予定については、OpenAIの発表を確認してください。</p>
<section class="article-source"><h2>関連情報</h2><ul><li><a href="https://help.openai.com/ja-jp/articles/20001498-how-banked-codex-resets-work">OpenAI：保存済みCodexリセットの仕組み</a></li><li><a href="https://help.openai.com/ja-jp/articles/11369540-using-codex-with-your-chatgpt-plan">OpenAI：ChatGPTプランでCodexを使う</a></li></ul></section><p class="article-back"><a href="./#history">履歴一覧に戻る</a></p></article>'''


ABOUT = f'''<article class="article"><h1 class="section-title">出典について</h1><p class="article-lead">掲載情報の出典、確認状況、日時の表記について説明します。</p>
<h2>このサイトについて</h2><p>ChatGPT リセット履歴は、ChatGPT Work・Codexの臨時リセットを掲載する非公式サイトです。OpenAIとは関係ありません。運営：<a href="https://github.com/mtk-ctrl">mtk-ctrl</a>。</p>
<h2>確認状況の区分</h2><dl class="policy-list"><dt>公式本文で日付確認</dt><dd>OpenAIの公式記事で実施日を確認できた履歴です。実施時刻の記載がない場合は、日付のみの確認です。</dd><dt>担当者発言の転載</dt><dd>OpenAI担当者の発言を、他の投稿に転載・引用された文章で確認した履歴です。元の投稿本文を直接確認したものとは区別しています。公式フォーラムの一般ユーザーによる投稿も、この区分に含みます。</dd><dt>第三者サイトの記録</dt><dd>第三者サイトに掲載された履歴です。元投稿の本文は確認できていません。掲載元が「確認済み」としている場合も、公式確認とは区別します。</dd></dl>
<h2 id="dates">日時の表記</h2><p>日時は出典に記録されたUTC（協定世界時）を日本時間に換算し、分単位で掲載しています。発表・報告・観測の時刻を含むため、実際に利用枠が回復した時刻とは異なる場合があります。</p><p>公式記事で実施日のみ確認できた場合は、その日付を別に記載します。表の日時を公式発表の時刻として扱うものではありません。</p>
<h2>履歴の更新</h2><p>履歴は2時間おきに自動更新します。取得に失敗した場合は、前回の履歴を表示します。サービス側の混雑などにより、更新が遅れる場合があります。</p><p>履歴の取得と、公式本文の確認は別に行います。サイトの制作と文章の整理にはAIを使用しています。</p>
<h2>データの出典</h2><p>履歴データは<a href="{ARCHIVE_URL}">Codex Resetの公開データ</a>を利用しています。掲載元のライセンスはCC BY 4.0です。日本時間への換算と分類・説明文の編集を行い、各記録に元投稿と掲載元のリンクを付けています。</p><p>公式確認には<a href="{OFFICIAL_URL}">OpenAI公式ヘルプ</a>を利用しています。確認できた内容は、各記録の「確認状況」に記載しています。</p>
<h2>訂正の連絡</h2><p>日時、内容、出典に誤りがある場合は、<a href="https://github.com/{REPO}/issues">GitHubの連絡窓口</a>へお知らせください。すべてのリセットを網羅した一覧ではなく、個人のアカウントへの反映を保証するものでもありません。</p>
<h2>プライバシー</h2><p>独自のアクセス解析、広告、Cookie、会員登録は導入していません。更新状況の表示には、GitHub上の公開ファイルを利用しています。ホスティング事業者が取得する接続情報については、各事業者の方針が適用されます。</p><p class="article-back"><a href="./">履歴一覧に戻る</a></p></article>'''


def build():
    records = read_json(DATA / "events.json", [])
    if not records:
        raise ValueError("records are required before building")
    health = read_json(DATA / "health.json", {})
    updated = utcnow()
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {
        "index": ("ChatGPT リセット履歴｜Codex・Workの臨時リセット", "ChatGPT Work・Codexの一斉リセットとリセット券の配布履歴。日時は日本時間で表記し、内容、確認状況、出典を掲載しています。", homepage(records, health, updated)),
        "guide": ("リセットの種類｜ChatGPT リセット履歴", "通常の利用枠更新、一斉リセット、リセット券の違いと、自分の残り枠・回復予定の確認先を説明します。", GUIDE),
        "about": ("出典について｜ChatGPT リセット履歴", "公式本文の確認、担当者発言の転載、第三者サイトの記録の区分と、日時の表記、出典、訂正の連絡先を掲載しています。", ABOUT),
    }
    for key, (title, description, content) in pages.items():
        (OUT / f"{key}.html").write_text(shell(title, description, key, content, updated), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    urls = [SITE_URL + "/", SITE_URL + "/guide.html", SITE_URL + "/about.html"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{e(u)}</loc><lastmod>{updated}</lastmod></url>" for u in urls) + "</urlset>"
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["記録ID", "参考日時_JST", "日時の根拠", "種類", "根拠区分", "公式記載日", "時刻の公式確認", "元投稿", "掲載元"])
    for r in records:
        writer.writerow([r["id"], jst(r["reference_at"]), r["time_basis"], KINDS[r["kind"]], EVIDENCE[r["evidence"]], (r.get("official_confirmation") or {}).get("official_date", ""), "いいえ", r.get("original_url") or "", r["archive_url"]])
    (OUT / "data.csv").write_text("\ufeff" + stream.getvalue(), encoding="utf-8")
    items = "".join(f'<item><title>{e(jst(r["reference_at"]))} JST・{KINDS[r["kind"]]}</title><link>{SITE_URL}/#r-{r["id"].replace(":", "-")}</link><guid isPermaLink="false">{e(r["id"])}</guid><description>{e(EVIDENCE[r["evidence"]] + "。" + r["note"])}</description></item>' for r in records[:30])
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>ChatGPT リセット履歴</title><link>{SITE_URL}/</link><description>ChatGPT Work・Codexの臨時リセット履歴</description><language>ja</language>{items}</channel></rss>', encoding="utf-8")
    (OUT / "404.html").write_text(shell("ページが見つかりません｜ChatGPT リセット履歴", "履歴一覧からご確認ください。", "404", '<article class="article"><h1 class="section-title">ページが見つかりません</h1><p><a href="' + SITE_URL + '/">履歴一覧へ</a></p></article>', updated), encoding="utf-8")
    print(f"Built {len(records)} records and 3 public pages in docs/")


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
