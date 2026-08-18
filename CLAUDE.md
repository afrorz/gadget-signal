# Gadget Terminal

海外ガジェット情報を毎日収集し、日本語記事にして静的サイト（https://gadgetterminal.com）で公開するリポジトリ。

```
収集 (collect.py) → ダイジェスト → 執筆(レビュー付き) → ビルド (build.py) → 公開 (公開.bat)
```

## この媒体の勝ち筋

**海外で報じられて、まだ日本語記事が無い話。** とくにクラウドファンディング発の新製品が主戦場。
大手の新製品ニュース、国内プレスリリース転載、セール情報は扱わない。

判断に迷ったら **`docs/PLAYBOOK.md` を読む。品質の定義はそこにある。**

## 絶対に破らないルール

記事を書く前に必ず確認する。詳細は `docs/PLAYBOOK.md` の「3. 絶対に破らないルール」。

- **元記事に無い数字を書かない。** 推測なら「未発表」「編集部推定」と明記する
- **リークは必ずリークと書き、確度に言及する**
- **翻訳ではなく再構成。** 元記事の文をそのまま訳して並べない
- **画像を転載しない。** front matter に他サイトの画像を入れない
- **円換算を書かない。** 為替で陳腐化する。ドル/ユーロのまま
- **一社しか報じていない話は、その旨を書く**
- **在庫・価格には「掲載時点」と付ける**
- **記事末に必ず「日本から見るとどうか」を書く。** 技適・電波法・国内流通・日本語対応。ここが差別化の中心
- **クラファン案件は「まだ製品ではない」ことを明記する。** 出資は購入ではない

## 文体

煽らない。感嘆符と絵文字を使わない。断定できることは断定し、できないことは「確認できていない」と書く。
曖昧に濁さない。読者が次に取れる行動（買う/待つ/諦める/代替を探す）まで書けると強い。

## 公開はしない

**`git push` を実行しない。** 公開は人間が `公開.bat` をダブルクリックして行う運用。
`git add` と `git commit` までは行ってよい。`.claude/settings.json` でも push を deny している。

## コマンド（Windows）

このPCは Python 3.10 / Windows。`python3` ではなく **`python`** を使う。
PowerShell では `&&` が使えないので `;` で繋ぐ。npm 系は `npm.cmd` / `npx.cmd`。

```bash
python scripts/collect.py --top 30      # 収集 → data/digest/YYYY-MM-DD.md
python scripts/collect.py --dry-run     # seen.json を汚さず件数だけ確認
python scripts/build.py                 # content/posts → public/
python scripts/build.py --serve         # http://localhost:8000 で確認
```

収集は `.github/workflows/collect.yml` が毎朝 JST 07:00 に自動実行し、`data/digest/` にコミットする。
**手元で collect.py を回す前に `git pull` すれば、その日のダイジェストは既にあることが多い。**

## ディレクトリ

| パス | 役割 |
|---|---|
| `config/feeds.yaml` | 収集ソースとスコアリング。**育てる対象はここ** |
| `config/site.yaml` | サイト名・カテゴリ・公開URL |
| `scripts/collect.py` | RSS収集 → 重複排除 → クラスタリング → スコアリング |
| `scripts/build.py` | Markdown → 静的HTML（RSS/sitemap/OGP/構造化データ込み） |
| `content/posts/*.md` | 記事本体。front matter + Markdown |
| `data/digest/` | 日次ダイジェスト（.md と .json） |
| `public/` | ビルド成果物。**手で編集しない** |
| `docs/PLAYBOOK.md` | 編集方針・記事の型・絶対ルール |
| `docs/RUNBOOK.md` | 公開設定・トラブル対応 |

## カテゴリ

`smartphone`（スマホ・ウェアラブル）/ `pc`（PC・周辺機器・自作）/ `weird`（変わり種・クラファン）
front matter の `category` にはこの3つのいずれかを書く。
