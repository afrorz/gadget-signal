---
name: daily-drafts
description: Gadget Terminal の毎朝の記事ドラフトを3本作る。ダイジェストを取得して候補を選び、元記事を読んで content/posts/ に front matter 付き Markdown を書き、ビルドまで通す。「今日の記事を作って」「毎朝の作業」「/daily-drafts」と言われたときに使う。
---

# 毎朝の記事ドラフト生成

`content/posts/` に、その日の記事ドラフトを **3本** 作るまでが仕事。**公開はしない。**

## 手順

### 1. ダイジェストを用意する

まず `git pull` する。GitHub Actions が毎晩 JST 22:30 に収集して `data/digest/` にコミットしているので、
その日のダイジェストは既にあることが多い。

```bash
git pull
```

`data/digest/<今日の日付>.md` があればそれを読む。**無ければ手元で収集する。**

```bash
python scripts/collect.py --top 30
```

`python3` ではなく `python`（このPCは Python 3.10）。
`ModuleNotFoundError` が出たら `pip install -r requirements.txt` を実行してから再試行する。

### 2. 書く3本を選ぶ

`data/digest/<今日の日付>.md` を読み、スコア上位から3本選ぶ。選ぶ基準は `docs/PLAYBOOK.md` の
「1. この媒体が勝てる場所」と「4. スコアと採否の目安」。

- **12pt 以上があれば必ず1本目に入れる**（その日の主役）
- **クラファン案件（`【クラファン】` 表示）を優先する。** この媒体の主戦場
- 0pt 以下は書かない
- **`content/posts/` に同じ製品の記事が既に無いか確認する。** 重複を出さない
- 3本はカテゴリが偏らないほうがよい（smartphone / pc / weird）

選んだ3本を、書き始める前にユーザーへ提示する。番号・タイトル・スコア・選んだ理由を1行ずつ。
**ユーザーが別のものを指定したらそちらを優先する。**

### 3. 元記事を読む

各記事について:

1. ダイジェストの該当項目のURLを `data/digest/<今日の日付>.json` から引く
2. **WebFetch で元記事の本文を取得する。** 読まずに書かない
3. `also_covered_by` / `related_urls` があれば **そちらも読む。** 片方にしかない数字が拾える
4. 型番・価格・寸法・日付・出典名を箇条書きで抜き出す。
   **ここで抜き出せなかった数字は記事に書かない**

許可されていないドメインで WebFetch が止まったら、ユーザーに許可を求める。
恒久的に使うソースなら `.claude/settings.json` の `allow` に
`"WebFetch(domain:そのドメイン)"` を追記してよい。

### 4. 書く

`docs/PLAYBOOK.md` の「2. 記事の構造」に従う。フォーマットの詳細は
`docs/SKILL-gadget-article.md` にある（媒体名の表記だけ古く "Gadget Signal" になっているが、
正しくは **Gadget Terminal**）。

ファイル名は `content/posts/YYYY-MM-DD-<slug>.md`。

```markdown
---
title: 固有名詞と数字を含むタイトル（「話題」「すごい」は禁止）
slug: url-safe-slug
category: smartphone | pc | weird
date: YYYY-MM-DD
kicker: 何が起きたかを言い切る一文リード
tags: [タグ, タグ]
sources:
  - title: 元記事タイトル
    url: https://...
    publisher: 媒体名
---

導入1〜2段落（何が・いつ・いくら を最初に確定させる）

## 見出し（スペックは必ず表にする）

## 日本から見るとどうか
```

**front matter で `:` を含む値は必ずダブルクォートで囲む。** とくに英語の元記事タイトルは
`Meet Token Monitor: A Physical AI Dashboard` のようにコロンを含むことが多く、
そのまま書くと YAML パースに失敗して `build.py` が落ちる。

```yaml
  - title: "Meet Token Monitor: A Physical AI Dashboard on Kickstarter"
```

`CLAUDE.md` の「絶対に破らないルール」を必ず守る。とくに:

- 元記事に無い数字を書かない
- 円換算を書かない
- 画像を転載しない（front matter に画像を入れない）
- **「日本から見るとどうか」は必須。** 技適・電波法・国内流通・日本語対応を具体的に
- クラファン案件は「まだ製品ではない」「調達額は取得時点」「配送時期は予定」を明記

YouTube を埋め込む場合は、**動画IDの存在を必ず確認してから書く。**

```
https://www.youtube.com/oembed?url=https%3A//www.youtube.com/watch%3Fv%3D<動画ID>&format=json
```

`title` と `author_name` が返らないIDは使わない。別製品・前世代の動画は貼らない。

### 5. 自己チェック

3本書き終えたら、`docs/PLAYBOOK.md` の3点チェックを自分でかける。

1. **数字が元記事と一致しているか**
2. **リークがリークと書かれているか**
3. **「日本から見るとどうか」が具体的か**（一般論で埋めていないか）

加えて、`sources` に参照した全URLが入っているかを確認する。**例外なし。**

### 6. ビルドを通す

```bash
python scripts/build.py
```

エラーが出たら直す。よくある原因は `docs/RUNBOOK.md` の「3. よくあるトラブル」:
front matter の `---` が先頭行にない、`draft: true` が残っている、など。

### 7. 報告する

作った3本について、ファイルパス・タイトル・カテゴリ・字数を一覧で出す。
そのうえで、**レビューしてほしい点があれば具体的に挙げる**（数字の確度が低い箇所、
日本視点が薄いと自覚している箇所、一社しか報じていない箇所）。

最後に、次の操作をユーザーに案内する。

> 記事を直したいときは、そのまま「2本目の日本視点が薄い。技適の話を具体的に」のように言ってください。
> 公開するときは `公開.bat` をダブルクリックしてください。

## やらないこと

- **`git push` しない。** 公開は人間が `公開.bat` で行う
- **`public/` を手で編集しない。** ビルド成果物
- **元記事を読まずに書かない**
- **3本を超えて量産しない。** 指示があれば別
