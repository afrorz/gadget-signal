---
title: HDD 443,156台・166万ドライブ年の査読論文 — 故障率はHGSTがSeagateの41%、東芝が107%
slug: backblaze-hdd-study
category: pc
date: 2026-08-16
kicker: Backblazeが公開してきた稼働データを、エセックス大学の研究者が回帰分析にかけて査読論文にした。年齢・容量・温度を揃えたうえでのメーカー別故障率が初めて出た。
tags: [HDD, Backblaze, 信頼性, NAS]
sources:
  - title: "HDD failure rates by manufacturer revealed"
    url: https://www.blocksandfiles.com/disk/2026/08/07/hdd-failure-rates-by-manufacturer-revealed/5284845
    publisher: Blocks & Files
  - title: "Peer-reviewed study of 443,000 Backblaze hard drives ranks HGST most reliable and Toshiba the least"
    url: https://www.tomshardware.com/pc-components/hdds/peer-reviewed-study-of-443000-backblaze-drivers-ranks-hgst-most-reliable-and-toshiba-least
    publisher: Tom's Hardware
---

クラウドバックアップ事業者の Backblaze は、自社データセンターのHDD稼働・故障データを長年公開してきた。そのデータを **エセックス大学の Christoph Siemroth 准教授と Yeomyung Park** が統計的に分析し、IEEE Xplore で査読論文として発表した。

対象は **443,156台のエンタープライズHDD、166万ドライブ年以上、2013年から2025年Q2まで**。

## 結果：Seagateを100としたときの故障率

| メーカー | 相対故障率 |
|---|---|
| HGST | 約41% |
| Western Digital | 約52% |
| Seagate | 100%（基準） |
| Toshiba | 約107% |

**SeagateとToshibaは、WDとHGSTのおよそ2倍の頻度で壊れている**、という結論になる。

## この研究の何が新しいのか

Backblaze の生データは以前から公開されており、年次レポートも出ていた。ただ、そのまま比較するには問題があった。**メーカーごとに導入時期が偏っている**からだ。初期のコホートに特定メーカーが集中していると、「古い個体が多いメーカー」が不利に見えてしまう。

今回の研究は回帰分析で **ドライブの年齢・容量・フォームファクタ・温度を統制**し、実質的に「同じ年齢のドライブ同士」を比較している。ここが従来の集計との違いだ。

論文自体も、Backblazeのデータに含まれるバイアス（右側打ち切り、メーカー構成の時期的な偏り）を課題として認めている。

## 日本から見るとどうか

**まず、これはエンタープライズ向けドライブを、データセンターの環境で、24時間365日回した結果である**という点を外してはいけない。家庭のNASや自作PCで同じ比率になる保証はどこにもない。温度・振動・電源品質・稼働時間のすべてが違います。

そのうえで、日本の読者にとって実用的な読み方は3つ。

**1. NASを組むなら、この序列は判断材料になる。** 常時稼働という条件がデータセンターに近いためです。ただし各社のNAS向けシリーズ（IronWolf、Red、N300など）は本研究の対象と同じ製品ではありません。

**2. HGSTブランドの扱いに注意。** HGSTは現在Western Digital傘下で、新品として「HGST」の名前で買える製品は限られます。上位2つがどちらもWD系という結果は、実務的には「WD系を選ぶ」に近い意味になります。

**3. 東芝が最下位という結果は、額面通りに受け取らない。** 日本メーカーであることと故障率は無関係ですが、同時に **107%という数字はSeagateとほぼ同等**であり、「東芝だけが突出して悪い」という読み方は誤りです。順位ではなく比率を見てください。

そして最も実用的な結論は、論文の外にあります。**どのメーカーを選んでも壊れる**。41%と107%の差は「壊れにくさ」の差であって、「壊れない」ではない。バックアップの設計のほうが、メーカー選びより桁違いに効きます。
