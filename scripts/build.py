#!/usr/bin/env python3
"""
build.py — content/posts/*.md から静的サイト public/ を生成する。

出力:
    public/index.html
    public/posts/<slug>.html
    public/category/<slug>.html
    public/about.html
    public/feed.xml
    public/sitemap.xml
    public/assets/style.css

使い方:
    python3 scripts/build.py
    python3 scripts/build.py --serve      # ローカルで確認 (http://localhost:8000)
"""
from __future__ import annotations

import argparse
import html
import json
from urllib.parse import quote
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

import markdown
import yaml

if sys.platform == "win32":  # Windows のコンソールは既定 cp932。出力を UTF-8 に固定する
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import ogp
except Exception:  # Pillow 未導入などでもビルドは通す
    ogp = None

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
PUBLIC = ROOT / "public"
SITE_CFG = ROOT / "config" / "site.yaml"
JST = timezone(timedelta(hours=9))

MD = markdown.Markdown(extensions=["extra", "sane_lists", "toc", "tables"])

# base_url がサブディレクトリ配下（例: https://user.github.io/gadget-signal）のとき、
# サイト内リンクにそのプレフィックスを付ける。独自ドメイン（ルート直下）なら空文字になる。
BASE_PATH = ""


def u(path: str) -> str:
    """サイト内リンクを base_path 付きの絶対パスにする。"""
    if path in ("/", ""):
        return f"{BASE_PATH}/" if BASE_PATH else "/"
    return f"{BASE_PATH}/{path.lstrip('/')}"


# ────────────────────────────── 読み込み ──────────────────────────────
def load_site() -> dict:
    return yaml.safe_load(SITE_CFG.read_text(encoding="utf-8"))


def parse_post(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        print(f"  ! front matter がありません: {path.name}")
        return None
    meta = yaml.safe_load(m.group(1)) or {}
    body_md = m.group(2).strip()
    if meta.get("draft"):
        print(f"  - draft をスキップ: {path.name}")
        return None

    MD.reset()
    meta["body_html"] = MD.convert(body_md)
    meta["slug"] = meta.get("slug") or path.stem
    meta["date"] = str(meta.get("date", datetime.now(JST).strftime("%Y-%m-%d")))
    meta["reading_min"] = max(1, round(len(body_md) / 500))
    meta["path"] = f"posts/{meta['slug']}.html"
    meta.setdefault("tags", [])
    meta["keyword"] = meta.get("keyword") or (meta["tags"][0] if meta.get("tags") else "")
    meta.setdefault("sources", [])
    meta.setdefault("excerpt", re.sub(r"<[^>]+>", "", meta["body_html"])[:110].strip() + "…")
    return meta


# ────────────────────────────── テンプレート ──────────────────────────────
def affiliate_url(s: dict, url: str, merchant: str) -> tuple[str, bool]:
    """商品URLをアフィリエイトリンクに変換する。

    もしもアフィリエイトは提携先ごとにリンク形式が違うため、site.yaml に
    テンプレート（{url} が商品URLの位置）を持たせて差し替える方式にしている。
    無効・テンプレート未設定・対象外の提携先なら素のURLをそのまま返す。
    戻り値: (URL, アフィリエイトリンクか)
    """
    aff = s.get("affiliate") or {}
    if not aff.get("enabled"):
        return url, False
    tmpl = str(aff.get(f"moshimo_{merchant}") or "").strip()
    if not tmpl or "{url}" not in tmpl:
        return url, False
    return tmpl.replace("{url}", quote(url, safe="")), True


def alternatives_section(s: dict, p: dict) -> tuple[str, bool]:
    """「今すぐ買える代替品」セクション。

    クラファン案件は出荷が先で技適も未取得のことが多い。読者が実際に取れる行動を
    示すのが本来の目的で、アフィリエイトはその副産物として置く。
    リンクが無効でもセクション自体は出す（編集上の価値はリンクと無関係のため）。
    戻り値: (HTML, アフィリエイトリンクを含むか)
    """
    items = [x for x in (p.get("alternatives") or []) if x.get("name") and x.get("url")]
    if not items:
        return "", False
    has_aff = False
    rows = []
    for x in items:
        link, is_aff = affiliate_url(s, str(x["url"]), str(x.get("merchant") or "amazon"))
        has_aff = has_aff or is_aff
        why = f'<p class="alt-why">{html.escape(str(x["why"]))}</p>' if x.get("why") else ""
        rows.append(
            f'<li class="alt-item"><a href="{html.escape(link)}" rel="nofollow sponsored noopener" '
            f'target="_blank">{html.escape(str(x["name"]))}</a>{why}</li>')
    label = ('<span class="alt-ad">広告</span>' if has_aff else "")
    return (f'<section class="alts"><h2>今すぐ買える代替品{label}</h2>'
            f'<ul>{"".join(rows)}</ul></section>', has_aff)


def analytics(s: dict) -> str:
    """アクセス解析のタグを出す。設定が空なら何も出さない（外部スクリプトを読み込まない）。

    - cf_analytics_token: Cloudflare Web Analytics。Cookie を使わないので同意表示が不要
    - analytics_id: GA4。使う場合は G- で始まる測定ID
    両方入れれば両方出る。
    """
    tags = []
    token = str(s.get("cf_analytics_token") or "").strip()
    if token:
        tags.append('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                    f"data-cf-beacon='{{\"token\": \"{token}\"}}'></script>")
    gid = str(s.get("analytics_id") or "").strip()
    if gid:
        tags.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
                    "<script>window.dataLayer=window.dataLayer||[];"
                    "function gtag(){dataLayer.push(arguments);}"
                    "gtag('js',new Date());"
                    f"gtag('config','{gid}');</script>")
    return "".join(tags)


def head(site: dict, title: str, desc: str, url_path: str, extra: str = "",
         image: str = "ogp/default.png") -> str:
    s = site["site"]
    # image が外部URL（公式サイトの製品画像）ならそのまま使う。
    # 自社生成のアイキャッチだけがサイト相対パスで渡ってくる。
    is_ext_img = image.startswith(("http://", "https://"))
    img_url = image if is_ext_img else f"{s['base_url'].rstrip('/')}/{image.lstrip('/')}"
    # 寸法は自社生成画像（1200x630 固定）のときだけ書く。
    # 外部画像は実寸が分からず、誤った値を書くとカードの描画が崩れる。
    dims = ('<meta property="og:image:width" content="1200">' '<meta property="og:image:height" content="630">')
    img_dims = "" if is_ext_img else dims
    _p = "" if url_path in ("index.html", "/") else url_path.lstrip("/")
    full_url = f"{s['base_url'].rstrip('/')}/{_p}"
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b0d10">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{html.escape(full_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(s['title'])}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{html.escape(full_url)}">
<meta property="og:locale" content="{s.get('locale', 'ja_JP')}">
<meta property="og:image" content="{html.escape(img_url)}">{img_dims}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{html.escape(img_url)}">
<link rel="icon" type="image/svg+xml" href="{u('assets/favicon.svg')}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(s['title'])}" href="{u('feed.xml')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{u('assets/style.css')}">
{analytics(s)}
{extra}
</head>
<body>"""


def header(site: dict) -> str:
    s = site["site"]
    cats = "".join(
        f'<a href="{u("category/" + c["slug"] + ".html")}" class="nav-item cat-{k}">'
        f'<span class="nav-code">{c.get("code", "---")}</span>'
        f'<span class="nav-label">{html.escape(c["label"])}</span></a>'
        for k, c in site["categories"].items()
    )
    return f"""
<header class="site-head">
  <div class="wrap head-inner">
    <a class="brand" href="{u("/")}">
      <span class="brand-name">{html.escape(s['title'])}</span><span class="caret" aria-hidden="true"></span>
    </a>
    <nav class="nav">{cats}<a href="{u("about.html")}" class="nav-item nav-about"><span class="nav-code">INF</span><span class="nav-label">運営</span></a></nav>
  </div>
</header>"""


def footer(site: dict) -> str:
    s = site["site"]
    year = datetime.now(JST).year
    span = f"{s['copyright_from']}" if year == s["copyright_from"] else f"{s['copyright_from']}–{year}"
    return f"""
<footer class="site-foot">
  <div class="wrap">
    <div class="foot-board">
      <span class="foot-code">SYS</span>
      <span class="foot-status">ONLINE</span>
      <span class="foot-tag">{html.escape(s['tagline'])}</span>
    </div>
    <div class="foot-cols">
      <p class="foot-meta">
        <a href="{u("feed.xml")}">RSS</a><a href="{u("about.html")}">運営・免責</a><a href="mailto:{s.get('contact_email','')}">お問い合わせ</a>
      </p>
      <p class="foot-copy">© {span} {html.escape(s['title'])} — {html.escape(s['author'])}</p>
    </div>
  </div>
</footer>
</body>
</html>"""


def card(site: dict, p: dict, featured: bool = False) -> str:
    key = p.get("category", "misc")
    cat = site["categories"].get(key, {"label": "その他", "slug": "misc", "code": "---"})
    cls = ("card card-featured" if featured else "card") + f" cat-{key}"
    blurb = p.get("kicker") or p["excerpt"]
    img, is_ext = card_image(p)
    return f"""
<article class="{cls}">
  <a class="card-thumb{' card-thumb-real' if is_ext else ''}" href="{u(p['path'])}" aria-hidden="true" tabindex="-1">
    <img src="{img}" alt="" loading="lazy" width="1200" height="675"
         onerror="this.onerror=null;this.src='{u("cards/" + p['slug'] + ".png")}'">
  </a>
  <p class="card-meta">
    <a class="card-code" href="{u("category/" + cat['slug'] + ".html")}">{cat.get('code','---')}</a>
    <span class="card-cat">{html.escape(cat['label'])}</span>
    <time datetime="{p['date']}">{p['date'].replace('-', '.')}</time>
    <span class="card-read">{p['reading_min']}MIN</span>
  </p>
  <h2 class="card-title"><a href="{u(p['path'])}">{html.escape(p['title'])}</a></h2>
  <p class="card-excerpt">{html.escape(blurb)}</p>
</article>"""


def board_row(site: dict, p: dict, i: int) -> str:
    key = p.get("category", "misc")
    cat = site["categories"].get(key, {"code": "---", "label": "その他"})
    return f"""<a class="board-row cat-{key}" href="{u(p['path'])}">
  <span class="b-no">{i:02d}</span>
  <span class="b-code">{cat.get('code','---')}</span>
  <span class="b-date">{p['date'].replace('-', '.')}</span>
  <span class="b-key">{html.escape(p.get('keyword') or '')}</span>
  <span class="b-title">{html.escape(p['title'])}</span>
  <span class="b-min">{p['reading_min']}MIN</span>
  <span class="b-arrow" aria-hidden="true">→</span>
</a>"""


def page_path(n: int) -> str:
    """ページ番号 → サイト内パス。1ページ目だけルートに置く。"""
    return "index.html" if n <= 1 else f"page/{n}.html"


def pager(current: int, total: int) -> str:
    """前へ／次へ と現在位置を出すページ送り。1ページしかないときは何も出さない。"""
    if total <= 1:
        return ""
    prev = (f'<a class="pager-link" href="{u(page_path(current - 1))}" rel="prev">← 新しい記事</a>'
            if current > 1 else '<span class="pager-link is-off">← 新しい記事</span>')
    nxt = (f'<a class="pager-link" href="{u(page_path(current + 1))}" rel="next">古い記事 →</a>'
           if current < total else '<span class="pager-link is-off">古い記事 →</span>')
    nums = "".join(
        f'<span class="pager-num is-here">{n}</span>' if n == current
        else f'<a class="pager-num" href="{u(page_path(n))}">{n}</a>'
        for n in range(1, total + 1))
    return f'<nav class="pager" aria-label="ページ送り">{prev}<span class="pager-nums">{nums}</span>{nxt}</nav>'


def render_index(site: dict, posts: list[dict], page: int = 1, total_pages: int = 1) -> str:
    s = site["site"]
    if not posts:
        body = '<p class="empty">まだ記事がありません。</p>'
    elif page <= 1:
        # 1ページ目だけ、案内板と大きい先頭記事を出す。
        lead, rest = posts[0], posts[1:]
        rows = "".join(board_row(site, p, i + 1) for i, p in enumerate(posts[:7]))
        body = f"""
<section class="board">
  <div class="board-head">
    <span>NO</span><span>CAT</span><span>DATE</span><span>KEY</span><span>ENTRY</span><span>LEN</span><span></span>
  </div>
  {rows}
</section>
<section class="lead">
  {card(site, lead, featured=True)}
</section>
<section class="grid">
  {''.join(card(site, p) for p in rest)}
</section>
{pager(page, total_pages)}"""
    else:
        # 2ページ目以降はカードだけを並べる。
        body = f"""
<section class="grid">
  {''.join(card(site, p) for p in posts)}
</section>
{pager(page, total_pages)}"""
    title = f"{s['title']} — {s['tagline']}" if page <= 1 else f"{s['title']} — {page}ページ目"
    return (
        head(site, title, s["description"], page_path(page))
        + header(site)
        + f"""
<main class="wrap">
  <section class="hero{'' if page <= 1 else ' hero-sm'}">
    <p class="eyebrow">{'DEPARTURES / 海外発' if page <= 1 else f'ARCHIVE / {page} of {total_pages}'}</p>
    <h1 class="hero-title">{html.escape(s['tagline']) if page <= 1 else f'過去の記事 — {page}ページ目'}</h1>
    <p class="hero-sub">{html.escape(s['description']) if page <= 1 else ''}</p>
  </section>
  {body}
</main>"""
        + footer(site)
    )


def render_category(site: dict, key: str, cat: dict, posts: list[dict]) -> str:
    s = site["site"]
    items = [p for p in posts if p.get("category") == key]
    body = "".join(card(site, p) for p in items) or '<p class="empty">このカテゴリの記事はまだありません。</p>'
    return (
        head(site, f"{cat['label']} — {s['title']}", cat["description"], f"category/{cat['slug']}.html")
        + header(site)
        + f"""
<main class="wrap">
  <section class="hero hero-sm cat-{key}">
    <p class="eyebrow">{cat.get('code','---')} / CATEGORY</p>
    <h1 class="hero-title">{html.escape(cat['label'])}</h1>
    <p class="hero-sub">{html.escape(cat['description'])}</p>
  </section>
  <section class="grid">{body}</section>
</main>"""
        + footer(site)
    )


def card_image(p: dict) -> tuple[str, bool]:
    """カードに出す画像を決める。

    優先順位:
      1. front matter の thumbnail（自社撮影・許諾済み素材を置く用）
      2. YouTube のサムネイル（動画を埋め込んでいる場合）
         YouTube はサムネイルを表示用に配信しており、oEmbed でも
         thumbnail_url として公開されている。転載ではなく正規の利用。
      3. 自動生成のアイキャッチ
    戻り値: (URL, 外部URLか)
    """
    if p.get("thumbnail"):
        th = str(p["thumbnail"])
        return (th, th.startswith("http"))
    for e in (p.get("embeds") or []):
        if (e.get("type") or "").lower() == "youtube" and e.get("id"):
            return (f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg", True)
    return (u("cards/" + p["slug"] + ".png"), False)


def render_embeds(p: dict) -> tuple[str, bool]:
    """front matter の embeds を、プラットフォーム公式の埋め込みHTMLに変換する。

    画像を自社サーバーにコピーせず、権利者が公開している投稿をそのまま表示する方式。
    転載にあたらないため、メーカー公式アカウントの製品写真を合法的に見せられる。
    戻り値: (HTML, X埋め込みスクリプトが必要か)
    """
    items = p.get("embeds") or []
    if not items:
        return "", False
    blocks, needs_x = [], False
    for e in items:
        kind = (e.get("type") or "").lower()
        url = e.get("url", "")
        caption = html.escape(e.get("caption", ""))
        if kind in ("x", "twitter"):
            needs_x = True
            blocks.append(
                f'<figure class="embed embed-x">'
                f'<blockquote class="twitter-tweet" data-lang="ja" data-dnt="true">'
                f'<a href="{html.escape(url)}"></a></blockquote>'
                f'{f"<figcaption>{caption}</figcaption>" if caption else ""}</figure>')
        elif kind == "youtube":
            vid = html.escape(e.get("id", ""))
            blocks.append(
                f'<figure class="embed embed-video">'
                f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}" '
                f'title="{caption or "YouTube"}" loading="lazy" allowfullscreen '
                f'referrerpolicy="strict-origin-when-cross-origin"></iframe>'
                f'{f"<figcaption>{caption}</figcaption>" if caption else ""}</figure>')
        elif kind == "link":
            # 権利上そのまま出せない画像は、元記事へのリンクカードで代替する
            title = html.escape(e.get("title", url))
            pub = html.escape(e.get("publisher", ""))
            blocks.append(
                f'<figure class="embed embed-link">'
                f'<a href="{html.escape(url)}" rel="nofollow noopener" target="_blank">'
                f'<span class="embed-link-title">{title}</span>'
                f'<span class="embed-link-pub">{pub} — 製品画像は元記事でご覧いただけます</span>'
                f'</a></figure>')
    return "\n".join(blocks), needs_x


def render_post(site: dict, p: dict, others: list[dict]) -> str:
    s = site["site"]
    cat = site["categories"].get(p.get("category"), {"label": "その他", "slug": "misc"})
    embeds_html, needs_x = render_embeds(p)
    # 最初の1本は本文の前に出す。下端に置くと誰も見ないため。
    lead_embed, rest_embed = "", ""
    if embeds_html:
        parts = embeds_html.split("</figure>")
        blocks = [x + "</figure>" for x in parts if x.strip()]
        lead_embed = f'<section class="embeds embeds-lead">{blocks[0]}</section>' if blocks else ""
        if len(blocks) > 1:
            rest_embed = ('<section class="embeds"><h2>関連する投稿・動画</h2>'
                          + "".join(blocks[1:]) + '</section>')
    embeds_html = rest_embed

    # 動画がある記事は生成画像を出さない。実写のほうが情報量が多い。
    # 動画が無く thumbnail がある場合は、そちらを実写として出す。
    # 外部URLのときは自社サーバーに複製せず、権利者のサーバーを直接参照する。
    fallback = u("cards/" + p["slug"] + ".png")
    if lead_embed:
        hero_block = lead_embed
    elif p.get("thumbnail"):
        th = str(p["thumbnail"])
        credit = p.get("thumbnail_credit")
        cap = (f'<figcaption class="hero-credit">出典: {html.escape(str(credit))}</figcaption>'
               if credit else "")
        onerr = 'this.onerror=null;this.src=' + repr(fallback)
        hero_block = (f'<figure class="article-hero article-hero-real">'
                      f'<img src="{html.escape(th)}" alt="{html.escape(p["title"])}" '
                      f'onerror="{onerr}">{cap}</figure>')
    else:
        hero_block = (f'<figure class="article-hero">'
                      f'<img src="{fallback}" '
                      f'alt="{html.escape(p["title"])}" width="1200" height="675"></figure>')
    sources = ""
    if p["sources"]:
        rows = "".join(
            f'<li><a href="{html.escape(src["url"])}" rel="nofollow noopener" target="_blank">'
            f'{html.escape(src.get("title", src["url"]))}</a>'
            f'<span class="src-pub">{html.escape(src.get("publisher", ""))}</span></li>'
            for src in p["sources"]
        )
        sources = f"""
<section class="sources">
  <h2>参照した一次ソース</h2>
  <ol>{rows}</ol>
  <p class="sources-note">本記事は上記の海外報道をもとに編集部が構成したものです。日本国内の発売・価格は各社の公式発表をご確認ください。</p>
</section>"""

    # 関連記事はタグの一致数で選ぶ。同数ならカテゴリ一致、それも同じなら新しい順。
    # 機械的に先頭3本を出すより回遊率が上がり、内部リンクの意味も強くなる。
    my_tags = {str(t).lower() for t in (p.get("tags") or [])}
    def relevance(o: dict) -> tuple:
        shared = len(my_tags & {str(t).lower() for t in (o.get("tags") or [])})
        same_cat = 1 if o.get("category") == p.get("category") else 0
        return (-shared, -same_cat, o["date"] < p["date"], o["date"])
    related = sorted((o for o in others if o["slug"] != p["slug"]), key=relevance)[:3]
    rel_html = ""
    if related:
        rel_html = f"""
<section class="related">
  <h2>ほかの記事</h2>
  <div class="grid">{''.join(card(site, r) for r in related)}</div>
</section>"""

    base = s["base_url"].rstrip("/")
    page_url = f"{base}/{p['path']}"
    # OGP画像は必ず存在する（生成される）ので、これを構造化データの image にも使う。
    # thumbnail がある記事は実写のほうが望ましいので、そちらを優先する。
    ld_image = str(p["thumbnail"]) if p.get("thumbnail") else f"{base}/ogp/{p['slug']}.png"
    article_ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": p["title"][:110],
        "description": p["excerpt"],
        "image": [ld_image],
        "datePublished": f"{p['date']}T09:00:00+09:00",
        "dateModified": f"{p.get('modified') or p['date']}T09:00:00+09:00",
        "url": page_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": page_url},
        "inLanguage": "ja",
        "articleSection": cat["label"],
        "author": {"@type": "Organization", "name": s["author"], "url": base + "/about.html"},
        "publisher": {"@type": "Organization", "name": s["title"],
                      "logo": {"@type": "ImageObject", "url": f"{base}/ogp/default.png"}},
    }
    if p.get("tags"):
        article_ld["keywords"] = ", ".join(str(t) for t in p["tags"])
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": s["title"], "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": cat["label"],
             "item": f"{base}/category/{cat['slug']}.html"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": page_url},
        ],
    }
    # front matter の faq を FAQPage として出す。検索結果に Q&A が展開されることがある。
    # ガジェット記事は「技適は?」「日本で使える?」が定番クエリなので効きやすい。
    faq = [x for x in (p.get("faq") or []) if x.get("q") and x.get("a")]
    faq_ld = None
    faq_html = ""
    if faq:
        faq_ld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": str(x["q"]),
                            "acceptedAnswer": {"@type": "Answer", "text": str(x["a"])}}
                           for x in faq],
        }
        rows = "".join(
            f'<div class="faq-item"><h3>{html.escape(str(x["q"]))}</h3>'
            f'<p>{html.escape(str(x["a"]))}</p></div>' for x in faq)
        faq_html = f'<section class="faq"><h2>よくある質問</h2>{rows}</section>'

    alts_html, has_aff = alternatives_section(s, p)
    # ステマ規制。アフィリエイトリンクがある記事は、本文の先頭で広告を含む旨を示す。
    # 「サイトのどこかに書いてある」では足りないため、記事ごとに出す。
    disclosure = ""
    if has_aff:
        text = str((s.get("affiliate") or {}).get("disclosure") or "この記事にはアフィリエイト広告を含みます")
        disclosure = f'<p class="ad-notice">{html.escape(text)}</p>'

    ld = "".join(
        f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False, separators=(",", ":"))}</script>'
        for d in (article_ld, breadcrumb_ld, faq_ld) if d)

    return (
        head(site, f"{p.get('seo_title') or p['title']} — {s['title']}", p["excerpt"], p["path"],
             ld + ('\n<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>'
                   if needs_x else ""),
             # thumbnail は外部URLのまま、生成アイキャッチはサイト相対で渡す
             image=(str(p["thumbnail"]) if p.get("thumbnail")
                    else f"ogp/{p['slug']}.png"))
        + header(site)
        + f"""
<main class="wrap article-wrap">
  <article class="article cat-{p.get("category", "misc")}">
    <p class="eyebrow"><a href="{u("category/" + cat['slug'] + ".html")}"><span class="eyebrow-code">{cat.get('code','---')}</span>{html.escape(cat['label'])}</a></p>
    <h1 class="article-title">{html.escape(p['title'])}</h1>
    {f'<p class="article-lede">{html.escape(p["kicker"])}</p>' if p.get('kicker') else ''}
    {disclosure}
    <p class="article-meta"><time datetime="{p['date']}">{p['date'].replace('-', '.')}</time><span class="dot"></span>{p['reading_min']} MIN READ</p>
    {hero_block}
    <div class="prose">{p['body_html']}</div>
    {embeds_html}
    {alts_html}
  {faq_html}
  {sources}
  </article>
  {rel_html}
</main>"""
        + footer(site)
    )


def render_about(site: dict) -> str:
    s = site["site"]
    body = f"""
<main class="wrap article-wrap">
  <article class="article">
    <p class="eyebrow">ABOUT</p>
    <h1 class="article-title">{html.escape(s['title'])}について</h1>
    <div class="prose">
      <p>{html.escape(s['description'])}</p>

      <h2>編集方針</h2>
      <ul>
        <li>海外メディア・メーカー公式発表を毎日巡回し、複数媒体が報じた話題を優先して扱います。</li>
        <li>スペックや価格などの数値は、参照元に記載のある範囲でのみ記載します。推測値は「未発表」と明示します。</li>
        <li>リーク情報は、その旨と確度を本文中に明記します。</li>
        <li>すべての記事に参照した一次ソースへのリンクを掲載します。</li>
      </ul>

      <h2>免責</h2>
      <p>本サイトの記事は海外の公開情報をもとに編集したものです。掲載時点の情報であり、価格・仕様・発売時期は変更される場合があります。
      日本国内での販売可否および技適等の認証状況は保証しません。購入・輸入の判断は読者ご自身の責任でお願いします。</p>

      <h2>権利について</h2>
      <p>各製品名・企業名は各社の商標です。画像は原則として自社作成のものか、権利者から許諾を得たもののみを使用します。
      引用は出典を明示のうえ、必要最小限の範囲で行います。訂正・削除のご依頼は下記までご連絡ください。</p>

      <h2>お問い合わせ</h2>
      <p>記事内容の訂正・削除のご依頼、その他のお問い合わせは下記までご連絡ください。</p>
      <ul>
        <li>一般のお問い合わせ： <a href="mailto:{s.get('contact_email','')}">{html.escape(s.get('contact_email',''))}</a></li>
        <li>製品情報・取材のご連絡： <a href="mailto:{s.get('press_email','')}">{html.escape(s.get('press_email',''))}</a></li>
      </ul>
      <p>運営： {html.escape(s['author'])}</p>
    </div>
  </article>
</main>"""
    return head(site, f"運営について — {s['title']}", "編集方針・免責・お問い合わせ", "about.html") + header(site) + body + footer(site)


def _json_str(v: str) -> str:
    import json
    return json.dumps(v, ensure_ascii=False)


def render_feed(site: dict, posts: list[dict]) -> str:
    s = site["site"]
    base = s["base_url"].rstrip("/")
    items = []
    for p in posts[:30]:
        dt = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=JST)
        items.append(f"""  <item>
    <title>{html.escape(p['title'])}</title>
    <link>{base}/{p['path']}</link>
    <guid isPermaLink="true">{base}/{p['path']}</guid>
    <pubDate>{format_datetime(dt)}</pubDate>
    <description>{html.escape(p['excerpt'])}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>{html.escape(s['title'])}</title>
  <link>{base}/</link>
  <description>{html.escape(s['description'])}</description>
  <language>ja</language>
{chr(10).join(items)}
</channel></rss>"""


def render_sitemap(site: dict, posts: list[dict]) -> str:
    base = site["site"]["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/about.html"]
    per_page = int(site["site"].get("posts_per_page") or 20)
    total_pages = max(1, -(-len(posts) // per_page))
    urls += [f"{base}/{page_path(n)}" for n in range(2, total_pages + 1)]
    urls += [f"{base}/category/{c['slug']}.html" for c in site["categories"].values()]
    urls += [f"{base}/{p['path']}" for p in posts]
    # lastmod があるとクローラーが再訪問すべきURLを判断できる。
    # 記事は自身の日付、一覧系は最新記事の日付を使う。
    latest = max((p["date"] for p in posts), default="")
    by_url = {f"{base}/{p['path']}": p["date"] for p in posts}
    def entry(loc: str) -> str:
        d = by_url.get(loc, latest)
        return f"<url><loc>{loc}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>"
    body = "".join(entry(u) for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


# ────────────────────────────── CSS ──────────────────────────────
CSS = """
/* ============================================================
   Gadget Terminal — 出発案内板を設計言語にしたダークテーマ
   ============================================================ */
:root{
  --bg:#0b0d10; --surface:#12161b; --raised:#171c22;
  --ink:#e9edf1; --ink-2:#96a0ac; --ink-3:#5f6975;
  --rule:#1e242c; --rule-2:#2a323c;
  --accent:#ff6b3d;
  --cat:var(--accent);
  --max:1280px; --measure:36rem;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --disp:"Space Grotesk","Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;
  --sans:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;
}
.cat-smartphone{--cat:#ff6b3d}
.cat-pc{--cat:#4fb3c4}
.cat-weird{--cat:#d9b45f}

/* 生成する画像がダーク固定のため、UIもダークに統一する。
   ライトモードにすると画像だけ黒い板になって不整合が出る。 */

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.72;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit;text-decoration:none}
img{max-width:100%}
.wrap{max-width:var(--max);margin:0 auto;padding:0 24px}

/* ── ヘッダー ───────────────────────────────── */
.site-head{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--rule);
  background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(14px) saturate(1.4)}
.head-inner{display:flex;align-items:center;justify-content:space-between;gap:20px;height:48px}
.brand{display:inline-flex;align-items:center;font-family:var(--mono);font-weight:600;
  font-size:14px;letter-spacing:.16em;text-transform:uppercase;white-space:nowrap}
.caret{width:9px;height:16px;background:var(--accent);margin-left:7px;display:inline-block;
  animation:blink 1.25s steps(1) infinite}
@keyframes blink{0%,55%{opacity:1}56%,100%{opacity:0}}
.nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
.nav::-webkit-scrollbar{display:none}
.nav-item{display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border-radius:2px;
  white-space:nowrap;transition:background .18s}
.nav-item:hover{background:var(--raised)}
.nav-code{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.1em;
  color:var(--cat);border:1px solid var(--cat);padding:2px 5px;border-radius:2px;opacity:.9}
.nav-label{font-size:12px;color:var(--ink-2)}
.nav-item:hover .nav-label{color:var(--ink)}
.nav-about{--cat:var(--ink-3)}

/* ── ヒーロー ───────────────────────────────── */
.hero{padding:30px 0 20px}
.hero-sm{padding:32px 0 22px;border-bottom:1px solid var(--rule);margin-bottom:0}
.eyebrow{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--cat);margin:0 0 10px;font-weight:600}
.hero-title{font-family:var(--disp);font-size:clamp(22px,2.9vw,34px);line-height:1.4;
  margin:0 0 10px;font-weight:700;letter-spacing:-.015em;max-width:30em}
.hero-sub{margin:0;color:var(--ink-2);font-size:13px;max-width:44em;line-height:1.75}

/* ── 出発案内板 ─────────────────────────────── */
.board{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin-bottom:40px}
.board-head,.board-row{display:grid;
  grid-template-columns:30px 44px 84px minmax(140px,0.9fr) minmax(0,2.1fr) 44px 20px;
  align-items:center;gap:14px;font-family:var(--mono);font-size:11.5px}
.board-head{padding:7px 4px;color:var(--ink-3);font-size:9.5px;letter-spacing:.16em;
  border-bottom:1px solid var(--rule)}
.board-row{padding:8px 4px;border-bottom:1px solid var(--rule);position:relative;
  transition:background .16s,padding-left .16s}
.board-row:last-child{border-bottom:0}
.board-row::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--cat);transform:scaleY(0);transition:transform .2s}
.board-row:hover{background:var(--raised);padding-left:10px}
.board-row:hover::before{transform:scaleY(1)}
.b-no{color:var(--ink-3)}
.b-code{color:var(--cat);font-weight:600;letter-spacing:.08em}
.b-date{color:var(--ink-3);font-variant-numeric:tabular-nums}
.b-key{font-family:var(--sans);font-size:13px;color:var(--ink);font-weight:600;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.b-title{font-family:var(--sans);font-size:12.5px;color:#bcc6d1;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.b-min{color:var(--ink-3);text-align:right}
.b-arrow{color:var(--ink-3);text-align:right;transition:transform .2s,color .2s}
.board-row:hover .b-arrow{color:var(--cat);transform:translateX(3px)}
.board-row:hover .b-title{color:var(--ink)}

/* ── ページ送り ─────────────────────────────── */
.pager{display:flex;align-items:center;justify-content:space-between;gap:16px;
  margin:36px 0 8px;padding-top:20px;border-top:1px solid var(--rule);
  font-family:var(--mono);font-size:12px;letter-spacing:.04em}
.pager-link{color:var(--ink-2);text-decoration:none;padding:6px 10px;border:1px solid var(--rule-2);border-radius:3px}
.pager-link:hover{color:var(--ink);border-color:var(--accent)}
.pager-link.is-off{opacity:.32;border-style:dashed}
.pager-nums{display:flex;gap:4px;flex-wrap:wrap;justify-content:center}
.pager-num{color:var(--ink-3);text-decoration:none;min-width:26px;text-align:center;padding:6px 4px;border-radius:3px}
.pager-num:hover{color:var(--ink)}
.pager-num.is-here{color:var(--bg);background:var(--accent);font-weight:600}
@media (max-width:520px){
  .pager{flex-direction:column;gap:12px}
}

/* ── カード ─────────────────────────────────── */
.lead{margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  gap:1px;background:var(--rule);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.card{background:var(--bg);padding:18px 18px 22px}
.card-featured{background:transparent;padding:0 0 22px;border-bottom:1px solid var(--rule);margin-bottom:26px;
  display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:24px;align-items:start;
  grid-template-rows:auto auto auto}
.card-thumb{display:block;margin:0 0 12px;overflow:hidden;background:var(--surface);
  border:1px solid var(--rule);border-radius:3px}
.card-thumb img{display:block;width:100%;height:124px;object-fit:cover;object-position:left center;
  background:var(--surface);
  transition:transform .55s cubic-bezier(.2,.6,.2,1),opacity .3s}
.card:hover .card-thumb img,.card-featured:hover .card-thumb img{transform:scale(1.03)}
.card-featured .card-thumb{margin:0;grid-column:1;grid-row:1/span 3;align-self:start}
.card-featured .card-thumb img{height:186px}
.card-featured .card-meta{grid-column:2;grid-row:1;margin-top:2px}
.card-featured .card-title{grid-column:2;grid-row:2}
.card-featured .card-excerpt{grid-column:2;grid-row:3}
.card-meta{display:flex;align-items:center;gap:9px;margin:0 0 8px;
  font-family:var(--mono);font-size:10px;letter-spacing:.06em;color:var(--ink-3)}
.card-code{color:var(--cat);font-weight:600;border:1px solid var(--cat);padding:1px 5px;
  border-radius:2px;opacity:.92}
.card-cat{color:var(--ink-2);font-family:var(--sans);font-size:11px;letter-spacing:0;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.card-read{margin-left:auto}
.card-title{font-family:var(--disp);font-weight:700;font-size:15.5px;line-height:1.55;
  margin:0 0 8px;letter-spacing:-.005em}
.card-featured .card-title{font-size:clamp(18px,1.7vw,23px);line-height:1.46;margin-bottom:9px}
.card-title a{background-image:linear-gradient(var(--cat),var(--cat));background-size:0 1.5px;
  background-position:0 100%;background-repeat:no-repeat;transition:background-size .3s}
.card-title a:hover{background-size:100% 1.5px}
.card-excerpt{margin:0;color:var(--ink-2);font-size:12.5px;line-height:1.78;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card-featured .card-excerpt{font-size:13px;max-width:40em;line-height:1.8;-webkit-line-clamp:3}

/* ── 記事 ───────────────────────────────────── */
.article-wrap{padding-top:38px}
.article{max-width:var(--measure);margin:0 auto}
.eyebrow-code{font-family:var(--mono);border:1px solid var(--cat);padding:2px 6px;
  border-radius:2px;margin-right:10px}
.article-title{font-family:var(--disp);font-size:clamp(23px,2.9vw,33px);line-height:1.42;
  font-weight:700;margin:0 0 14px;letter-spacing:-.012em}
.article-lede{font-size:15px;color:var(--ink-2);line-height:1.82;margin:0 0 16px}
.article-meta{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--ink-3);
  display:flex;align-items:center;gap:10px;padding-bottom:20px;border-bottom:1px solid var(--rule);margin:0}
.dot{width:3px;height:3px;border-radius:50%;background:var(--ink-3);display:inline-block}
.article-hero{margin:0 0 30px;border-bottom:1px solid var(--rule)}
.hero-credit{padding:8px 0 10px;color:var(--ink-3);font-family:var(--mono);font-size:11px;letter-spacing:.03em}
.article-hero img{display:block;width:100%;height:auto;max-height:220px;object-fit:cover;object-position:left center}
.prose{font-size:15.5px;line-height:1.9;color:var(--ink)}
.prose h2{font-family:var(--disp);font-size:19px;line-height:1.5;margin:38px 0 14px;font-weight:700;
  letter-spacing:-.01em;padding-top:8px;position:relative}
.prose h2::before{content:"";position:absolute;top:-1px;left:0;width:38px;height:2px;background:var(--cat)}
.prose h3{font-size:15.5px;margin:26px 0 8px;font-weight:700}
.prose p{margin:0 0 18px}
.prose ul,.prose ol{margin:0 0 18px;padding-left:1.3em}
.prose li{margin-bottom:6px}
.prose li::marker{color:var(--cat)}
.prose a{color:var(--cat);border-bottom:1px solid color-mix(in srgb,var(--cat) 40%,transparent)}
.prose a:hover{border-bottom-color:var(--cat)}
.prose strong{font-weight:700;color:var(--ink)}
.prose blockquote{margin:30px 0;padding:2px 0 2px 22px;border-left:2px solid var(--cat);
  color:var(--ink-2);font-size:15.5px}
.prose table{width:100%;border-collapse:collapse;margin:22px 0;font-size:13.5px;
  font-variant-numeric:tabular-nums}
.prose th,.prose td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--rule);vertical-align:top}
.prose thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;border-bottom:1px solid var(--rule-2)}
.prose td:first-child{color:var(--ink-2);width:34%}
.prose tbody tr:hover{background:var(--raised)}
.prose code{font-family:var(--mono);font-size:.86em;background:var(--raised);padding:2px 7px;
  border-radius:3px;color:var(--cat)}
.prose hr{border:0;border-top:1px solid var(--rule);margin:44px 0}

/* ── 埋め込み・出典 ─────────────────────────── */
.embeds,.sources{margin-top:38px;padding-top:22px;border-top:1px solid var(--rule)}
.embeds-lead{margin:0 0 30px;padding-top:0;border-top:0}
.embeds-lead .embed{margin-bottom:0}
.embeds h2,.sources h2{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 20px;font-weight:600}
.embed{margin:0 0 30px}
.embed figcaption{font-size:13px;color:var(--ink-3);margin-top:11px;line-height:1.75}
.embed-video{background:var(--surface);border:1px solid var(--rule);border-radius:3px;overflow:hidden}
.embed-video iframe{width:100%;aspect-ratio:16/9;border:0;display:block;background:var(--surface)}
.embed-video figcaption{padding:0 2px}
.embed-link a{display:block;padding:22px 24px;border:1px solid var(--rule);border-radius:3px;
  background:var(--surface);transition:border-color .2s,background .2s}
.embed-link a:hover{border-color:var(--cat);background:var(--raised)}
.embed-link-title{display:block;font-family:var(--disp);font-weight:600;font-size:16px;
  line-height:1.6;margin-bottom:8px}
.embed-link-pub{display:block;font-family:var(--mono);font-size:11.5px;color:var(--ink-3);letter-spacing:.04em}
.sources ol{margin:0 0 20px;padding-left:1.3em;font-size:14px;line-height:1.8}
.sources li{margin-bottom:11px}
.sources li::marker{font-family:var(--mono);color:var(--ink-3)}
.sources a{border-bottom:1px solid var(--rule-2)}
.sources a:hover{border-bottom-color:var(--cat)}
.src-pub{font-family:var(--mono);color:var(--ink-3);font-size:11.5px;margin-left:9px}
.sources-note{font-size:12.5px;color:var(--ink-3);line-height:1.85;margin:0}

.ad-notice{max-width:var(--measure);margin:0 0 18px;padding:7px 11px;border:1px solid var(--rule-2);
  border-radius:3px;color:var(--ink-3);font-family:var(--mono);font-size:11px;letter-spacing:.03em}
.alts{max-width:var(--measure);margin:44px 0 0;padding-top:24px;border-top:1px solid var(--rule)}
.alts h2{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 16px;display:flex;align-items:center;gap:8px}
.alt-ad{background:var(--rule-2);color:var(--ink-2);padding:2px 6px;border-radius:2px;letter-spacing:.1em}
.alts ul{list-style:none;padding:0;margin:0}
.alt-item{margin:0 0 16px}
.alt-item>a{font-size:15px;line-height:1.6}
.alt-why{margin:4px 0 0;color:var(--ink-2);font-size:13.5px;line-height:1.8}
.faq{max-width:var(--measure);margin:44px 0 0;padding-top:24px;border-top:1px solid var(--rule)}
.faq h2{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-3);margin:0 0 18px}
.faq-item{margin:0 0 18px}
.faq-item h3{font-size:15px;margin:0 0 6px;line-height:1.6}
.faq-item p{margin:0;color:var(--ink-2);font-size:14px;line-height:1.85}
.related{max-width:var(--max);margin:56px auto 0}
.related h2{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 22px;font-weight:600}
.empty{color:var(--ink-3);padding:60px 0}

/* ── フッター ───────────────────────────────── */
.site-foot{margin-top:64px;border-top:1px solid var(--rule);padding:26px 0 44px}
.foot-board{display:flex;align-items:center;gap:14px;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.1em;padding-bottom:26px;border-bottom:1px solid var(--rule);margin-bottom:26px}
.foot-code{color:var(--ink-3);border:1px solid var(--rule-2);padding:2px 6px;border-radius:2px}
.foot-status{color:var(--accent);font-weight:600}
.foot-status::before{content:"● "}
.foot-tag{font-family:var(--sans);letter-spacing:0;color:var(--ink-2);font-size:13px;margin-left:auto;
  text-align:right}
.foot-cols{display:flex;justify-content:space-between;align-items:baseline;gap:24px;flex-wrap:wrap}
.foot-meta{margin:0;display:flex;gap:22px;font-size:13px}
.foot-meta a{color:var(--ink-2);border-bottom:1px solid transparent;padding-bottom:2px}
.foot-meta a:hover{color:var(--ink);border-bottom-color:var(--accent)}
.foot-copy{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);margin:0;letter-spacing:.06em}

/* ── レスポンシブ ───────────────────────────── */
@media (max-width:1100px){
  .board-head,.board-row{grid-template-columns:30px 44px 84px minmax(0,1fr) 44px 20px}
  .b-title,.board-head span:nth-child(5){display:none}
}
@media (max-width:900px){
  .nav-label{display:none}
  .board-head,.board-row{grid-template-columns:30px 44px minmax(0,1fr) 20px}
  .b-date,.b-min,.board-head span:nth-child(3),.board-head span:nth-child(6){display:none}
}
@media (max-width:820px){
  .card-featured{grid-template-columns:1fr;gap:14px}
  .card-featured .card-thumb{grid-row:auto}
}
@media (max-width:640px){
  .wrap{padding:0 18px}
  .hero{padding:52px 0 34px}
  .board{margin-bottom:48px}
  .article-wrap{padding-top:38px}
  .grid{grid-template-columns:1fr}
  .card-featured .card-thumb img{height:170px}
  .card-thumb img{height:150px}
  .foot-tag{margin-left:0;text-align:left;width:100%}
  .foot-board{flex-wrap:wrap}
}
"""


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#fbfaf8"/>
  <circle cx="32" cy="32" r="7" fill="#b4472b"/>
  <circle cx="32" cy="32" r="15" fill="none" stroke="#b4472b" stroke-width="3" stroke-opacity=".55"/>
  <circle cx="32" cy="32" r="23" fill="none" stroke="#b4472b" stroke-width="3" stroke-opacity=".25"/>
</svg>
"""


# ────────────────────────────── メイン ──────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()

    site = load_site()

    global BASE_PATH
    from urllib.parse import urlparse
    BASE_PATH = urlparse(site["site"]["base_url"]).path.rstrip("/")
    print(f"■ base_path: {BASE_PATH or '(ルート直下)'}")

    posts = [p for p in (parse_post(f) for f in sorted(POSTS_DIR.glob("*.md"))) if p]
    # 日付 → priority（front matter で 1 以上を指定するとその日の先頭に来る）→ slug
    posts.sort(key=lambda p: (p["date"], p.get("priority", 0), p["slug"]), reverse=True)
    print(f"■ 記事 {len(posts)}本")
    long_titles = [p for p in posts if len(p.get("seo_title") or p["title"]) > 34]
    if long_titles:
        print(f"! 検索用タイトルが長い記事 {len(long_titles)}本 "
              f"(Google は全角32字前後で切る。front matter に seo_title を足すと直る)")
        for p_ in long_titles[:3]:
            print(f"    {len(p_.get('seo_title') or p_['title'])}字 {p_['slug']}")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "posts").mkdir(parents=True)
    (PUBLIC / "category").mkdir(parents=True)
    (PUBLIC / "assets").mkdir(parents=True)

    (PUBLIC / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (PUBLIC / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")

    # OGP画像（フォントが無い環境では静かにスキップ）
    if ogp is not None:
        made = 0
        for p in posts:
            cat = site["categories"].get(p.get("category"), {"label": "その他"})
            if ogp.render(p["title"], cat["label"], s_title := site["site"]["title"],
                          PUBLIC / "ogp" / f"{p['slug']}.png"):
                made += 1
        ogp.render(site["site"]["tagline"], site["site"]["title"].upper(), site["site"]["title"],
                   PUBLIC / "ogp" / "default.png")

        cards = 0
        for p in posts:
            key = p.get("category")
            cat = site["categories"].get(key, {"label": "その他"})
            word = p.get("keyword") or cat["label"]
            if ogp.render_card(word, cat["label"], key or "", site["site"]["title"],
                               p["slug"], PUBLIC / "cards" / f"{p['slug']}.png"):
                cards += 1
        print(f"■ OGP画像 {made}枚 / アイキャッチ {cards}枚" if made
              else "■ 画像生成: フォントが無いためスキップ")
    # ページ送り。site.yaml の posts_per_page 件ずつに切る（1ページ目は先頭記事を含む）。
    per_page = int(site["site"].get("posts_per_page") or 20)
    pages = [posts[i:i + per_page] for i in range(0, len(posts), per_page)] or [[]]
    total_pages = len(pages)
    for n, chunk in enumerate(pages, start=1):
        out = PUBLIC / page_path(n)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_index(site, chunk, n, total_pages), encoding="utf-8")
    if total_pages > 1:
        print(f"■ ページ送り {total_pages}ページ ({per_page}件/ページ)")
    (PUBLIC / "about.html").write_text(render_about(site), encoding="utf-8")
    for p in posts:
        (PUBLIC / p["path"]).write_text(render_post(site, p, posts), encoding="utf-8")
    for key, cat in site["categories"].items():
        (PUBLIC / "category" / f"{cat['slug']}.html").write_text(
            render_category(site, key, cat, posts), encoding="utf-8")
    (PUBLIC / "feed.xml").write_text(render_feed(site, posts), encoding="utf-8")
    (PUBLIC / "sitemap.xml").write_text(render_sitemap(site, posts), encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site['site']['base_url'].rstrip('/')}/sitemap.xml\n",
        encoding="utf-8")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")

    # IndexNow の所有者確認ファイル。ルートに <key>.txt を置き、中身はキーそのもの。
    # これが無いと通知が 403 で弾かれる。
    key_file = ROOT / ".indexnow-key"
    if key_file.exists():
        k = key_file.read_text(encoding="ascii").strip()
        if k:
            (PUBLIC / f"{k}.txt").write_text(k, encoding="ascii")
            print(f"■ IndexNow キーファイル: {k}.txt")

    # 独自ドメイン用の CNAME。base_url のホスト名から自動生成する。
    # GitHub Pages はこのファイルを見て独自ドメインを認識するため、
    # 成果物に必ず含める必要がある（無いと設定がリセットされる）。
    from urllib.parse import urlparse as _up
    host = _up(site["site"]["base_url"]).netloc
    if host and not host.endswith("github.io"):
        (PUBLIC / "CNAME").write_text(host + "\n", encoding="utf-8")
        print(f"■ CNAME: {host}")

    print(f"■ 出力 public/ ({len(list(PUBLIC.rglob('*.html')))} ページ)")

    if args.serve:
        import http.server, socketserver, os
        os.chdir(PUBLIC)
        with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
            print("http://localhost:8000 で確認できます (Ctrl+C で停止)")
            httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
