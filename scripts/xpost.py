#!/usr/bin/env python3
"""
xpost.py — 公開した記事を X に投稿する。

検索流入が育つまでの数か月、記事を読む人をゼロで待たないための導線。

## 設計上の判断

**x-poster アプリには相乗りしない。** 理由:

1. x-poster は認証情報を1か所に集めて複数アカウントを切り替える構造で、
   2026-08-15 に「認証情報が想定と別のアカウントを指していた」事故が
   起きかけている(x-poster/DESIGN.md)。媒体の投稿が別アカウントに出る事故は
   取り返しがつかないため、認証情報ごと分離する。
2. x-poster は Cloud Scheduler の無料枠3ジョブを使い切っている(SPEC.md §2)。
3. GadgetTerminal は既に GitHub Actions で公開まで自動化されており、
   投稿もそこに置くのが素直。

**OAuth 1.0a を使う。** GitHub Actions はステートレスで、OAuth 2.0 の
リフレッシュトークンを保存し直す先が無い。1.0a のアクセストークンは無期限で
更新が要らない。画像アップロード(2.0 必須)はしない — X が記事URLから
OG カードを展開するため、画像は自動で付く。

## 必要な環境変数(GitHub Secrets)

    X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET

未設定なら何もせず正常終了する(公開そのものは止めない)。

## 使い方

    python scripts/xpost.py --dry-run      # 投稿文だけ出す。認証情報不要
    python scripts/xpost.py                # 今日ぶんを投稿
    python scripts/xpost.py --date 2026-08-19
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
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
STATE_FILE = ROOT / "data" / "xposted.json"
JST = timezone(timedelta(hours=9))

ENDPOINT = "https://api.x.com/2/tweets"
TWEET_LIMIT = 280
URL_LEN = 23  # t.co により、URLの実長に関わらず固定でこの文字数として数えられる


# ────────────────────────── 投稿文を組み立てる ──────────────────────────
def build_text(post: dict, url: str) -> str:
    """タイトル + 一言 + URL + タグ。280字に収める。

    X は全角も1文字として数える(日本語は2文字換算ではない)。
    URLは実長に関わらず23文字固定。
    """
    tags = []
    for t in (post.get("tags") or [])[:2]:
        tag = "".join(ch for ch in str(t) if ch.isalnum() or ch in "ー_")
        if tag:
            tags.append(f"#{tag}")
    tail = "\n" + url + (("\n" + " ".join(tags)) if tags else "")
    tail_len = 1 + URL_LEN + ((1 + len(" ".join(tags))) if tags else 0)

    head = str(post.get("seo_title") or post.get("title") or "").strip()
    kicker = str(post.get("kicker") or "").strip()

    budget = TWEET_LIMIT - tail_len
    if len(head) >= budget:
        return head[: budget - 1] + "…" + tail

    # 余白があれば kicker を足す。入り切らなければ足さない(途中で切れた要約は読めない)
    if kicker and len(head) + 1 + len(kicker) <= budget:
        return head + "\n" + kicker + tail
    return head + tail


def tweet_len(text: str, url: str) -> int:
    """X が数える文字数。URLは実長ではなく t.co の23文字として扱われる。"""
    return len(text) - len(url) + URL_LEN if url in text else len(text)


# ══════════════════════════════════════════════════════════════════
#  認証と送信 — ここが差し替え点
#
#  X に触るのは oauth_header() と post_tweet() の2つだけ。認証方式を
#  変えるときはこの区画だけを書き換えれば済む状態を保つこと。
#
#  ## OAuth 2.0 へ移行するのはどういうときか
#
#  **画像を自分でアップロードしたくなったとき。** v2 のメディアAPIは
#  `Authorization: Bearer` を要求し、1.0a では通らない（2026-08 時点）。
#
#  逆に言えば、それまでは移行する理由が無い:
#  - 自動生成のアイキャッチは X が og:image から勝手に展開するので、
#    アップロードしても同じ絵が出るだけ
#  - 公式サイトの製品画像を X に上げるのは「権利者のサーバーを参照する」
#    という本サイトの方針から外れる（docs/PLAYBOOK.md 3.5 を参照）
#
#  ## 移行するときに必要になること
#
#  OAuth 2.0 のアクセストークンは期限付きで、更新のたびにリフレッシュ
#  トークンも変わる。GitHub Actions はステートレスなので保存先が要る:
#
#  1. リフレッシュトークンを GitHub Secret に置く
#  2. 実行のたびにトークンを更新し、**GitHub API で Secret を書き戻す**
#     （Secrets の更新には libsodium での暗号化と、secrets への書き込み
#       権限を持つ PAT が別途必要）
#  3. post_tweet() のヘッダを Bearer に変え、oauth_header() を捨てる
#
#  認証情報が1つ増え、失敗時の切り分けが複雑になる。それに見合う理由
#  （＝上げたい画像が実際にある）が出てから着手すること。
# ══════════════════════════════════════════════════════════════════
def _quote(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")


def oauth_header(method: str, url: str, creds: dict) -> str:
    """OAuth 1.0a のヘッダを作る。

    本文が JSON の場合、署名対象に含めるのは OAuth パラメータのみ(RFC 5849)。
    ボディを署名base に入れてはいけない — 入れると 401 になる。
    """
    params = {
        "oauth_consumer_key": creds["api_key"],
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    param_str = "&".join(f"{_quote(k)}={_quote(params[k])}" for k in sorted(params))
    base = "&".join([method.upper(), _quote(url), _quote(param_str)])
    key = f'{_quote(creds["api_secret"])}&{_quote(creds["access_token_secret"])}'
    import base64
    sig = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    params["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_quote(k)}="{_quote(v)}"' for k, v in sorted(params.items()))


def post_tweet(text: str, creds: dict) -> tuple[bool, str]:
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={
            "Authorization": oauth_header("POST", ENDPOINT, creds),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode("utf-8"))
        return True, (data.get("data") or {}).get("id", "")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return False, f"HTTP {e.code} {detail}"
    except Exception as e:
        return False, str(e)


# ────────────────────────── 本体 ──────────────────────────
def load_state() -> set[str]:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            print("! xposted.json を読めないので空として扱う")
    return set()


def save_state(done: set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=0),
                          encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="対象日 (既定: 今日 JST)")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず本文だけ出す")
    ap.add_argument("--limit", type=int, default=3, help="1回に投稿する上限")
    args = ap.parse_args()

    target = args.date or datetime.now(JST).strftime("%Y-%m-%d")
    site = yaml.safe_load(SITE_CFG.read_text(encoding="utf-8"))["site"]
    base = site["base_url"].rstrip("/")

    creds = {
        "api_key": os.environ.get("X_API_KEY", ""),
        "api_secret": os.environ.get("X_API_SECRET", ""),
        "access_token": os.environ.get("X_ACCESS_TOKEN", ""),
        "access_token_secret": os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
    }
    if not args.dry_run and not all(creds.values()):
        print("! X の認証情報が無いのでスキップする（公開は完了している）")
        return 0

    done = load_state()
    posts = []
    for path in sorted(POSTS_DIR.glob(f"{target}-*.md")):
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
        slug = fm.get("slug") or path.stem
        if slug in done:
            continue
        posts.append(fm | {"slug": slug})

    if not posts:
        print(f"■ {target} に未投稿の記事は無い")
        return 0

    print(f"■ 対象 {len(posts)}件 (上限 {args.limit})")
    ok = 0
    for fm in posts[: args.limit]:
        url = f"{base}/posts/{fm['slug']}.html"
        text = build_text(fm, url)
        print("─" * 56)
        print(text)
        n = tweet_len(text, url)
        print(f"[X換算 {n}/{TWEET_LIMIT}字]" + ("  ← 超過" if n > TWEET_LIMIT else ""))
        if n > TWEET_LIMIT:
            print("! 280字を超えるので送らない")
            continue
        if args.dry_run:
            continue
        success, info = post_tweet(text, creds)
        if success:
            print(f"→ 投稿した (id={info})")
            done.add(fm["slug"])
            ok += 1
            time.sleep(3)  # 連投を避ける
        else:
            print(f"! 失敗: {info}")

    if not args.dry_run and ok:
        save_state(done)
        print(f"■ {ok}件 投稿した")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
