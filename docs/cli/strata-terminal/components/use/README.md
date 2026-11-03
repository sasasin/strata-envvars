# `strata components use`（Strata Terminal CLI）

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/engine_library.py` |

## 役割

この PC にインストール済みの engine を選び、これからモデルを起動するときに使う engine を切り替えます。engine のダウンロードや削除はしません。`strata components engines` でインストール済み engine と使用中のものを確認してから実行できます（`strata_cli/update_cmd.py:82-87,358-378`）。

## 基本的な使い方

```sh
# インストール済み engine と使用状況を確認
strata components engines

# インストール済みの版を選択（同じ版が複数ある場合は --family か folder 名で特定）
strata components use 0.1.54

# DeepSeek engine の版を指定
strata components use 0.1.54 --family deepseek

# この PC で使える最新 engine を選択し、自動更新への追従に戻す
strata components use newest
```

`engine` には版番号、インストール先の folder 名、または `newest` を指定します。実装は `latest` も `newest` と同じ指定として受理します。Qwen と DeepSeek の両方に一致する engine がある場合は `--family qwen` または `--family deepseek` を付けるか、曖昧さのない folder 名を使ってください（`strata_control/engine_library.py:198-210`）。

## 実行モード

このコマンドは選択・切り替えを行う一回実行の管理コマンドです。engine の一覧表示は `strata components engines`、更新の実施は `strata update` が担当します。`strata components use` 自体は feed を読み込まず、既存 engine だけを対象にします（`strata_cli/update_cmd.py:84-87,272-283,378-394`）。

共通の `--components-dir` で engine component の格納先を指定できます。`--family` は同じ版の候補を絞り込み、`--backend` はこの PC 用候補の判定に使われます。`--wait` は使用中の engine が停止するまで待つ秒数です。さらに `--output`（`human` / `json` / `jsonl`）、alias の `--json`、`--quiet` を使えます（`strata_cli/update_cmd.py:47-56,85-87`、`strata_cli/cli.py:508-515`）。

## 主な動作と副作用

- 指定値からインストール済み候補を検索します。folder 名が版番号より先に照合され、一致なしは終了コード 2、複数候補への一致も folder 名を使うよう案内して終了コード 2 になります（`strata_control/engine_library.py:198-210`）。
- 対象 engine がこの PC で実行できるかを確認し、適合しない場合は切り替えず終了コード 5 になります。Qwen engine では署名とファイル全体を再検証してから切り替えます。DeepSeek engine では実行ファイルの test-start を確認します（`strata_cli/update_cmd.py:378-383`、`strata_control/engine_library.py:246-262,265-289`）。
- 選択を記録する状態ファイルを更新します。古い版を選ぶとその engine が pin され、次回以降の起動で使われます。`newest` を選ぶと、この PC で適合する最新候補を選択し、pin を外して更新への追従に戻します（`strata_control/engine_library.py:202-205,225-227`、`strata_control/updater.py:1303-1352`）。
- 切り替え後に開始するモデルが対象です。すでに稼働中のモデルはそのまま元の engine を使います。DeepSeek の切り替えでは関連するモデル設定の参照先も選択した engine に更新され、履歴が記録されます（`strata_control/engine_library.py:225-227,280-289`）。
- engine が稼働中の場合、対話端末では待機確認が表示されます。スクリプト・JSON 出力では対話せず、`--wait SECONDS` がなければ切り替えを拒否して終了コード 7 になります。Strata の `launch` が起動したモデルではこの確認を省略します（`strata_cli/update_cmd.py:403-418`、`strata_control/engine_library.py:216-239`）。

## 注意点

既に使用中の engine を指定した場合は成功扱いで「変更なし」と表示されます。ここでの `newest` は単純な最大版番号ではなく、この PC に適合する候補の中の最新です。適合条件や現在の使用先は `strata components engines` で事前に確認できます（`strata_control/engine_library.py:91-123,198-210`、`strata_cli/update_cmd.py:363-377,386-393`）。

## オプションの調査・文書

このコマンドの位置引数とオプションは [`docs/cli/README.md`](../../../README.md) の `strata components use` 節に一覧します。値や個別オプションの動作は同節からリンクされる文書を参照してください。

## 根拠

- `strata_cli/update_cmd.py:47-56,84-87` — 共通オプション、位置引数、`--family` とコマンド説明の parser 定義。
- `strata_cli/cli.py:508-515,2136-2138` — `--json` / `--quiet` の登録と `use` 実行処理への委譲。
- `strata_cli/update_cmd.py:358-394,403-418` — engine 候補選択、適合確認、使用中の engine に対する待機処理、出力。
- `strata_control/engine_library.py:91-123,198-210,225-289` — インストール済み候補・`newest` の判定、切り替え、Qwen / DeepSeek ごとの検証と状態更新。
- `strata_control/updater.py:1303-1352` — pin、active / previous 状態、切り替え履歴と preset 再確認マークの更新。
