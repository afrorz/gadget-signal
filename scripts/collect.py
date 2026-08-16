#!/usr/bin/env python3
"""
collect.py — 海外ガジェット情報の収集エンジン

config/feeds.yaml のソースを巡回し、
  1. 取得  2. 正規化  3. 重複排除  4. 話題クラスタリング  5. スコアリング
を行って data/digest/YYYY-MM-DD.{json,md} を出力する。

使い方:
    python3 scripts/collect.py                 # 今日のダイジェストを作る
    python3 scripts/collect.py --top 25        # 上位25件だけ拾う
    python3 scripts/collect.py --category pc   # カテゴリ限定
    python3 scripts/collect.py --dry-run       # seen.json を更新しない
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import yaml

try:
    import crowdfunding
except Exception:  # 収集モジュールが無くてもRSS収集は動かす
    crowdfunding = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "feeds.yaml"
DATA = ROOT / "data"
DIGEST_DIR = DATA / "digest"
SEEN_PATH = DATA / "seen.json"

JST = timezone(timedelta(hours=9))

# 記事タイトルの比較で無視する語
STOPWORDS = set("""
a an the and or of for to in on with is are be by from at as its it this that new
""".split())

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|ref|source$|mc_)", re.I)


# ────────────────────────────── ユーティリティ ──────────────────────────────
def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def canonical_url(url: str) -> str:
    """トラッキングパラメータを落として URL を正規化する。"""
    try:
        p = urlparse(url)
    except ValueError:
        return url
    query = "&".join(
        q for q in p.query.split("&")
        if q and not TRACKING_PARAMS.match(q.split("=")[0])
    )
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", query, ""))


def item_id(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:16]


def strip_html(text: str, limit: int = 400) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def title_tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def parse_time(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        tt = entry.get(key)
        if tt:
            return datetime(*tt[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


# ────────────────────────────── 収集 ──────────────────────────────
def fetch_source(src: dict, defaults: dict) -> list[dict]:
    url = src["url"]
    agent = defaults.get("user_agent", "GadgetSignalBot/1.0")
    max_items = defaults.get("max_items_per_feed", 40)

    for attempt in (1, 2):
        try:
            feed = feedparser.parse(url, agent=agent)
            if feed.entries:
                break
            if getattr(feed, "status", None) in (403, 429) and attempt == 1:
                time.sleep(3)
                continue
            break
        except Exception as exc:  # ネットワーク断でも全体を止めない
            print(f"  ! {src['id']}: {exc}", file=sys.stderr)
            return []

    if not feed.entries:
        status = getattr(feed, "status", "?")
        print(f"  ! {src['id']}: 0件 (status={status})", file=sys.stderr)
        return []

    items = []
    for e in feed.entries[:max_items]:
        link = e.get("link")
        if not link:
            continue
        items.append({
            "id": item_id(link),
            "title": strip_html(e.get("title", ""), 300),
            "url": link,
            "canonical": canonical_url(link),
            "summary": strip_html(e.get("summary", e.get("description", "")), 400),
            "published": parse_time(e).isoformat(),
            "source_id": src["id"],
            "source": src["name"],
            "category": src["category"],
            "tier": src.get("tier", 2),
            "kind": "news",
        })
    print(f"  + {src['id']}: {len(items)}件")
    return items


# ────────────────────────────── スコアリング ──────────────────────────────
def score_item(item: dict, cfg_scoring: dict, now: datetime) -> tuple[int, list[str]]:
    text = f"{item['title']} {item['summary']}".lower()
    score, reasons = 0, []

    for kw, pts in cfg_scoring.get("boost", {}).items():
        if kw.lower() in text:
            score += pts
            reasons.append(f"+{pts} {kw}")
    for kw, pts in cfg_scoring.get("penalty", {}).items():
        if kw.lower() in text:
            score += pts
            reasons.append(f"{pts} {kw}")

    kb = cfg_scoring.get("kind_bonus", {}).get(item.get("kind", "news"), 0)
    if kb:
        score += kb
        reasons.append(f"+{kb} クラファン発")

    tb = cfg_scoring.get("tier_bonus", {}).get(item["tier"], 0)
    if tb:
        score += tb
        reasons.append(f"+{tb} tier{item['tier']}")

    published = datetime.fromisoformat(item["published"])
    age_h = (now - published).total_seconds() / 3600
    if age_h <= cfg_scoring.get("fresh_hours", 36):
        b = cfg_scoring.get("fresh_bonus", 3)
        score += b
        reasons.append(f"+{b} fresh")
    elif age_h > 24 * 7:
        score -= 5
        reasons.append("-5 stale")

    return score, reasons


def cluster(items: list[dict]) -> list[dict]:
    """タイトルの語の重なりで「同じ話題」をまとめ、複数ソースが報じたものを重要とみなす。"""
    clusters: list[dict] = []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        toks = title_tokens(it["title"])
        if not toks:
            clusters.append({"items": [it], "tokens": toks})
            continue
        placed = False
        for c in clusters:
            overlap = len(toks & c["tokens"])
            denom = min(len(toks), len(c["tokens"])) or 1
            if overlap / denom >= 0.55 and overlap >= 3:
                c["items"].append(it)
                c["tokens"] |= toks
                placed = True
                break
        if not placed:
            clusters.append({"items": [it], "tokens": toks})
    return clusters


# ────────────────────────────── メイン ──────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30, help="ダイジェストに載せる件数")
    ap.add_argument("--category", choices=["smartphone", "pc", "weird"])
    ap.add_argument("--dry-run", action="store_true", help="seen.json を更新しない")
    ap.add_argument("--min-score", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config()
    defaults = cfg.get("defaults", {})
    sources = [s for s in cfg["sources"] if s.get("enabled", True)]
    if args.category:
        sources = [s for s in sources if s["category"] == args.category]

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict = json.loads(SEEN_PATH.read_text()) if SEEN_PATH.exists() else {}

    print(f"■ 収集開始 — RSS {len(sources)}ソース")
    raw: list[dict] = []
    for src in sources:
        raw.extend(fetch_source(src, defaults))

    # クラウドファンディング（RSSを出していないプラットフォーム）
    if crowdfunding is not None and not args.category:
        try:
            cf_items = crowdfunding.collect_all(seen=set(seen.keys()), id_of=item_id)
            for it in cf_items:
                it.setdefault("id", item_id(it["url"]))
                it.setdefault("canonical", canonical_url(it["url"]))
            raw.extend(cf_items)
        except Exception as e:
            print(f"  ! クラウドファンディング収集を飛ばしました: {e}", file=sys.stderr)

    # 1. URL重複を除去（同一記事が複数フィードに出るケース）
    by_id: dict[str, dict] = {}
    for it in raw:
        by_id.setdefault(it["id"], it)

    # 2. 既出を除去
    fresh = [it for it in by_id.values() if it["id"] not in seen]
    print(f"■ 取得 {len(raw)}件 → 重複除去 {len(by_id)}件 → 新規 {len(fresh)}件")

    # 3. クラスタリング（複数ソースが報じた話題を加点）
    now = datetime.now(timezone.utc)
    scoring = cfg.get("scoring", {})
    clusters = cluster(fresh)

    ranked = []
    for c in clusters:
        lead = max(c["items"], key=lambda x: (-x["tier"], x["published"]))
        base, reasons = score_item(lead, scoring, now)
        n_sources = len({i["source_id"] for i in c["items"]})
        if n_sources > 1:
            bonus = 4 * (n_sources - 1)
            base += bonus
            reasons.append(f"+{bonus} {n_sources}媒体が報道")
        lead = dict(lead)
        lead["score"] = base
        lead["reasons"] = reasons
        lead["also_covered_by"] = sorted(
            {i["source"] for i in c["items"]} - {lead["source"]}
        )
        lead["related_urls"] = [i["url"] for i in c["items"] if i["url"] != lead["url"]][:4]
        ranked.append(lead)

    ranked = [r for r in ranked if r["score"] >= args.min_score]
    ranked.sort(key=lambda x: (-x["score"], x["published"]), reverse=False)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    top = ranked[: args.top]

    # 4. 出力
    today = datetime.now(JST).strftime("%Y-%m-%d")
    payload = {
        "date": today,
        "generated_at": datetime.now(JST).isoformat(),
        "stats": {
            "fetched": len(raw),
            "unique": len(by_id),
            "new": len(fresh),
            "clusters": len(clusters),
            "selected": len(top),
        },
        "items": top,
    }
    (DIGEST_DIR / f"{today}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DIGEST_DIR / f"{today}.md").write_text(render_markdown(payload, cfg), encoding="utf-8")

    if not args.dry_run:
        for it in fresh:
            seen[it["id"]] = it["published"]
        # 30日より古い記録は捨てる
        cutoff = (now - timedelta(days=30)).isoformat()
        seen = {k: v for k, v in seen.items() if v >= cutoff}
        SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")

    print(f"■ 出力 data/digest/{today}.md ({len(top)}件)")
    return 0


CAT_LABEL = {"smartphone": "スマホ・ウェアラブル", "pc": "PC・周辺機器・自作", "weird": "変わり種・中華"}


def render_markdown(payload: dict, cfg: dict) -> str:
    s = payload["stats"]
    lines = [
        f"# 海外ガジェット・ダイジェスト {payload['date']}",
        "",
        f"取得 {s['fetched']} / 新規 {s['new']} / 話題 {s['clusters']} → 候補 {s['selected']}件",
        "",
        "> 記事化する候補にチェックを入れて、そのまま執筆プロンプトに渡す。",
        "",
    ]
    for cat in ("smartphone", "pc", "weird"):
        rows = [i for i in payload["items"] if i["category"] == cat]
        if not rows:
            continue
        lines += [f"## {CAT_LABEL[cat]}", ""]
        for i, it in enumerate(rows, 1):
            pub = datetime.fromisoformat(it["published"]).astimezone(JST).strftime("%m/%d %H:%M")
            mark = "【クラファン】" if it.get("kind") == "crowdfunding" else ""
            lines.append(f"- [ ] **[{it['score']}pt] {mark}{it['title']}**")
            lines.append(f"  - {it['source']} / {pub} JST — {it['url']}")
            if it["also_covered_by"]:
                lines.append(f"  - 他媒体: {', '.join(it['also_covered_by'])}")
            if it["summary"]:
                lines.append(f"  - {it['summary'][:180]}")
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
