#!/usr/bin/env python3
"""
crowdfunding.py — クラウドファンディング発の新着プロダクトを収集する。

RSSを出していないプラットフォームが多いため、方式を2つ用意している。

  sitemap 方式  サイトマップから新着プロジェクトURLを拾い、各ページの
                OGPタグ（og:title / og:description / og:image）を読む。
                Makuake で動作を確認済み。
  atom 方式     公式のAtomフィードを読む。Kickstarter はブラウザ相当の
                User-Agent を送らないと 406 を返すことがある。

守っていること:
  - robots.txt で禁止されている領域は取りに行かない（設定側で制御）
  - リクエスト間隔を空ける（既定 1.2 秒）
  - 1回の実行で取得するページ数に上限を設ける
  - 取得できないソースがあっても例外で止めず、そのソースを飛ばす

collect.py から呼ばれる。単体でも動く:
    python3 scripts/crowdfunding.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "feeds.yaml"

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ガジェット/テック系のプロジェクトだけを残すための手がかり。
# Makuake は食品・ファッションなども多いため、この網で絞る。
TECH_HINTS = [
    "ガジェット", "スマホ", "スマートフォン", "イヤホン", "ヘッドホン", "スピーカー",
    "カメラ", "モバイルバッテリー", "充電", "USB", "Type-C", "ワイヤレス", "Bluetooth",
    "Wi-Fi", "スマートウォッチ", "ウェアラブル", "プロジェクター", "モニター", "ディスプレイ",
    "キーボード", "マウス", "PC", "パソコン", "タブレット", "ドローン", "ロボット",
    "センサー", "IoT", "AI", "電動", "バッテリー", "LED", "ライト", "時計", "オーディオ",
    "レンズ", "SSD", "ストレージ", "ハブ", "ドック", "アプリ連携", "リモコン", "掃除機",
    "3Dプリンタ", "電子", "デバイス", "端末", "アダプタ", "ケーブル", "軽量", "折りたたみ",
]

_TAG = re.compile(r'<meta[^>]+property=["\']og:(title|description|image)["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_TAG_ALT = re.compile(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*property=["\']og:(title|description|image)["\']', re.I)
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.I | re.S)
_LASTMOD = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)


def _get(url: str, ua: str, timeout: int = 20) -> str | None:
    """1本取得する。失敗しても例外を投げず None を返す。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        return raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"    ! {e.code} {url}", file=sys.stderr)
    except Exception as e:
        print(f"    ! {type(e).__name__} {url}", file=sys.stderr)
    return None


def _ogp(html_text: str) -> dict:
    """OGPタグを取り出す。属性の順序が逆のパターンにも対応する。"""
    out: dict[str, str] = {}
    for key, val in _TAG.findall(html_text):
        out.setdefault(key.lower(), val.strip())
    for val, key in _TAG_ALT.findall(html_text):
        out.setdefault(key.lower(), val.strip())
    return out


def _unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s or "").strip()


def looks_tech(text: str) -> bool:
    """ガジェット系かどうかを、手がかり語の有無で判定する。"""
    t = text.lower()
    return any(h.lower() in t for h in TECH_HINTS)


# ────────────────────────── sitemap 方式 ──────────────────────────
def collect_sitemap(src: dict, cfg: dict, seen: set[str], id_of=None) -> list[dict]:
    """サイトマップから新着プロジェクトを拾い、各ページのOGPを読む。"""
    ua = cfg.get("user_agent", BROWSER_UA)
    interval = float(cfg.get("request_interval", 1.2))
    max_pages = int(cfg.get("max_pages_per_run", 40))
    pattern = re.compile(src["project_pattern"])

    index = _get(src["sitemap_index"], ua)
    if not index:
        return []
    children = _LOC.findall(index)
    if not children:
        children = [src["sitemap_index"]]

    # 新しいプロジェクトは後ろのサイトマップに入るので、末尾から見る
    candidates: list[tuple[str, str]] = []
    for child in list(reversed(children))[: int(src.get("scan_sitemaps", 2))]:
        time.sleep(interval)
        body = _get(child, ua)
        if not body:
            continue
        for block in _URL_BLOCK.findall(body):
            loc = _LOC.search(block)
            if not loc or not pattern.match(loc.group(1)):
                continue
            lm = _LASTMOD.search(block)
            candidates.append((loc.group(1), lm.group(1) if lm else ""))

    # lastmod の新しい順。未取得のものだけを対象にする
    candidates.sort(key=lambda x: x[1], reverse=True)
    def _known(u: str) -> bool:
        return (id_of(u) in seen) if id_of else (u in seen)

    todo = [(u, lm) for u, lm in candidates if not _known(u)][:max_pages]
    print(f"  + {src['id']}: サイトマップ {len(candidates)}件 → 新規 {len(todo)}件を確認")

    items = []
    for url, lastmod in todo:
        time.sleep(interval)
        page = _get(url, ua)
        if not page:
            continue
        og = _ogp(page)
        title = _unescape(og.get("title", ""))
        desc = _unescape(og.get("description", ""))
        if not title:
            continue
        if src.get("tech_filter", True) and not looks_tech(f"{title} {desc}"):
            continue
        items.append({
            "title": title[:300],
            "url": url,
            "summary": desc[:400],
            "image": og.get("image", ""),
            "published": _to_iso(lastmod),
            "source_id": src["id"],
            "source": src["name"],
            "category": src.get("category", "weird"),
            "tier": src.get("tier", 1),
            "kind": "crowdfunding",
        })
    print(f"    → ガジェット系として {len(items)}件を採用")
    return items


def _to_iso(lastmod: str) -> str:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(lastmod[:25] if "T" in lastmod else lastmod[:10], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


# ────────────────────────── atom 方式 ──────────────────────────
def collect_atom(src: dict, cfg: dict) -> list[dict]:
    """公式Atomフィードを読む。ブラウザ相当のUAで取りに行く。"""
    import feedparser
    ua = BROWSER_UA if src.get("browser_ua") else cfg.get("user_agent", BROWSER_UA)
    body = _get(src["url"], ua)
    if not body:
        print(f"  ! {src['id']}: 取得できず（この回はスキップ）", file=sys.stderr)
        return []
    feed = feedparser.parse(body)
    items = []
    for e in feed.entries[: int(src.get("limit", 30))]:
        link = e.get("link")
        if not link:
            continue
        tt = e.get("published_parsed") or e.get("updated_parsed")
        pub = datetime(*tt[:6], tzinfo=timezone.utc).isoformat() if tt else datetime.now(timezone.utc).isoformat()
        items.append({
            "title": re.sub(r"<[^>]+>", " ", e.get("title", "")).strip()[:300],
            "url": link,
            "summary": re.sub(r"<[^>]+>", " ", e.get("summary", "")).strip()[:400],
            "image": "",
            "published": pub,
            "source_id": src["id"],
            "source": src["name"],
            "category": src.get("category", "weird"),
            "tier": src.get("tier", 1),
            "kind": "crowdfunding",
        })
    print(f"  + {src['id']}: {len(items)}件")
    return items


# ────────────────────────── 入口 ──────────────────────────
def collect_all(seen: set[str] | None = None, id_of=None) -> list[dict]:
    cfg_all = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    cf = cfg_all.get("crowdfunding") or {}
    if not cf.get("enabled", True):
        return []
    seen = seen or set()
    out: list[dict] = []
    print(f"■ クラウドファンディング収集 — {len(cf.get('sources', []))}ソース")
    for src in cf.get("sources", []):
        if not src.get("enabled", True):
            continue
        try:
            if src.get("type") == "sitemap":
                out.extend(collect_sitemap(src, cf, seen, id_of))
            elif src.get("type") == "atom":
                out.extend(collect_atom(src, cf))
        except Exception as e:  # 1ソースの失敗で全体を止めない
            print(f"  ! {src.get('id')}: {type(e).__name__}: {e}", file=sys.stderr)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    got = collect_all()
    print(f"\n合計 {len(got)}件")
    for g in got[:15]:
        print(f"  [{g['source']}] {g['title'][:70]}")
