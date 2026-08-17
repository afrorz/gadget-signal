---
title: "AIコーディング利用量を専用ディスプレイで表示する「Token Monitor」がKickstarter開始、99ユーロから"
slug: token-monitor-esp32
keyword: Token Monitor
category: pc
date: 2026-08-18
kicker: Claude Code・Codex CLI・Antigravity CLIのトークン消費量を、常設の4インチタッチディスプレイでリアルタイムに表示するESP32-S3デバイスがKickstarterで支援受付中。
tags: [ESP32, Kickstarter, Claude Code, 自作ガジェット, オープンソース]
sources:
  - title: "Token Monitor - An ESP32-S3 desktop display that tracks AI coding assistant usage (Crowdfunding)"
    url: https://www.cnx-software.com/2026/08/07/token-monitor-an-esp32-s3-desktop-display-that-tracks-ai-coding-assistant-usage/
    publisher: CNX Software
---

Fractal Manifoldが開発した**Token Monitor**は、AIコーディングアシスタントの利用量を専用ハードウェアで常時表示するデスクトップディスプレイだ。Claude Code・Codex CLI・Antigravity CLIのクォータ消費、セッション上限、トークン数、リセットまでの時間、推定コストといった情報を、PC画面を開かなくても確認できる。Kickstarterで支援受付中で、まだ量産・出荷前の段階にある。

## スペック

| 項目 | 内容 |
| --- | --- |
| ディスプレイ | 4インチ 480×480 IPSタッチスクリーン（ST7701ドライバ、GT911タッチコントローラ） |
| SoC | Espressif ESP32-S3（デュアルコアTensilica LX7、最大240MHz） |
| メモリ | 512KB SRAM、8MB PSRAM、16MBフラッシュ |
| 無線 | Wi-Fi 4、Bluetooth LE 5 |
| 電源 | USB Type-C給電、オプションで1S Li-ionバッテリー（AXP2101 PMIC、5時間以上駆動） |
| サイズ | 86×86mm |
| 対応アシスタント | Claude Code、Codex CLI、Antigravity CLI |

仕組みは、ユーザーのPCまたはネットワーク内の常時稼働マシン（Raspberry Piやヘッドレスの Linux VPSなど）上でローカルのブローカーソフト「tokenmonitor-mcp」（Apache 2.0ライセンスのオープンソース）を動かし、そこから使用状況データを本体に送る方式。認証情報はユーザーのマシン内にとどまる設計になっている。

## 価格と発送予定

Kickstarterの価格は次の通り。

| ティア | 価格 |
| --- | --- |
| Super Early Bird | 99ユーロ（約115ドル） |
| Early Bird | 120ユーロ |

目標金額は25,000ユーロ。発送先は現時点で米国・カナダ・EU・英国に対応し、初回出荷は2026年11月予定。目標金額の達成状況や現在の支援者数は、本稿執筆時点で確認できていない。

## 日本から見るとどうか

**まだクラウドファンディング段階であり、目標金額に達しなければプロジェクト自体が実施されない可能性もある。** 発送予定時期も現時点での予定にすぎない。

**発送対象地域** — 現状、発送先に日本は含まれていない。支援自体ができない、もしくは別送手配が必要になる可能性がある。この点はプロジェクトページの更新を待つ必要がある。

**技適** — Wi-Fi 4とBluetooth LE 5を積んだESP32-S3ベースの機器であり、国内で無線機能を使うには技適の取得が前提になる。ESP32モジュール自体に技適マークが付いた個体もあるが、本製品がどのモジュール・ファームウェア構成で技適を取得しているかはCNX Softwareの記事からは確認できない。

**類似コンセプトの先行事例** — AIコーディングアシスタントの利用量を可視化する自作ESP32プロジェクトは、Token Monitor以前にも「Clawdmeter」など複数がDIYコミュニティで発表されている。Token Monitorはそれを完成品・量産品として仕上げた位置づけと見てよい。日本語UIへの対応有無は記事からは分からない。

ハードウェア自体は汎用的なESP32-S3ボードなので、技適さえクリアできれば国内の開発者コミュニティでも使い道はある。ただし現時点では「支援できるかどうか」からして未確定な段階にあることは押さえておきたい。
