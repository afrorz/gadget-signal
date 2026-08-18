---
title: CtrlVibe AI Consoleは9キーのAI操作用キーパッド。Kickstarterで目標10,000ドルに対し33,018ドル、109ドルから
slug: ctrlvibe-ai-console
keyword: CtrlVibe
category: pc
date: 2026-08-17
kicker: AIコーディングツールの「実行」「停止」「モデル切り替え」を物理キーに割り当てる専用キーパッド。CtrlVibeがKickstarterで公開したAI Consoleは、品切れが続くOpenAIのCodex Microより安い代替を狙う。ただし出荷は2026年11月予定で、まだ製品ではない。
tags: [Kickstarter, キーパッド, クラウドファンディング, AIコーディング, 自作キーボード]
sources:
  - title: CtrlVibe AI Console keypad - An OpenAI Codex Micro alternative for AI workflows (Crowdfunding)
    url: https://www.cnx-software.com/2026/08/05/ctrlvibe-ai-console-keypad-an-openai-codex-micro-alternative-for-ai-workflows/
    publisher: CNX Software
  - title: CtrlVibe Takes on Codex Micro
    url: https://www.hackster.io/news/ctrlvibe-takes-on-codex-micro-fadba9a457fa
    publisher: Hackster.io
  - title: "CtrlVibe: AI Workflow Console for Coders & Creators"
    url: https://www.kickstarter.com/projects/663521697/ctrlvibe-ai-keyboard-workflow-control-console-for-the-ai-era
    publisher: Kickstarter
  - title: Track CtrlVibe on BackerTracker
    url: https://www.backerkit.com/projects/663521697/ctrlvibe-ai-keyboard-workflow-control-console-for-the-ai-era
    publisher: BackerKit
---

AIにコードを書かせる作業は、キーボードから手を離さないわりに操作の種類が多い。走らせる、止める、差分を見る、モデルを替える、やり直す。CtrlVibeがKickstarterに出した「CtrlVibe AI Console」は、この操作を9個の物理キーとダイヤルに逃がす卓上デバイスだ。

CNX Softwareが8月5日に報じた。プロジェクトは7月30日に開始し、終了は9月13日。BackerKitの集計では、目標額10,000ドルに対して33,018ドルが集まっており、達成率は330%となっている（掲載時点）。

## 何が付いているか

| 項目 | 内容 |
| --- | --- |
| キー | 9個のロープロファイルメカニカルキー（ホットスワップ対応） |
| ディスプレイ | 1.14インチカラー液晶 |
| ロータリーエンコーダ | EC11（ツール／モデル切り替え用） |
| トグルスイッチ | ステンレス製3ポジション |
| マイク | MEMSマイクアレイ内蔵 |
| 照明 | RGBステータスライト |
| 接続 | USB Type-C、Bluetooth、2.4GHzワイヤレス |
| 本体サイズ | 120×89×30mm |
| 筐体 | アルミ合金トップケース、ブラスト＋アルマイト仕上げ |
| MCU | 未公表 |

初期状態のキー割り当ては、Record、Run、Stop、Apply、Retry、Agent、Model、Diff、Promptの9つ。2キー同時押しと3キー同時押しにも別の動作を割り当てられる。音声入力は内蔵マイクで拾い、処理はローカルか、オプションのクラウドサービスのどちらかを選ぶ。

価格はスーパーアーリーバードが109ドル、カーボンマトリックス版が129ドル、通常のアーリーバードが139ドル。出荷予定は2026年11月とされている。

Hackster.ioは、OpenAIのCodex Microが230ドルで長く在庫切れが続いている点を挙げ、その空白を埋める製品だと位置づけている。

## 数字の扱いについて

BackerKitの集計ではバッカー数が26人と表示されている。しかし33,018ドルという調達額と109〜139ドルという単価を突き合わせると、この人数は明らかに整合しない。集計側の反映遅れか不具合の可能性が高く、本稿ではバッカー数を参考値としても採用しない。目標額と調達額、達成率は複数の表示で一致しているため、そちらを掲載時点の値として記載した。

いずれにしても、クラウドファンディングの調達額は日々動く。ここに書いた数字は8月17日時点のものであり、支援を検討するなら必ず自分でプロジェクトページを開いて確認してほしい。

## まだ製品ではない

支援は予約購入ではない。CNX Softwareが指摘しているとおり、制御ソフトウェアである「CtrlVibe Configurator」はまだ公開されておらず、キャンペーン終了後に提供されるとされている。つまり現時点では、このキーパッドを実際に動かすソフトを誰も外から検証できない。ハードウェアの写真と説明だけがある状態だ。

MCUが未公表である点も引っかかる。ホットスワップ対応の9キーとエンコーダ、液晶、マイク、無線という構成は、既存の自作キーボード用ファームウェアで実現可能な範囲に見えるが、その情報は出ていない。ファームウェアが開いているのか閉じているのかも確認できていない。

出荷予定の2026年11月は、キャンペーン終了から2か月後にあたる。金型を使うアルミ筐体と無線モジュールの認証取得を含めた工程としては、余裕のある日程とは言いがたい。納期が後ろにずれる前提で考えたほうがいい。

## 日本から見るとどうか

**技適の問題がある。** Bluetoothと2.4GHzワイヤレスを積んでいるので、無線を使う限り日本では技術基準適合証明が必要になる。技適マークのない無線機を国内で発信させれば電波法違反だ。CtrlVibeが技適を取得する予定があるかどうかは、公表された情報の中に記載がなく、確認できていない。

**USB接続だけで使えるかどうかが分かれ目になる。** 本機はUSB Type-Cポートを備えている。無線を切って有線でのみ使えるなら電波を出さない運用は理屈のうえでは成り立つが、無線機能を完全に無効化できる仕様かどうかは公開情報から判断できない。日本から支援するなら、この一点をプロジェクトオーナーに質問してから決めるべきだ。

**電源はUSB給電なので電圧とプラグ形状の問題はない。** ACアダプタを別途用意する場合だけ、PSEマークのある国内向け製品を選べばいい。

**日本語環境での使い勝手は未知数。** キーに割り当てるのはショートカットとコマンドなので、日本語入力そのものの問題は小さい。ただし設定ソフトのUIが日本語化されるかどうか、音声入力が日本語を扱えるかどうかは、いずれも公開情報がない。

**代替はある。** 同じことは市販のマクロパッドとキーボード用ファームウェアの組み合わせでもできる。技適を通した国内向けの製品を選べば法的な不安もない。CtrlVibeが持っているのは、AI作業向けに最初から並べられたキー配列と、液晶とダイヤルとマイクを1台にまとめた設計だ。そこに109ドルと1年近い待ち時間を払う価値があるかどうかで判断が分かれる。急がないなら、ソフトウェアが公開されて実物のレビューが出るまで待つのが妥当だと考える。
