# Gadget Terminal

海外ガジェット情報を毎日収集し、日本語記事にして静的サイトで公開するまでの一式。

```
収集 (collect.py) → ダイジェスト → 執筆(レビュー付き) → ビルド (build.py) → 公開 (GitHub Pages)
```

---

## セットアップ

```bash
pip install -r requirements.txt
```

Python 3.11 以上。依存は `feedparser` / `PyYAML` / `Markdown` の3つだけ。

## 毎日やること

```bash
# 1. 収集 — data/digest/YYYY-MM-DD.md ができる
python3 scripts/collect.py --top 30

# 2. ダイジェストを読み、書くものを選ぶ（3〜5本）
#    → Claude に「今日のダイジェストの1・3・5を記事にして」と渡す
#    → content/posts/YYYY-MM-DD-<slug>.md ができる
#    → docs/PLAYBOOK.md の3点チェックでレビュー

# 3. ビルドしてローカル確認
python3 scripts/build.py --serve      # http://localhost:8000

# 4. 公開
git add . && git commit -m "post: ..." && git push
```

`git push` すると `.github/workflows/deploy.yml` が走り、GitHub Pages に反映される。
収集自体も `.github/workflows/collect.yml` で毎朝 JST 07:00 に自動実行される（手元で回さなくてよい）。

---

## ディレクトリ

| パス | 役割 |
|---|---|
| `config/feeds.yaml` | 収集ソースとスコアリング設定。**育てる対象はここ。** |
| `config/site.yaml` | サイト名・説明・カテゴリ・公開URL |
| `scripts/collect.py` | RSS収集 → 重複排除 → 話題クラスタリング → スコアリング |
| `scripts/build.py` | Markdown記事 → 静的HTML（＋RSS/sitemap/OGP/構造化データ） |
| `content/posts/*.md` | 記事本体。front matter + Markdown |
| `data/digest/` | 日次ダイジェスト（JSON / Markdown） |
| `data/seen.json` | 既出URLの記録（30日で自動削除） |
| `public/` | ビルド成果物。**手で編集しない** |
| `docs/PLAYBOOK.md` | 編集方針・記事の型・守るべきルール |
| `docs/RUNBOOK.md` | 公開設定・トラブル対応・チューニング |

---

## 記事の front matter

```yaml
---
title: 記事タイトル（固有名詞と数字を入れる）
slug: url-safe-slug
category: smartphone | pc | weird
date: 2026-08-16
priority: 10          # 任意。大きいほどその日の先頭に来る
kicker: 一文リード。カードの説明文にも使われる
tags: [タグ, タグ]
draft: true           # 任意。true にするとビルドから除外される
sources:              # 必須。参照した全URL
  - title: 元記事タイトル
    url: https://...
    publisher: 媒体名
---

本文（Markdown）
```

---

## 収集のチューニング

`config/feeds.yaml` の `scoring` を触るだけで、拾ってくる話題の傾向が変わる。

- 記事化しないものが上位に来る → `penalty` にその語を追加
- 拾ってほしいジャンルが埋もれる → `boost` にキーワードを追加
- ソースを増やす → `sources` に1ブロック足すだけ。`tier` は 1（一次寄り）〜3（ネタ枠）

ソースを追加したら必ず一度 `--dry-run` で件数を確認する。

```bash
python3 scripts/collect.py --dry-run --top 50
```

---

## ライセンスと権利

記事本文は自社著作物。参照元の文章・画像は転載しない（`docs/PLAYBOOK.md` の「絶対に破らないルール」参照）。
