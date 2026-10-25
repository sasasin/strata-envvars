# `strata drafting`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting` |
| 主な実装 | `strata_cli/drafting_cmd.py`、`strata_control/drafting.py`、`strata_control/drafting_fetch.py` |

## 役割

DFlash2 drafter の取得計画を表示するか、ファイルをダウンロードして Strata engine 用 pack に変換します。サブコマンド `plan` は確認のみ、`fetch` は明示的な取得操作です。モデル起動の通常経路では自動取得せず、このコマンドを明示して実行した場合にネットワークへ接続します（`strata_control/drafting_fetch.py:3-8`）。

## 基本的な使い方

```sh
# 既定のデータフォルダーについて取得計画を表示
strata drafting plan

# モデルの run config を考慮した計画を JSON で表示
strata drafting plan --config /path/to/run-config.json --output json

# drafter を取得して pack にする
strata drafting fetch

# 選択したモデルが必要とし、まだ存在しない場合だけ取得
strata drafting fetch --config /path/to/run-config.json --if-needed --output jsonl
```

`--data-dir` はモデルデータの保存先を指定します。省略すると、設定ファイル内の engine 引数からデータフォルダーを判定し、見つからなければ Strata が使う既定フォルダーを使います。`--config` が読めない場合も空の設定として処理されます（`strata_cli/drafting_cmd.py:40-54`）。

## 実行モード

| サブコマンド | 動作 |
| --- | --- |
| `plan` | 既存 pack の有無、必要な場合の取得量、選択される drafter の判断を表示します。ファイルの変更やダウンロードは行いません。 |
| `fetch` | DFlash2 の固定 revision のファイルを取得し、SHA-256 を確認して engine 用 pack に変換します。正常に pack を作成した後、取得元ファイルを削除します。 |

`fetch --if-needed` は、選択が DFlash2 を使い、対応モデルで、engine が serve 時に DFlash2 を提供し、pack がまだない場合にだけ取得します。それ以外は成功扱いで「Nothing to download.」または JSON の `skipped: true` を出して終了します（`strata_cli/drafting_cmd.py:57-79`; `strata_control/drafting.py:162-183`）。

## 主な動作と副作用

- `--mode` は `auto`、`mtp`、`dflash2`、`off` のいずれかです。省略時は run config の `drafting` 設定を使い、それもなければ `auto` として判定します。`--family` は config にモデル情報がない場合などに対象 family を指定します（`strata_cli/drafting_cmd.py:23-29,40-54`; `strata_control/drafting.py:23-25,136-138`）。
- 現行実装では `ENGINE_SERVES_DFLASH2 = False` です。このため serve 用の選択判定では DFlash2 は必要扱いにならず、`--if-needed` は取得を省略します。`plan` は `needed`、選択判断、pack の状態を返します（`strata_control/drafting.py:141-146,162-183`; `strata_cli/drafting_cmd.py:62-78`）。
- `fetch` は `--if-needed` がない限り選択状態にかかわらず `ensure()` を呼びます。取得先はデータフォルダー内の `dflash2/qwen3.8-flash-next-dflash2.q8.pack` です。配布元ファイルを検証してから一時ファイルに pack を作り、置き換えで完成 pack にします（`strata_cli/drafting_cmd.py:74-89`; `strata_control/drafting.py:88-100`; `strata_control/drafting_fetch.py:54-101`）。
- 取得は約 1.2 GB の safetensors ファイルを対象とし、engine 用 pack は約 0.76 GB です。既に pack が準備済みなら保持して取得を行いません（`strata_control/drafting.py:84-100,114-122`; `strata_control/drafting_fetch.py:29-39,54-62`）。
- `--output human` が既定です。`json` は結果を JSON オブジェクトとして、`jsonl` は取得中の進捗イベントと最終結果を JSON Lines として標準出力へ出します（`strata_cli/drafting_cmd.py:29,57-73,81-98`）。

## 注意点と失敗

取得にはネットワーク接続が必要です。SHA-256 が一致しないファイルは削除対象となり、取得の中断は再開可能な `.part` ファイルを使います。取得失敗や pack 作成失敗では human 出力を標準エラーに出し、終了コード `5` を返します。machine 出力では `ok: false` と `drafting_failed` を返します（`strata_control/drafting_fetch.py:72-94`; `strata_cli/drafting_cmd.py:87-98`）。

`--mode` の不正値や必須のサブコマンドがない呼び出しは parser に拒否されます。無効値の具体的な usage 表示文言や終了コードは、このコマンド固有コードでは指定されておらず、本調査では実行して確認していません（`strata_cli/drafting_cmd.py:17-29`）。

## 関連文書

- [`strata drafting plan`](plan/README.md) — 取得計画サブコマンドの概要。
- [`strata drafting fetch`](fetch/README.md) — 取得・pack 作成サブコマンドの概要。
- [CLI オプション索引](../../README.md) — このコマンドと各オプション文書へのリンク。

## 根拠

- `strata_cli/cli.py:172-173,2144-2146` — トップレベル parser への登録と実行時委譲。
- `strata_cli/drafting_cmd.py:17-29` — サブコマンドとオプションの parser 定義。
- `strata_cli/drafting_cmd.py:40-54,57-98` — 入力設定の決定、plan/fetch 実行、出力・失敗処理。
- `strata_control/drafting.py:23-25,67-79,88-100,114-122,136-183` — 選択肢、カード分類、pack 状態、DFlash2 適用条件。
- `strata_control/drafting_fetch.py:29-39,54-101` — 計画表示、取得・検証・pack 作成・一時ファイル処理。
