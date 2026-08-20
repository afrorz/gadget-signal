# 運用ランブック

---

## 1. 公開までの初期設定（一度だけ）

### GitHub Pages で公開する

```bash
cd gadget-signal
git init && git branch -M main
git add . && git commit -m "init: Gadget Signal"
gh repo create <あなたのアカウント>/gadget-signal --public --source=. --push
```

1. GitHub のリポジトリ → **Settings → Pages → Build and deployment → Source を「GitHub Actions」に変更**
2. `config/site.yaml` の `base_url` を実際のURLに書き換える
   例: `https://<アカウント名>.github.io/gadget-signal`
3. `git push` すると `deploy.yml` が走って公開される

### 独自ドメインにする場合

1. `config/site.yaml` の `base_url` をそのドメインに変更
2. `scripts/build.py` の出力に `public/CNAME` を追加する（1行、ドメイン名のみ）
3. DNS で `A` レコードを GitHub Pages のIPに、または `CNAME` を `<アカウント>.github.io` に向ける
4. Settings → Pages → Custom domain に入力し、Enforce HTTPS を有効化

独自ドメインは検索評価が自分に貯まるので、**本気でやるなら最初から取ったほうがいい**（後から移すと初期の評価を捨てることになる）。

### 検索エンジンへの登録

- Google Search Console にプロパティを追加 → `sitemap.xml` を送信

### アクセス解析（Cloudflare Web Analytics）

`config/site.yaml` の `cf_analytics_token` にトークンを入れると、全ページの `<head>` に
ビーコンのスクリプトが入る。**Cookie を使わないので同意表示は不要。**
空文字のあいだはタグを一切出さないので、外部スクリプトも読み込まない。

レポートは https://dash.cloudflare.com/ → Analytics → Web analytics で見る。

**設定方法に注意点がある。** `gadgetterminal.com` は Cloudflare で DNS だけを管理し、
通信は GitHub Pages に直接届く構成（グレー雲）。このため Cloudflare が提示してくる
「自動セットアップ」は**機能しない**（プロキシを通過しない通信にはビーコンを注入できないため）。

サイト追加時にホスト名を入力したら、候補の**下段**にある
「Click here to use "gadgetterminal.com" which does not belong to Cloudflare websites」
を選ぶこと。これで JS スニペット方式になり、トークンが発行される。

計測を止めたいときは `cf_analytics_token` を空に戻して再ビルドすれば、タグごと消える。

### GA4 を併用する場合

`analytics_id` に測定ID（`G-` で始まる）を入れれば、Cloudflare と併用できる。

ただし `analytics.google.com` は広告ブロック系の遮断リストに載っており、
**開発環境のネットワークからは管理画面を開けない**（DNS が経路上で書き換えられている）。
Chrome のセキュア DNS を有効にすれば開けるが、常用は勧めない。
- 最初の 2〜3 週間はインデックスされない。焦らない

---

## 2. 定時実行

`.github/workflows/collect.yml` が毎晩 **JST 22:30** に収集を実行し、`data/digest/` にコミットする。
その30分後の **JST 23:00** に `daily-article.yml` が記事を生成する。

記事生成は `claude_code_oauth_token` を使うため **Claude サブスクリプションの利用枠を消費する**（GitHub Actions の実行時間自体は public リポジトリなので無料）。
日中の作業と5時間ウィンドウを取り合わないよう、意図的に夜に寄せてある。時刻を変えるときはこの点を考慮すること。
手元で回すなら:

```bash
python3 scripts/collect.py --top 30
```

時刻を変える場合は cron を UTC で書く（JST = UTC+9）。

| やりたい時刻(JST) | cron (UTC) |
|---|---|
| 07:00 | `0 22 * * *` |
| 22:30 | `30 13 * * *` |
| 23:00 | `0 14 * * *` |
| 09:00 | `0 0 * * *` |
| 07:00 と 19:00 | `0 22,10 * * *` |

---

## 3. よくあるトラブル

### 特定のソースだけ 0 件になる

```
! techpowerup: 0件 (status=403)
```

多くは User-Agent 拒否。`config/feeds.yaml` の `defaults.user_agent` を実在ブラウザ相当の文字列に変えると通ることが多い。
それでも駄目なら、そのソースに `enabled: false` を付けて外す。**1ソースが死んでも全体は止まらない設計になっている。**

### 同じ記事が何度も候補に出る

`data/seen.json` が消えている可能性がある。GitHub Actions で回している場合は、コミットが成功しているか確認する。

### 記事が公開されない

- `draft: true` が残っていないか
- front matter の `---` が先頭行にあるか（前に空行があるとパースに失敗する）
- ビルドログに `! front matter がありません` が出ていないか

### クラスタリングが効きすぎて別の話題がまとまる

`scripts/collect.py` の `cluster()` にある閾値 `0.55` / `overlap >= 3` を上げる。

---

## 4. 育て方のロードマップ

| 時期 | やること | 判断基準 |
|---|---|---|
| 〜1か月 | 記事30本。ソースを10→20に増やす | 毎日1本以上出せているか |
| 2〜3か月 | Search Console で流入キーワードを見る。伸びたテーマのまとめ記事を作る | 検索表示回数が動き出したか |
| 3か月〜 | 収益化を検討（`site.yaml` の `affiliate.enabled`）。X連携で初速をつける | 月間PVが4桁に乗ったか |
| 6か月〜 | 実機レビュー（現物購入）を混ぜる。一次コンテンツが最大の差別化 | 指名検索が発生しているか |

### 収益化を入れるとき

`config/site.yaml`:

```yaml
affiliate:
  enabled: true
  amazon_tag: "your-tag-22"
```

Amazon アソシエイトの審査は「独自コンテンツがある記事が一定数あること」が実質要件になる。
翻訳寄りの記事だけでは通りにくいので、**日本視点セクションの厚みがそのまま審査対策にもなる。**

---

## 5. 法務・権利の再確認

- 元記事の文章を丸ごと翻訳して載せない（翻訳権の侵害にあたりうる）
- 画像を転載しない。プレス素材でも利用条件を確認する
- 事実（スペック・価格・日付）そのものに著作権はない。**事実を抜き出して自分の言葉で書く** のが安全かつ品質も高い
- 引用する場合は、出典明示・引用部分の明確な区別・主従関係（自分の記述が主）の3点を守る
- 訂正依頼への窓口を `about.html` に用意しておく（現在「準備中」。連絡先を入れること）
