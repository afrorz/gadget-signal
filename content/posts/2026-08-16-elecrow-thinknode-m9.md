---
title: Elecrow ThinkNode M9 — 電波が届かない場所で文字を送る、75ドルのQWERTY端末
slug: elecrow-thinknode-m9
keyword: ThinkNode M9
category: weird
date: 2026-08-16
kicker: BlackBerry の子孫のような見た目だが電話ではない。LoRa と MeshCore で、携帯圏外どうしを直接つなぐメッシュ通信端末。
tags: [LoRa, MeshCore, Meshtastic, ESP32, 変わり種]
embeds:
  - type: youtube
    id: l7ITJTsp9CY
    caption: ThinkNode M9 の実機レビュー。QWERTYキーと画面の大きさが分かる（andy kirby）
sources:
  - title: "Elecrow ThinkNode M9 is a phone-like mesh communicator with a 2.4 inch screen, QWERTY keyboard, and LoRa"
    url: https://liliputing.com/elecrow-thinknode-m9-is-a-phone-like-mesh-communicator-with-a-2-4-inch-sccreen-qwerty-keyboard-and-lora/
    publisher: Liliputing
---

**Elecrow ThinkNode M9** は、iPhone と Android ではなく BlackBerry と Palm Treo の側に進化した世界線から来たような端末だ。実際にはスマートフォンではない。通話機能はなく、携帯電話網も使わない。**LoRa** による長距離無線と **MeshCore** を使って、端末どうしが直接メッセージをやり取りする通信機である。

## スペック

| 項目 | 内容 |
|---|---|
| SoC | ESP32-S3R8 |
| 無線（メッシュ） | LoRa モジュール Semtech LR1110 |
| その他無線 | Wi-Fi 4（802.11n）、Bluetooth 5.0 |
| 測位 | GPS 受信機 |
| ディスプレイ | 2.4インチ LCD / 320×240（非タッチ） |
| 入力 | 37キー QWERTY ＋ 操作用ファンクションキー |
| バッテリー | 2,300mAh |
| 端子 | USB 2.0 Type-C（充電） |
| 音 | ブザー（スピーカーではない） |
| サイズ | 126 × 67 × 10mm |
| 重量 | 123g |
| 価格 | 約75ドル（Elecrow で販売中） |

近い立ち位置の製品としては LILYGO の T-Deck Pro シリーズがある。

## 何が面白いのか

この手のデバイスの本質は「インフラに依存せずに文字が届く」ことにある。基地局も、インターネットも、契約も要らない。端末どうしが中継し合ってメッシュを作り、ホップを重ねてメッセージを運ぶ。

**スマホと決定的に違うのは、通信が「圏内かどうか」ではなく「近くに仲間の端末があるかどうか」で決まる点だ。** だから単体で買っても意味がなく、最低2台、実用的にはグループで導入するタイプの製品になる。登山・キャンプ、イベント運営、アマチュア無線的な実験、災害時の備えといった文脈で使われている。

75ドルという価格は、フルキーボードと GPS を積んだ完成品としてはかなり安い。ESP32-S3 なので、ファームウェアを自分で書き換えて遊ぶ余地も大きい。

## 日本から見るとどうか

**ここが最大の論点で、そのまま買って使うことはできない。**

LoRa の運用周波数は国ごとに割り当てが違う。日本で免許不要で使えるのは 920MHz 帯（ARIB STD-T108）で、この帯域に適合し、かつ **技術基準適合証明（技適）を取得した無線機であること** が必要になる。海外向けの LoRa 機は 868MHz（EU）や 915MHz（US）向けの設定で出荷されることが多く、**技適のない機器を国内で電波を出して使えば電波法違反となる。**

ThinkNode M9 について、掲載時点で以下は確認できていない。

- 日本向け 920MHz 帯モデルの有無
- 技適取得の有無
- 国内正規流通の有無

したがって現時点での現実的な位置づけは、「海外でこういう製品が75ドルで出ている」という情報として押さえておくもの、ということになる。国内で LoRa メッシュを試したい場合は、**技適取得済みの 920MHz 帯モジュールを使った製品を選ぶ** のが唯一の安全な道筋だ。技適の有無は必ず販売元の表示と総務省の登録情報で確認してほしい。

Elecrow の製品ページで日本向けモデルの取り扱いが確認でき次第、追記する。
