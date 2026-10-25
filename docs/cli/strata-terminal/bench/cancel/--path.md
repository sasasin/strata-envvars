# `--path`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| オプション | `--path` |
| 別名 | なし |
| 値 | 必須のパス文字列。絶対パスで指定する |

## 役割

`--profile` で指定する保存済み profile のもとで実行中のベンチマークを特定し、その実行にキャンセル要求を記録します。対象は同じ profile の「現在アクティブな実行」と出力ディレクトリが一致する場合だけです。エンジンやベンチマークプロセスを直接終了する指定ではありません。

## 使い方

```sh
strata bench cancel --profile my-profile --path /absolute/path/to/run
```

`--path` には実行出力ディレクトリ、またはその中の `results.json` を指定します。実装上は `progress.json` を指定した場合も同じディレクトリとして扱います。パスは相対パスではなく絶対パスにしてください。

## 値と既定値

値は必須で、省略時に使われる既定値はありません。`argparse` による型変換や存在確認は parser では行われず、コマンド処理で `Path` に変換して絶対パスかを検査します。`--path` の重複指定時の独自処理はありません（通常の `argparse` の単一値引数として最後に指定した値が使われます）。相対パスはキャンセル処理へ進まず、終了コード `2` で拒否されます。

## 実行時の動作

1. CLI は絶対パスを確認し、`--profile` の保存済み profile を読み込みます。profile が存在しない、または不正な場合はキャンセル処理に進みません。
2. `results.json` または `progress.json` を指定した場合は親ディレクトリを対象にします。それ以外は指定パス自体を出力ディレクトリとして扱います。
3. 出力ディレクトリがディレクトリであることを確認します。POSIX では owner-only の権限も要求します。さらに、指定 profile の lease が記録する実行パスと一致して実行中であり、`progress.json` の状態が `running` であることを確認します。
4. 対象ディレクトリに `cancel.request` を排他的に作成し、1 byte の要求を記録して同期します。既に有効な marker があれば再利用します。応答の `state` は runner が最終記録を作る前なら `cancel_requested`、進行状況が既に `cancelled` なら `cancelled` です。

ベンチマーク側は marker を約 0.1 秒間隔で監視し、検出すると自身が追跡している HTTP 応答 socket を shutdown して処理を中断します。その後 runner が結果レポートと進行状況を保存します。そのため、成功応答は要求が記録されたことを示し、サーバーや runner が停止済みであることを保証しません。最終結果は保存レポートで確認してください。

## 適用条件と副作用

- `--profile` は保存済み profile 名である必要があります。実行中であっても、異なる profile または異なる出力先の run は対象になりません。
- ディレクトリが owner-only でない（POSIX）、run がアクティブでない、または最終レポートが既に保存されている場合は拒否されます。
- ファイルシステムに `cancel.request` を作成します。既存 marker が不正な形式・権限・リンク数なら拒否します。run の report 自体をこのオプションが直接書き換えることはなく、runner が後続処理で保存します。
- `--output json` を指定すると応答を JSON にできます。既定の `human` 出力では成功時にキャンセル要求を受け付けた旨を表示します。

## 出力とエラー

相対パスは `strata: benchmark cancel path must be absolute` を stderr に出し、終了コード `2` で返ります。既定の成功表示は `Cancellation requested; check the saved report for the final outcome.` です。JSON 出力では成功 payload に `ok`、`path`、`state` が含まれます。

保存済み profile の読込エラーや、ディレクトリ・進行状況・marker の検査エラーは CLI のエラー経路で返ります。対象 run がアクティブでない、または既に最終レポートがある場合は `6`、権限・形式等の検査失敗は `5` が使われます。OS のファイル操作エラーも CLI で捕捉され、ローカルファイル操作エラーとして終了コード `6` になります。`--output json` の場合はエラーも JSON 形式です。

## 根拠

- `strata_cli/cli.py:335-338` — `strata bench cancel` の parser。`--path` は必須で、help 上の値は絶対 run directory または `results.json`。出力形式は `human` / `json`、既定は `human`。
- `strata_cli/cli.py:1129-1131,1175-1182` — `Path` への変換、絶対パス検査、profile 読込、cancel helper 呼び出し、成功表示。
- `strata_cli/cli.py:527-542,2166-2188` — 人間向け stderr / JSON 応答と、例外から終了コードへの変換。
- `strata_control/benchmarking.py:138-168` — 対象ディレクトリの決定、owner-only / lease / progress 検査、marker 作成、戻り値と拒否条件。
- `strata_cli/bench.py:695-741` — progress ファイルの読み込みと state / report 整合性検査。
- `strata_cli/bench.py:57-82,108-115` — runner 側の marker 監視、追跡 socket の shutdown。
- `strata_cli/bench.py:843-888` — cancel 状態の判定、`results.json` と最終 progress の保存。
- `docs/MANAGEMENT_PROTOCOL.md:22` — 同じ `bench.cancel` 機能について、正確な active run の停止要求であり engine 停止を保証しない旨の説明。

調査範囲は上記 commit の checkout 内の parser、CLI 分岐、benchmarking helper と runner、およびローカル管理プロトコル文書です。同一 revision の CLI `--help` や Release 配布物は実行・照合していません。
