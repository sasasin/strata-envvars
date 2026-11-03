# `strata components engines`（Strata Terminal CLI）

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/update_cmd.py`、`strata_control/engine_library.py` |

## 役割

この PC の component directory に導入済みの推論 engine を、family ごとに一覧表示します。版、backend / variant、容量、現在の選択状態、この PC で実行できるかを確認できます。engine の取得、切り替え、削除は行いません。

このコマンドは `strata components` の `engines` サブコマンドとして登録され、`strata_cli/update_cmd.py` の一覧処理へ振り分けられます。位置引数はありません。`engines` 自体のほか、共通 parser option として `--backend`、`--components-dir`、`--feed`、`--force`、`--model-config`、`--output`、`--wait` が登録され、CLI 側で `--json` と `--quiet` も追加されます。実際の一覧処理が参照するのは component directory、backend、output です。`--feed`、`--force`、`--model-config`、`--wait`、`--quiet` はこの一覧経路では読み取り処理に使われません。個々の option は[索引](../../../../README.md)を参照してください。

## 基本的な使い方

```sh
# 導入済み engine を人向けの形式で一覧表示
strata components engines

# JSON 形式で一覧表示
strata components engines --output json

# CUDA backend を指定した環境として互換性・選択状態を確認
strata components engines --backend cuda
```

`--components-dir DIR` を指定すると一覧の対象ディレクトリを変更できます。指定しない場合は `STRATA_COMPONENTS_DIR` があればその値、なければ OS ごとのユーザー領域（通常は `$XDG_DATA_HOME/strata/components`、未設定なら `~/.local/share/strata/components`。Windows は `LOCALAPPDATA` 配下）が使われます。

## 実行モード

このコマンドには対話・起動・更新モードはありません。一度のローカル照会を行い、人向け出力または機械向け出力を返します。`--output` は `human`（既定）、`json`、`jsonl` を受け付け、`--json` は `--output json` の alias です。JSON 系の出力は `schema_version: 1`、`ok: true` と一覧データを含む単一 JSON オブジェクトです（`jsonl` もこの一覧処理では単一イベントの逐次配信ではありません）。

## 主な動作

- Qwen 系 engine component を走査し、DeepSeek engine が見つかった場合はその導入先も一覧に加えます。Qwen family は導入済み項目がなくても一覧に残ります。各 family 内は version と folder 名の降順です。
- OS、指定 backend、Strata runtime 要件、GPU architecture、NVIDIA driver 要件、component file の検証結果を使って実行可否を表示します。Qwen 系では選択中の engine、実行可能な中での newest も示します。DeepSeek 系は保存済み選択状態などを使って使用中の engine を判定します。
- package の容量を集計し、稼働中プロセスが engine を使っているかも確認します。人向け表示では「in use」「newest」「not for this computer」と理由を表示し、最後に `use` / `remove` の案内を出します。
- 実装上は component files・選択状態の読み取りと process 使用状況の照会だけを行います。ファイルの変更、engine のダウンロード、engine の起動は行いません。

## 関連状態・他の実行経路

一覧と engine の切り替え・削除はアプリの Settings > Engine と `strata components use` / `strata components remove` で同じ `strata_control/engine_library.py` の状態を使います。切り替えは[use の概要](../use/README.md)、削除は[remove の概要](../remove/README.md)、更新は[`strata components update`](../update/README.md)を参照してください。`strata components use newest` は選択を自動更新追従へ戻す操作ですが、一覧コマンド自身は状態を変更しません。

## オプションの調査・文書

このコマンドの option 一覧は [`docs/cli/README.md`](../../../../README.md) の `strata components engines` 節にあります。共通 option の名前だけがこの概要にも現れますが、値と個々の挙動は索引から各 option 文書を参照してください。

## 調査範囲と制約

backend の自動検出や実行可否はホスト環境、導入済み package、driver/runtime の状態に依存します。この文書では実機ごとの検出結果や全 platform/backend の実行可否は確認していません。配布済み Release binary ではなく、記載した commit の parser とソース実装を根拠にしています。

## 根拠

- `strata_cli/update_cmd.py:47-57,82-83` — 共通 option と `engines` parser の登録。
- `strata_cli/cli.py:508-515,2136-2138` — `--json` / `--quiet` の後付け、および `engines` を `update_cmd.run()` に渡す分岐。
- `strata_cli/update_cmd.py:233-255,358-377` — component directory と backend の context 作成、人向け・JSON 出力、一覧表示。
- `strata_control/engine_component.py:176-186` — component directory の既定値と `STRATA_COMPONENTS_DIR` の優先。
- `strata_control/engine_library.py:59-80,91-123` — Qwen package の互換性判定と一覧項目。
- `strata_control/engine_library.py:167-195` — 稼働状況・削除可否、family ごとの一覧、容量集計と read-only の説明。
- `strata_control/engine_library.py:198-211` — 後続の `use` / `remove` で使う version・folder・`newest` の解決と曖昧・未導入時の失敗経路。
