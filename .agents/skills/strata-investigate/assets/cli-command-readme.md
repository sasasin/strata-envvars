# `<tool> <command>`（<ツール側の呼び出し名・プラットフォーム>）

調査対象: Strata commit `<完全な commit SHA>`（`YYYY-MM-DD` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `<tool-id>` |
| コマンド | `<strata launch>` |
| POSIX の入口 | `<bin/strata>` |
| Windows の入口 | `<bin\strata.cmd / strata.ps1>` |
| 主な実装 | `<strata_cli/launch/cmd.py>` |

## 役割

このコマンドがまとめてやること（入口から完了まで）。どの利用者が何のために使うか。

## 基本的な使い方

対話式で使う例、フラグで設定を渡す例、dry-run / 計画表示など安全な確認例を comment 付きで並べる。
実際に変更する例と変更しない例を混同しない。

## 実行モード

付けない場合の既定の振る舞いと、モードを分けるオプション・環境変数・条件。
同じコマンド名でも実行先が変わる場合（wrapper とネイティブ実行ファイルなど）はここで区別する。

## 主な動作

起動から完了までに起きる処理の順（ファイル準備、engine 取得、server 起動、監視、状態ファイル、ログの置き場所）。
副作用（ファイル書き換え、既存設定の上書き、ポート使用）を明示する。

## 関連状態・他の実行経路

同じ設定を共有する別経路（アプリの profiles、presets、config ファイル、既に動いている server）との関係。

## オプションの調査・文書

このコマンド節の option 一覧は索引（`docs/cli/README.md`）にある。個別 option の値と効果は
`<command-path>/--option.md` に書き、ここには複製しない。

## 根拠

parser 登録箇所、実行処理、配布 wrapper などの `path:line`。Release への同梱実績を書く場合は取得日で示す。

<!--
基準文書: docs/cli/strata-terminal/launch/README.md（详しさはこの文書に合わせる）。
コマンド概要は docs/cli/<tool-id>/<command-path>/README.md に置き、索引の各節の先頭リンクにする。
-->
