# `strata ops result`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/journal.py` |

## 役割

指定した profile に保存されている operation journal から、1件の操作記録を読み出して表示します。recipe の実行結果だけでなく、直接実行された対象操作の記録も journal の形式が有効なら取得できます。結果の検索や操作の再実行は行いません。

## 基本的な使い方

```sh
# 指定した profile の操作記録を表示
strata ops result 0123456789abcdef0123456789abcdef --profile work

# 機械処理向け JSON で表示（--json は --output json の alias）
strata ops result 0123456789abcdef0123456789abcdef --profile work --json
```

`operation_id` は必須の位置引数です。profile は `--profile` で必ず指定します。operation ID の確認には [`strata ops runs`](../runs/README.md) と [`strata ops run`](../run/README.md) の結果を利用できます。

## 実行モードと出力

| 指定 | 動作 |
| --- | --- |
| 既定（`--output human`） | 記録全体を整形 JSON として標準出力へ表示します。専用の人間向け要約はありません。 |
| `--output json` または `--json` | `{"schema_version":1,"ok":true,"record":...}` 形式の JSON を標準出力へ表示します。 |
| `--quiet` | 既定の人間向け出力を抑制します。JSON 出力は quiet 処理を通らず表示されます。 |

`journal.load` は `state` が `running` の記録を返す際に `completion_unverified: true` を付加します。これは呼び出し元の中断後に完了が確認できないことを示すもので、worker が現在も実行中である証拠ではありません。

## 主な動作と注意点

- operation ID は小文字の16進数32文字で検証され、`<profile の ops 保存先>/.runs/<operation_id>.json` の記録を1件読みます。保存先のルートは OS ごとの profile directory 配下です。
- 読み込んだ記録はサイズ、通常ファイルであること、POSIX での所有者専用アクセス、schema・profile・ID・状態・イベント・結果フィールドなどの整合性が検証されます。上限は64 KiBです。
- このコマンドは記録の読み出しだけを行います。ファイルがない、不正な形式、profile と記録の不一致、権限・ファイル種別の問題などは失敗になります。通常の human 出力ではエラーを標準エラーへ表示し、JSON 出力では JSON のエラーオブジェクトを出します。
- 調査は指定 commit のソースに基づきます。別 OS 上の実行や Release 配布物の挙動はこの checkout からは確認していません。

## 関連文書

- [`strata ops` の索引と他の操作コマンド](../../../README.md#strata-terminal)
- [`strata ops runs`](../runs/README.md) — 操作記録の一覧
- [`strata ops run`](../run/README.md) — recipe の実行と operation ID の出力
- [`strata ops`](../README.md) — `ops` コマンド群の概要

## 根拠

- Strata `strata_cli/cli.py:255-267` — `ops` と `result` parser、必須の `operation_id`・`--profile`・出力形式。
- Strata `strata_cli/cli.py:508-515,2232-2237` — one-shot parser 群への `--json` / `--quiet` 追加と `--json` の `--output json` への正規化。
- Strata `strata_cli/cli.py:1391-1411,2160-2162` — `ops result` dispatch、`journal.load` 呼び出し、標準出力への成功結果出力。
- Strata `strata_cli/cli.py:2166-2193` — `ValueError` / `OSError` 等の CLI エラー表示と終了コードの処理。
- Strata `strata_control/journal.py:47-63,185-244` — profile 配下の `.runs` 保存先、32桁 ID、記録ファイル・内容の検証。
- Strata `strata_control/journal.py:247-251` — 記録読み込みと実行中記録への `completion_unverified` 付与。

同一 revision の CLI help は補助実行せず、parser と処理本体を根拠にしました。
