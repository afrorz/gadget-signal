#!/usr/bin/env python3
"""
indexnow.py — 公開したURLを IndexNow に通知する。

Google は IndexNow に対応していないが、Bing・Yandex・Seznam・Naver が対応しており、
Bing のインデックスは DuckDuckGo と ChatGPT の検索にも使われる。
サイトマップ経由のクロール待ちが数日かかるのに対し、こちらは申請ベースで数分〜数時間。

使い方:
    python scripts/indexnow.py                 # 直近1日ぶんの記事を通知
    python scripts/indexnow.py --all           # 全URLを通知（初回や大幅更新時）
    python scripts/indexnow.py --days 3        # 直近3日ぶん
    python scripts/indexnow.py --dry-run       # 送信せず対象URLだけ出す

キーは .indexnow-key に置く。build.py が public/<key>.txt として出力し、
IndexNow 側はそのファイルを取得して所有者確認を行う。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

if sys.platform == "win32":  # Windows のコンソールは既定 cp932。出力を UTF-8 に固定する
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
SITE_CFG = ROOT / "config" / "site.yaml"
KEY_FILE = ROOT / ".indexnow-key"
JST = timezone(timedelta(hours=9))

ENDPOINT = "https://api.indexnow.org/indexnow"


def load_key() -> str | None:
    if not KEY_FILE.exists():
        return None
    key = KEY_FILE.read_text(encoding="ascii").strip()
    return key or None


def collect_urls(base: str, days: int | None) -> list[str]:
    """通知するURLを集める。days=None なら全記事＋トップ。"""
    base = base.rstrip("/")
    urls: list[str] = []
    cutoff = None
    if days is not None:
        cutoff = (datetime.now(JST) - timedelta(days=days)).strftime("%Y-%m-%d")

    for path in sorted(POSTS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            continue
        try:
            fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except yaml.YAMLError:
            print(f"! front matter を読めない: {path.name}")
            continue
        if fm.get("draft"):
            continue
        date = str(fm.get("date", ""))
        if cutoff and date < cutoff:
            continue
        slug = fm.get("slug") or path.stem
        urls.append(f"{base}/posts/{slug}.html")

    if urls or days is None:
        # 記事が増えるとトップの内容も変わるので併せて通知する
        urls.insert(0, f"{base}/")
    return urls


def submit(host: str, key: str, urls: list[str]) -> bool:
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key}.txt",
        "urlList": urls,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            code = res.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # ネットワーク断などで公開自体は止めたくない
        print(f"! 送信に失敗: {e}")
        return False

    # 200/202 が成功。422 はURLとホストの不一致、403 はキー不正。
    if code in (200, 202):
        print(f"■ IndexNow に {len(urls)}件 通知 (HTTP {code})")
        return True
    reason = {400: "リクエストが不正", 403: "キーが確認できない",
              422: "URLがホストと一致しない", 429: "送りすぎ"}.get(code, "")
    print(f"! IndexNow が HTTP {code} を返した{' — ' + reason if reason else ''}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全記事を通知する")
    ap.add_argument("--days", type=int, default=1, help="直近N日ぶんを通知する（既定1）")
    ap.add_argument("--dry-run", action="store_true", help="送信せず対象を表示する")
    args = ap.parse_args()

    key = load_key()
    if not key:
        print("! .indexnow-key が無いのでスキップする")
        return 0

    site = yaml.safe_load(SITE_CFG.read_text(encoding="utf-8"))["site"]
    base = site["base_url"]
    host = base.split("//", 1)[-1].strip("/")

    urls = collect_urls(base, None if args.all else args.days)
    if not urls:
        print("■ 通知対象なし")
        return 0

    print(f"■ 対象 {len(urls)}件")
    for u in urls[:10]:
        print(f"    {u}")
    if len(urls) > 10:
        print(f"    ... 他 {len(urls) - 10}件")

    if args.dry_run:
        print("■ dry-run のため送信しない")
        return 0

    submit(host, key, urls)
    return 0  # 通知に失敗しても公開は止めない


if __name__ == "__main__":
    raise SystemExit(main())
