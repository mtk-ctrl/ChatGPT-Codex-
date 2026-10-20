"""Collect from first-party OpenAI pages and original X posts only.

Public X timelines may refuse automated requests. This is reported as unavailable
rather than silently substituting third-party data.
"""
import html
import json
import re
from datetime import datetime, timezone

OFFICIAL_URL = "https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex"
X_HANDLES = ("thsottiaux", "OpenAI")
DONE = re.compile(r"(?:we (?:have |just |now )?reset|have now reset|limits? (?:were|have been) reset|full reset (?:done|complete)|reset (?:is )?(?:complete|completed))", re.I)
TARGET = re.compile(r"(?:codex|work|usage|rate limits?)", re.I)

def plain(markup):
    markup = re.sub(r"<script\b[^>]*>.*?</script>", " ", markup, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()

def official_verified(markup):
    text = plain(markup)
    return (all(re.search(r"Sep(?:tember)?\s+" + d + r",?\s+2026", text, re.I)
                for d in ("3", "4", "7"))
            and "reset" in text.lower() and "Plus" in text and "Business" in text)

def post_ids(page, handle):
    return sorted(set(re.findall(r"/" + re.escape(handle) + r"/status/(\d{12,24})", page, re.I)), reverse=True)[:20]

def tweet_description(page):
    for prop in ("og:description", "twitter:description"):
        pattern = r'<meta[^>]+(?:property|name)=["\']' + prop + r'["\'][^>]+content=["\'](.*?)["\']'
        match = re.search(pattern, page, re.I | re.S)
        if match:
            return html.unescape(match.group(1))
    return ""

def x_record(handle, post_id, markup):
    desc = tweet_description(markup)
    if not DONE.search(desc) or not TARGET.search(desc) or re.search(r"\b(?:maybe|might|if|rumor)\b", desc, re.I):
        return None
    when = datetime.fromtimestamp(((int(post_id) >> 22) + 1288834974657)/1000, timezone.utc)
    if when > datetime.now(timezone.utc):
        return None
    return {
        "id": post_id + ":global", "post_id": post_id,
        "kind": "global", "state": "reported",
        "reference_at": when.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "date_precision": "minute",
        "time_basis": "X投稿IDから計算した投稿時刻（リセットの実施時刻ではない）",
        "time_officially_verified": False,
        "evidence": "staff_x", "products": ["codex", "chatgpt_work"],
        "note": "OpenAI関係者本人がXで利用枠リセット完了を報告。",
        "original_url": "https://x.com/" + handle + "/status/" + post_id,
        "official_confirmation": None, "reason_tags": []
    }

def trusted(record):
    if not isinstance(record, dict):
        return False
    if record.get("evidence") == "official":
        return (record.get("date_precision") == "day"
                and record.get("official_date") in ("2026-09-03", "2026-09-04", "2026-09-07")
                and (record.get("official_confirmation") or {}).get("url") == OFFICIAL_URL)
    if record.get("evidence") == "staff_x":
        return (record.get("date_precision") == "minute"
                and any(re.fullmatch("https://x.com/" + handle + r"/status/\d{12,24}",
                                     record.get("original_url", ""), re.I) for handle in X_HANDLES))
    return False

def collect_primary(data, fetch, read_json, write_json, utcnow, github_output=None, input_file=None):
    if input_file:
        raise ValueError("Importing third-party feeds is disabled.")
    checked = utcnow()
    old = read_json(data / "events.json", []) or []
    records = {r["id"]: r for r in old if trusted(r)}
    prev = read_json(data / "health.json", {}) or {}
    status = {"checked_at": checked, "last_success_at": prev.get("last_success_at"),
              "feed": "failed", "official_page": "unavailable", "x_status": "unavailable",
              "message": "一次資料を確認できません。確認済みの過去データのみ表示中。",
              "source_policy": "OpenAI official and original staff X"}
    official = False
    try:
        official = official_verified(fetch(OFFICIAL_URL))
        status["official_page"] = "verified" if official else "unverified"
    except (RuntimeError, OSError, ValueError):
        pass
    accessible = 0
    newly_added = 0
    for handle in X_HANDLES:
        try:
            listing = fetch("https://x.com/" + handle, max_bytes=500000)
            accessible += 1
            for post_id in post_ids(listing, handle):
                if post_id + ":global" in records:
                    continue
                try:
                    content = fetch("https://x.com/" + handle + "/status/" + post_id, max_bytes=500000)
                    entry = x_record(handle, post_id, content)
                    if entry is not None:
                        records[entry["id"]] = entry
                        newly_added += 1
                except (RuntimeError, OSError, ValueError):
                    continue
        except (RuntimeError, OSError, ValueError):
            continue
    status["x_status"] = "checked" if accessible == len(X_HANDLES) else ("partial" if accessible else "unavailable")
    status["feed"] = "ok" if official and accessible == len(X_HANDLES) else ("partial" if official else "failed")
    if official:
        status["last_success_at"] = checked
        status["message"] = "OpenAI公式情報を確認。X直接取得の可否は別途表示。"
    status["new_x_records"] = newly_added
    status["record_count"] = len(records)
    sorted_records = sorted(records.values(), key=lambda r: r["reference_at"], reverse=True)
    changed = write_json(data / "events.json", sorted_records)
    write_json(data / "health.json", status)
    if github_output:
        with open(github_output, "a", encoding="utf-8") as stream:
            stream.write("records_changed=" + str(changed).lower() + "\n")
    print(json.dumps({"status": status["feed"], "official": status["official_page"], "x": status["x_status"], "records": len(records)}, ensure_ascii=False))
    return 0 if official else 2
