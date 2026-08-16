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
import re
import shutil
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

import markdown
import yaml

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
    meta.setdefault("sources", [])
    meta.setdefault("excerpt", re.sub(r"<[^>]+>", "", meta["body_html"])[:110].strip() + "…")
    return meta


# ────────────────────────────── テンプレート ──────────────────────────────
def head(site: dict, title: str, desc: str, url_path: str, extra: str = "",
         image: str = "ogp/default.png") -> str:
    s = site["site"]
    img_url = f"{s['base_url'].rstrip('/')}/{image.lstrip('/')}"
    _p = "" if url_path in ("index.html", "/") else url_path.lstrip("/")
    full_url = f"{s['base_url'].rstrip('/')}/{_p}"
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{html.escape(full_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(s['title'])}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{html.escape(full_url)}">
<meta property="og:locale" content="{s.get('locale', 'ja_JP')}">
<meta property="og:image" content="{html.escape(img_url)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{html.escape(img_url)}">
<link rel="icon" type="image/svg+xml" href="{u('assets/favicon.svg')}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(s['title'])}" href="{u('feed.xml')}">
<link rel="stylesheet" href="{u('assets/style.css')}">
{extra}
</head>
<body>"""


def header(site: dict) -> str:
    s = site["site"]
    cats = "".join(
        f'<a href="{u("category/" + c["slug"] + ".html")}">{html.escape(c["label"])}</a>'
        for c in site["categories"].values()
    )
    return f"""
<header class="site-head">
  <div class="wrap head-inner">
    <a class="brand" href="{u("/")}">
      <span class="brand-mark" aria-hidden="true"></span>
      <span class="brand-name">{html.escape(s['title'])}</span>
    </a>
    <nav class="nav">{cats}<a href="{u("about.html")}">運営</a></nav>
  </div>
</header>"""


def footer(site: dict) -> str:
    s = site["site"]
    year = datetime.now(JST).year
    span = f"{s['copyright_from']}" if year == s["copyright_from"] else f"{s['copyright_from']}–{year}"
    return f"""
<footer class="site-foot">
  <div class="wrap">
    <p class="foot-tag">{html.escape(s['tagline'])}</p>
    <p class="foot-meta">
      <a href="{u("feed.xml")}">RSS</a> ・ <a href="{u("about.html")}">運営・免責</a>
    </p>
    <p class="foot-copy">© {span} {html.escape(s['title'])}</p>
  </div>
</footer>
</body>
</html>"""


def card(site: dict, p: dict, featured: bool = False) -> str:
    cat = site["categories"].get(p.get("category"), {"label": "その他", "slug": "misc"})
    cls = "card card-featured" if featured else "card"
    blurb = p.get("kicker") or p["excerpt"]
    return f"""
<article class="{cls}">
  <a class="card-cat" href="{u("category/" + cat['slug'] + ".html")}">{html.escape(cat['label'])}</a>
  <h2 class="card-title"><a href="{u(p['path'])}">{html.escape(p['title'])}</a></h2>
  <p class="card-excerpt">{html.escape(blurb)}</p>
  <p class="card-meta"><time datetime="{p['date']}">{p['date'].replace('-', '.')}</time><span class="dot"></span>{p['reading_min']}分</p>
</article>"""


def render_index(site: dict, posts: list[dict]) -> str:
    s = site["site"]
    if not posts:
        body = '<p class="empty">まだ記事がありません。</p>'
    else:
        lead, rest = posts[0], posts[1:]
        body = f"""
<section class="lead">
  {card(site, lead, featured=True)}
</section>
<section class="grid">
  {''.join(card(site, p) for p in rest)}
</section>"""
    return (
        head(site, f"{s['title']} — {s['tagline']}", s["description"], "index.html")
        + header(site)
        + f"""
<main class="wrap">
  <section class="hero">
    <h1 class="hero-title">{html.escape(s['tagline'])}</h1>
    <p class="hero-sub">{html.escape(s['description'])}</p>
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
  <section class="hero hero-sm">
    <p class="eyebrow">CATEGORY</p>
    <h1 class="hero-title">{html.escape(cat['label'])}</h1>
    <p class="hero-sub">{html.escape(cat['description'])}</p>
  </section>
  <section class="grid">{body}</section>
</main>"""
        + footer(site)
    )


def render_post(site: dict, p: dict, others: list[dict]) -> str:
    s = site["site"]
    cat = site["categories"].get(p.get("category"), {"label": "その他", "slug": "misc"})
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

    related = [o for o in others if o["slug"] != p["slug"]][:3]
    rel_html = ""
    if related:
        rel_html = f"""
<section class="related">
  <h2>ほかの記事</h2>
  <div class="grid">{''.join(card(site, r) for r in related)}</div>
</section>"""

    ld = f"""<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"NewsArticle",
"headline":{_json_str(p['title'])},"datePublished":"{p['date']}",
"description":{_json_str(p['excerpt'])},
"publisher":{{"@type":"Organization","name":{_json_str(s['title'])}}}}}
</script>"""

    return (
        head(site, f"{p['title']} — {s['title']}", p["excerpt"], p["path"], ld,
             image=f"ogp/{p['slug']}.png")
        + header(site)
        + f"""
<main class="wrap article-wrap">
  <article class="article">
    <p class="eyebrow"><a href="{u("category/" + cat['slug'] + ".html")}">{html.escape(cat['label'])}</a></p>
    <h1 class="article-title">{html.escape(p['title'])}</h1>
    {f'<p class="article-lede">{html.escape(p["kicker"])}</p>' if p.get('kicker') else ''}
    <p class="article-meta"><time datetime="{p['date']}">{p['date'].replace('-', '.')}</time><span class="dot"></span>読了 {p['reading_min']}分</p>
    <div class="prose">{p['body_html']}</div>
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
      <p>運営: {html.escape(s['author'])}<br>連絡先: 準備中</p>
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
    urls += [f"{base}/category/{c['slug']}.html" for c in site["categories"].values()]
    urls += [f"{base}/{p['path']}" for p in posts]
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


# ────────────────────────────── CSS ──────────────────────────────
CSS = """
:root{
  --ink:#14181d; --ink-2:#454e59; --ink-3:#78828f;
  --bg:#fbfaf8; --surface:#ffffff; --rule:#e4e1db;
  --accent:#b4472b; --accent-soft:#f6ece8;
  --max:1120px; --measure:38rem;
  --serif: "Iowan Old Style","Hiragino Mincho ProN","Yu Mincho",Georgia,serif;
  --sans: -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{ --ink:#eceae6; --ink-2:#b3b0aa; --ink-3:#85817a;
    --bg:#14151a; --surface:#1b1d23; --rule:#2c2f37;
    --accent:#e8825f; --accent-soft:#2a1f1b; }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.8;letter-spacing:.01em;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit;text-decoration:none}
.wrap{max-width:var(--max);margin:0 auto;padding:0 24px}

/* header */
.site-head{border-bottom:1px solid var(--rule);position:sticky;top:0;
  background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);z-index:10}
.head-inner{display:flex;align-items:center;justify-content:space-between;gap:24px;height:64px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.06em}
.brand-mark{width:9px;height:9px;border-radius:50%;background:var(--accent);
  box-shadow:0 0 0 4px var(--accent-soft);display:inline-block}
.brand-name{font-size:15px;text-transform:uppercase}
.nav{display:flex;gap:22px;font-size:13.5px;color:var(--ink-2);overflow-x:auto;white-space:nowrap}
.nav a{padding-bottom:2px;border-bottom:1px solid transparent}
.nav a:hover{color:var(--ink);border-bottom-color:var(--accent)}

/* hero */
.hero{padding:72px 0 44px;border-bottom:1px solid var(--rule);margin-bottom:44px}
.hero-sm{padding:52px 0 32px}
.hero-title{font-family:var(--serif);font-size:clamp(28px,4.4vw,46px);line-height:1.35;
  margin:0 0 14px;font-weight:600;letter-spacing:-.01em;max-width:30ch}
.hero-sub{margin:0;color:var(--ink-2);font-size:15px;max-width:32em;line-height:1.85}
.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);
  margin:0 0 12px;font-weight:600}

/* cards */
.lead{margin-bottom:56px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(288px,1fr));
  gap:1px;background:var(--rule);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.card{background:var(--bg);padding:28px 26px 30px}
.card-featured{background:var(--bg);padding:0;border:0}
.card-featured .card-title{font-size:clamp(24px,3.4vw,36px);line-height:1.4}
.card-featured .card-excerpt{font-size:16.5px;max-width:34em;line-height:1.9}
.card-cat{display:inline-block;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--accent);font-weight:600;margin-bottom:10px}
.card-title{font-family:var(--serif);font-weight:600;font-size:19px;line-height:1.55;margin:0 0 10px}
.card-title a{background-image:linear-gradient(var(--accent),var(--accent));
  background-size:0 1px;background-position:0 100%;background-repeat:no-repeat;transition:background-size .25s}
.card-title a:hover{background-size:100% 1px}
.card-kicker{margin:0 0 8px;color:var(--ink-2);font-size:14px}
.card-excerpt{margin:0 0 14px;color:var(--ink-2);font-size:14px;line-height:1.8}
.card-meta{margin:0;font-size:12px;color:var(--ink-3);letter-spacing:.04em;
  display:flex;align-items:center;gap:9px}
.dot{width:3px;height:3px;border-radius:50%;background:var(--ink-3);display:inline-block}

/* article */
.article-wrap{padding-top:56px}
.article{max-width:var(--measure);margin:0 auto}
.article-title{font-family:var(--serif);font-size:clamp(27px,4vw,40px);line-height:1.45;
  font-weight:600;margin:0 0 16px;letter-spacing:-.005em}
.article-lede{font-size:17px;color:var(--ink-2);line-height:1.85;margin:0 0 18px}
.article-meta{font-size:12.5px;color:var(--ink-3);display:flex;align-items:center;gap:9px;
  padding-bottom:28px;border-bottom:1px solid var(--rule);margin:0 0 36px}
.prose{font-size:16.5px;line-height:1.95}
.prose h2{font-family:var(--serif);font-size:23px;line-height:1.5;margin:52px 0 16px;
  font-weight:600;padding-top:6px;border-top:1px solid var(--rule)}
.prose h3{font-size:17px;margin:34px 0 10px;font-weight:700;letter-spacing:.01em}
.prose p{margin:0 0 22px}
.prose ul,.prose ol{margin:0 0 22px;padding-left:1.35em}
.prose li{margin-bottom:9px}
.prose a{color:var(--accent);border-bottom:1px solid color-mix(in srgb,var(--accent) 35%,transparent)}
.prose strong{font-weight:700}
.prose blockquote{margin:28px 0;padding:2px 0 2px 20px;border-left:2px solid var(--accent);
  color:var(--ink-2);font-size:15.5px}
.prose table{width:100%;border-collapse:collapse;margin:28px 0;font-size:14.5px;
  font-variant-numeric:tabular-nums}
.prose th,.prose td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--rule);vertical-align:top}
.prose th{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.prose td:first-child{color:var(--ink-2);width:34%;white-space:nowrap}
.prose code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.88em;
  background:var(--accent-soft);padding:2px 6px;border-radius:3px}
.prose hr{border:0;border-top:1px solid var(--rule);margin:40px 0}

/* sources */
.sources{margin-top:56px;padding-top:26px;border-top:1px solid var(--rule)}
.sources h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);
  margin:0 0 16px;font-weight:600}
.sources ol{margin:0 0 18px;padding-left:1.3em;font-size:14px;line-height:1.75}
.sources li{margin-bottom:9px}
.sources a{color:var(--ink);border-bottom:1px solid var(--rule)}
.sources a:hover{border-bottom-color:var(--accent)}
.src-pub{color:var(--ink-3);font-size:12.5px;margin-left:8px}
.sources-note{font-size:12.5px;color:var(--ink-3);line-height:1.8;margin:0}

.related{max-width:var(--max);margin:80px auto 0}
.related h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);
  margin:0 0 20px;font-weight:600}
.empty{color:var(--ink-3);padding:60px 0}

/* footer */
.site-foot{margin-top:96px;border-top:1px solid var(--rule);padding:44px 0 60px}
.foot-tag{font-family:var(--serif);font-size:17px;margin:0 0 14px;max-width:30ch}
.foot-meta{font-size:13px;color:var(--ink-2);margin:0 0 20px}
.foot-meta a{border-bottom:1px solid var(--rule)}
.foot-copy{font-size:12px;color:var(--ink-3);margin:0}

@media (max-width:640px){
  .hero{padding:44px 0 30px;margin-bottom:32px}
  .article-wrap{padding-top:34px}
  .grid{grid-template-columns:1fr}
  .prose{font-size:16px}
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
        ogp.render(site["site"]["tagline"], "GADGET SIGNAL", site["site"]["title"],
                   PUBLIC / "ogp" / "default.png")
        print(f"■ OGP画像 {made}枚" if made else "■ OGP画像: フォントが無いためスキップ")
    (PUBLIC / "index.html").write_text(render_index(site, posts), encoding="utf-8")
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
