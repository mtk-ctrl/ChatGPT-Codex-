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
EVIDENCE = {"official": "実施日は公式確認", "quoted": "担当者発言の転載", "third_party": "第三者の記録"}
REASONS = {
    "incident": "障害・不具合への対応に伴う記録です。",
    "compensation": "利用状況の問題への補償に伴う記録です。",
    "launch": "モデルや機能の公開に伴う記録です。",
    "milestone": "利用者数などの節目に伴う記録です。",
    "promotion": "記念・キャンペーンに伴う記録です。",
    "promo": "記念・キャンペーンに伴う記録です。",
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
            note = editorial.get(post_id) or (REASONS[reasons[0]] if reasons else "公開された履歴サイトに記録された回です。対象と詳細は出典をご確認ください。")
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
    nav = "".join(f'<a href="{href}" {"aria-current=page" if active == key else ""}>{label}</a>' for key, href, label in [("index", "./", "最新・履歴"), ("guide", "guide.html", "リセットの種類"), ("about", "about.html", "根拠と更新方針")])
    website = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "リセットログ", "url": SITE_URL + "/", "inLanguage": "ja"}, ensure_ascii=False).replace("<", "\\u003c")
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta name="theme-color" content="#164b3d"><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/style.css"><link rel="alternate" type="application/rss+xml" title="リセットログ 更新情報" href="feed.xml"><link rel="sitemap" type="application/xml" href="sitemap.xml">
<script type="application/ld+json">{website}</script><script defer src="assets/app.js"></script></head>
<body><a class="skip" href="#main">本文へ移動</a><header class="site-header"><div class="container header-inner"><a class="brand" href="./"><span class="brand-icon" aria-hidden="true">↻</span><span>リセットログ<small>ChatGPT / Codex</small></span></a><nav aria-label="メインナビゲーション">{nav}</nav><span class="unofficial">非公式</span></div></header>
<main id="main" class="container">{content}</main>
<footer class="container site-footer"><p>リセットログ — ChatGPT Work・Codexの利用枠の記録</p><p>OpenAIとは関係のない非公式サイトです。公開情報を整理し、根拠の確認状況を表示します。</p><p>データの出典：<a href="{ARCHIVE_URL}">Codex Reset</a>（掲載元の表示：CC BY 4.0）。日時・区分を再構成しています。<a href="about.html">出典・確認方法</a> · <a href="https://github.com/{REPO}">運営・訂正窓口</a> · <a href="data.csv">履歴CSV</a> · <a href="feed.xml">RSS</a></p><p class="muted">履歴ページ生成：{e(jst(updated))} JST</p></footer></body></html>'''


def record_row(record):
    proof = record.get("official_confirmation")
    evidence = record["evidence"]
    state = {"reported": "完了の記録", "announced": "予告の記録", "observed": "観測の記録"}[record["state"]]
    official = (f'<p class="proof-note">公式記事の日付：{e(proof["official_date"])}。時刻の公式記載なし。</p>' + link(proof["url"], "確認した公式記事")) if proof else ""
    quotation = record.get("quotation_confirmation")
    quoted_source = link(quotation["url"], "確認した転載") if quotation else ""
    original = link(record.get("original_url"), "元投稿（本文未確認）")
    products = "・".join({"codex": "Codex", "chatgpt_work": "Work"}[p] for p in record["products"]) or "対象は出典参照"
    return f'''<tr id="r-{e(record['id'].replace(':', '-'))}" data-record data-kind="{record['kind']}" data-evidence="{evidence}" data-month="{e(parse_time(record['reference_at']).astimezone(JST).strftime('%Y-%m'))}">
<td data-label="参考日時（日本時間）"><time datetime="{e(record['reference_at'])}">{e(jst(record['reference_at']))}</time><small>JST・履歴サイトの参考時刻</small></td>
<td data-label="種類・対象"><span class="kind">{KINDS[record['kind']]}</span><small>{e(products)}</small><span class="state">{state}</span></td>
<td data-label="根拠・内容"><span class="badge {evidence}">{EVIDENCE[evidence]}</span><p>{e(record['note'])}</p>{official}</td>
<td data-label="出典"><div class="source-links">{quoted_source}{original}{link(record['archive_url'], '掲載元の履歴')}</div></td></tr>'''


def homepage(records, health, updated):
    globals_ = [r for r in records if r["kind"] == "global" and r["state"] != "announced"]
    latest = globals_[0] if globals_ else records[0]
    proof_count = sum(r["evidence"] == "official" for r in records)
    months = sorted({parse_time(r["reference_at"]).astimezone(JST).strftime("%Y-%m") for r in records}, reverse=True)
    options = "".join(f'<option value="{m}">{m[:4]}年{int(m[5:])}月</option>' for m in months)
    rows = "".join(record_row(r) for r in records)
    check = health.get("checked_at", updated)
    if health.get("feed") == "ok" and health.get("last_success_at"):
        health_text = "自動取得の最終成功：" + jst(health["last_success_at"]) + " JST。公式本文の確認状況は各行をご覧ください。"
    elif health.get("feed") == "failed":
        health_text = "情報の取得に失敗しています。保存済みの履歴を掲載しています。"
    else:
        health_text = "初期データ作成：" + jst(check) + " JST。自動更新の初回成功は未確認です。"
    return f'''<section class="hero"><div class="eyebrow">利用枠の回復を、日本時間と根拠で。</div><h1>ChatGPTの利用枠、<br>いつリセットされた？</h1><p class="hero-lead">ChatGPT Work・Codexの臨時リセットを記録しています。<br class="desktop">過去の日時と、どこまで確認できた情報かを一緒に確認できます。</p><a class="button" href="#history">過去の履歴を見る <span aria-hidden="true">↓</span></a><div class="hero-note">このページは、会話やパスワードの初期化ではなく、利用枠の回復を扱います。</div></section>
<section class="latest-panel" aria-labelledby="latest-heading"><div><div class="eyebrow light">LATEST RECORD</div><h2 id="latest-heading">直近の一斉リセットの公開記録</h2><p class="latest-time">{e(jst(latest['reference_at']))}<span>ごろ / 日本時間</span></p><p>履歴サイトが掲載する参考時刻です。全アカウントの実施時刻を確認したものではありません。</p></div><div class="latest-side"><span class="badge {latest['evidence']}">{EVIDENCE[latest['evidence']]}</span><p>{e(latest['note'])}</p><a href="#r-{latest['id'].replace(':', '-')}">この記録の出典を見る →</a></div></section>
<div class="status-line" data-health-url="{HEALTH_URL}"><span class="status-dot" aria-hidden="true"></span><span id="health-text">{e(health_text)}</span></div>
<section class="reading-note"><strong>時刻と根拠の読み方</strong><p>日時は発表・報告・観測などの参考時刻です。<span class="inline-badge">実施日は公式確認</span>の表示があっても、時刻まで公式に確認できたとは限りません。各行に確認範囲を明記します。<a href="about.html">詳しく見る →</a></p></section>
<section id="history" class="history-section"><div class="section-heading"><div><div class="eyebrow">RESET HISTORY</div><h2>リセット履歴</h2></div><p>{len(records)}件の記録 / 実施日を公式本文で確認：{proof_count}件</p></div>
<form class="filters" id="filters" aria-label="履歴の絞り込み"><label>種類<select id="kind-filter"><option value="all">すべて</option><option value="global">一斉リセット</option><option value="banked">リセット券の配布</option></select></label><label>根拠<select id="evidence-filter"><option value="all">すべて</option><option value="official">実施日は公式確認</option><option value="quoted">担当者発言の転載</option><option value="third_party">第三者の記録</option></select></label><label>年月<select id="month-filter"><option value="all">すべての月</option>{options}</select></label><label class="search-label">キーワード<input id="search-filter" type="search" placeholder="モデル名・節目など" autocomplete="off"></label><button class="reset-filter" type="reset">条件をクリア</button></form>
<p id="result-count" class="result-count" aria-live="polite">{len(records)}件を表示</p><div class="table-wrap"><table><caption class="sr-only">ChatGPT Work・Codexの利用枠リセット履歴</caption><thead><tr><th scope="col">参考日時（日本時間）</th><th scope="col">種類・対象</th><th scope="col">根拠・内容</th><th scope="col">出典</th></tr></thead><tbody>{rows}</tbody></table></div><p id="no-results" hidden>条件に合う記録がありません。絞り込み条件を変えてください。</p><noscript><p>JavaScriptが無効なため絞り込みは使えません。全履歴はそのままお読みいただけます。</p></noscript></section>
<section class="bottom-guide"><div><div class="eyebrow">BEFORE YOU CHECK</div><h2>自分のリセット時刻と、一斉リセットの違い</h2><p>通常の5時間枠・週間枠の更新はアカウントごとに異なります。この履歴から、あなたの残り枠や次の回復時刻は判定できません。</p></div><a class="text-button" href="guide.html">3種類のリセットを確認 →</a></section>'''


GUIDE = '''<article class="article"><div class="eyebrow">GUIDE</div><h1>ChatGPTのリセットはいつ？<br>3種類の違い</h1><p class="article-lead">『リセット』という言葉には、通常の利用枠の更新と、OpenAIが臨時に行う回復、保存して使うリセット券があります。</p>
<h2>1. 通常の利用枠の更新</h2><p>自分のアカウントの利用期間に応じて回復するものです。Work・Codexの現在の残り枠と回復時刻は、ChatGPTの「設定 → 使用状況」で確認します。このサイトは個人の利用状況にはアクセスしません。</p>
<h2>2. 臨時の一斉リセット</h2><p>障害への対応や記念イベントなどに伴い、OpenAIが対象の利用枠を直接回復するものです。対象プランや対象となる枠は発表ごとに異なります。このサイトの「一斉リセット」は、この公開記録をまとめたものです。</p>
<h2>3. 保存して使うリセット券</h2><p>アカウントに付与され、使用するか期限が切れるまで保存されるリセットです。付与された日時と、実際に使って利用枠が回復する日時は異なるため、履歴では「リセット券の配布」と表示します。利用条件と期限は自分のアカウントで確認してください。</p>
<h2>「全員」「ChatGPT」の範囲に注意</h2><p>発表で「全員」と表現されていても、有料プランの対象者やWork・Codex利用者などの範囲を指すことがあります。通常のChatのすべてのモデル、画像生成、APIなどの枠も一緒に回復したとは判断しません。</p>
<h2>次回の一斉リセットは予測できる？</h2><p>過去の間隔は、次回の実施予定ではありません。このサイトでは、過去の記録から算出した確率やカウントダウンを実施予定として表示しません。</p>
<div class="article-source"><strong>確認先</strong><p><a href="https://help.openai.com/ja-jp/articles/20001498-how-banked-codex-resets-work">OpenAI公式：保存済みCodexリセットの仕組み ↗</a><br><a href="https://help.openai.com/ja-jp/articles/11369540-using-codex-with-your-chatgpt-plan">OpenAI公式：ChatGPTプランでCodexを使う ↗</a></p></div><a class="text-button" href="./#history">リセット履歴へ戻る →</a></article>'''


ABOUT = f'''<article class="article"><div class="eyebrow">SOURCES & POLICY</div><h1>根拠と更新方針</h1><p class="article-lead">「確認済み」の範囲がわかる、利用枠リセットの記録を目指しています。</p>
<h2>このサイトについて</h2><p>リセットログは、ChatGPT Work・Codexの利用枠の臨時回復を日本語で整理する非公式の情報サイトです。運営：<a href="https://github.com/mtk-ctrl">mtk-ctrl</a>。OpenAIとは関係ありません。</p>
<h2>根拠の3区分</h2><dl class="policy-list"><dt>実施日は公式確認</dt><dd>OpenAI公式本文を直接読み、該当の実施を確認した記録です。公式が日付だけを述べている場合、時刻は公式確認済みとは扱いません。</dd><dt>担当者発言の転載</dt><dd>担当者の発言を転載・引用で確認した記録です。元の本文の直接確認とは分けます。公式フォーラム上の一般ユーザーによる投稿も、この基準で区別します。</dd><dt>第三者の記録</dt><dd>独立した履歴サイトの記録を取得したものです。掲載元が「confirmed」としていても、当サイトの「公式確認」に自動昇格させません。</dd></dl>
<h2>日本時間と時刻の扱い</h2><p>情報源がUTCで記録した時刻を日本時間（JST、UTC+9）に換算します。実施時刻・観測時刻・発表時刻は一致するとは限りません。現在の自動取得データでは発表・報告・観測の区別を原文から一律に確定できないため、「履歴サイトの参考時刻」と表示しています。</p><p>情報源によって時刻が違う場合があります。元投稿の本文と実施時刻を直接確認できるまでは、利用枠がその分に全員一斉に回復したとは断定しません。</p>
<h2>情報の取得と更新</h2><p>専用のGitHub Actionsで2時間おきに取得する設定です。実行はGitHub側の混雑や制限によって遅れる場合があります。更新があった場合に履歴ページを生成し、取得状況は別途保存します。新しい情報を取得できない場合も、前回の履歴を保持します。</p><p>プログラムで時刻の換算、分類、重複排除を行い、初期の説明文や構築にはAIの支援を利用しています。日々の処理に有料AI APIは使いません。データを取得できたことと、公式本文を直接確認したことは別々に管理します。</p>
<h2>出典と再利用</h2><p>初期・自動取得の履歴データ：<a href="{ARCHIVE_URL}">Codex Resetの公開データ ↗</a>。掲載元はCC BY 4.0と表示しています。当サイトでは日時・種類・対象・リンクなどの事実項目を再構成し、英文の投稿全文や説明文を一括転載していません。各記録の元投稿と掲載元もリンクします。</p><p>公式確認の根拠：<a href="{OFFICIAL_URL}">OpenAI公式ヘルプ ↗</a>。個別の確認内容はリポジトリの <code>data/official-confirmations.json</code> に記録します。</p>
<h2>訂正と運営</h2><p>日付、区分、対象、出典に誤りがあれば、<a href="https://github.com/{REPO}/issues">GitHubの訂正窓口 ↗</a>からお知らせください。履歴の訂正はコードと同様に変更履歴へ残します。網羅性や、個人のアカウントへの反映を保証する一覧ではありません。</p>
<h2>プライバシー</h2><p>当サイト独自のアクセス解析、広告、Cookie、アカウント登録は導入していません。最新の取得状況を表示するため、閲覧時に公開されたGitHub上の状態ファイルへ接続します。ホスティング事業者が技術上取得する接続情報は、各事業者の方針が適用されます。</p><a class="text-button" href="./">最新・履歴へ戻る →</a></article>'''


def build():
    records = read_json(DATA / "events.json", [])
    if not records:
        raise ValueError("records are required before building")
    health = read_json(DATA / "health.json", {})
    updated = utcnow()
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {
        "index": ("ChatGPTのリセット履歴｜利用枠の回復を日本時間と根拠で確認", "ChatGPT Work・Codexの一斉リセットとリセット券の配布履歴。日本時間、対象、公式本文の確認状況、出典を掲載する非公式サイトです。", homepage(records, health, updated)),
        "guide": ("ChatGPTのリセットはいつ？5時間・週間・一斉回復の違い｜リセットログ", "通常の利用枠更新、一斉リセット、保存して使うリセット券の違いと、自分の回復時刻の確認先を説明します。", GUIDE),
        "about": ("根拠と更新方針｜ChatGPT・Codexリセットログ", "公式本文の直接確認、担当者発言の転載、第三者記録の区分と、日本時間の扱い、出典、訂正方法を掲載します。", ABOUT),
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
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>リセットログ</title><link>{SITE_URL}/</link><description>ChatGPT Work・Codexの臨時リセット公開記録</description><language>ja</language>{items}</channel></rss>', encoding="utf-8")
    (OUT / "404.html").write_text(shell("ページが見つかりません｜リセットログ", "最新の履歴ページへお進みください。", "index", '<article class="article"><h1>ページが見つかりません</h1><p><a href="' + SITE_URL + '/">最新・履歴へ進む →</a></p></article>', updated), encoding="utf-8")
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
