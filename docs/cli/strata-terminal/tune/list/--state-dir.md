# `--state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune list` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリのパス（文字列）。型・存在・絶対パスの検証は parser では行わない |

## 役割

調査対象とする tuning job の保存ルートを指定します。`list` はその直下にある各子ディレクトリの `job.json` を読み、job ID、状態、backend、objective を列挙します。既定の tuning 保存先とは別の場所に保存した job を確認するときに使えます。

## 使い方

```sh
strata tune list --state-dir ./tuning-state
```

JSON で取得する例:

```sh
strata tune list --state-dir ./tuning-state --output json
```

## 値と既定値

- parser は値を文字列として受け取り、既定値は `None` です。専用の型変換、選択肢、空でないことやディレクトリであることの検証はありません（`strata_cli/cli.py:482-484`）。
- 実行時に値が truthy なら `Path(a.state_dir)` を使います。したがって相対パスはプロセスの作業ディレクトリ基準で解釈されます。空文字列は未指定と同様に扱われ、後述の環境変数または既定値へ進みます（`strata_cli/cli.py:1643-1650`）。
- 同一オプションを複数回指定した場合の値の上書き規則は、この parser で個別には設定されていません。argparse の通常の単一値引数として最後に指定した値が残ります（`strata_cli/cli.py:482-483`）。

## 実行時の動作

保存先は次の優先順で決まります。

1. 空でない `--state-dir` の値
2. 環境変数 `STRATA_TUNE_DIR` の値（空文字列は未設定扱い）
3. `state_base() / "tuning"`

`state_base()` は POSIX では `${XDG_STATE_HOME:-~/.local/state}/strata`、Windows では `${LOCALAPPDATA:-~/AppData/Local}/Strata` を返します。このため最後の既定値は POSIX で `${XDG_STATE_HOME:-~/.local/state}/strata/tuning`、Windows で `${LOCALAPPDATA:-~/AppData/Local}/Strata/tuning` です（`strata_cli/cli.py:1643-1650`、`strata_control/paths.py:13-21`）。`STRATA_TUNE_DIR` の追加説明は [`STRATA_TUNE_DIR.md`](../../../../STRATA_TUNE_DIR.md) を参照してください。同文書は別の Strata revision（`011c9e600a93bbc9fd451c563501b5831c32bbca`）を対象としており、ここではリンク案内としてのみ記載しています。

選択したルートがディレクトリの場合だけ、その直下の項目をソート順で走査します。各項目を job ディレクトリとして扱い、その中に通常ファイル `job.json` があれば UTF-8 で読み込みます。出力レコードには JSON の `id` と `state`、`plan.backend` と `plan.objective` を含めます。サブディレクトリ以下を再帰検索したり、ディレクトリ名から ID を補ったりはしません（`strata_cli/cli.py:1655-1668`）。

## 適用条件と副作用

- `--state-dir` は `strata tune list` の parser に属します。同じオプション名は `tune run`、`apply`、`rollback`、`status` にも個別に定義されていますが、各コマンドの処理を共有する指定ではありません（`strata_cli/cli.py:458-484`）。
- このコマンドは保存先を読み取って表示するだけで、ディレクトリや job ファイルを作成・変更・削除しません。保存先が存在しない、またはディレクトリでない場合は走査せず、job が空の結果になります（`strata_cli/cli.py:1655-1673`）。
- `job.json` の読み込みで `OSError` または JSON/Unicode の値エラーが起きたファイルは黙ってスキップされます。JSON として読めてもトップレベルや `plan` の型が想定と異なる場合の schema validation はなく、`.get()` による未処理例外になる可能性があります（`strata_cli/cli.py:1661-1668`）。

## 出力とエラー

- 既定の human 出力は job がなければ stdout に `no tuning jobs recorded` を出して終了コード `0` を返します。job があれば ID の先頭 12 文字、state、backend、objective を1行ずつ stdout に出し、終了コード `0` を返します（`strata_cli/cli.py:1669-1676`）。
- `--output json` では stdout に schema version 1 の成功オブジェクト `{"schema_version":1,"ok":true,"jobs":[...]}` を出します。空の場合も成功オブジェクトを返します（`strata_cli/cli.py:1641`, `1669-1670`; `_success` の形式は `strata_cli/cli.py:535-538`）。
- ディレクトリ走査などで `OSError` が読み込みループの個別ファイル処理外から発生すると、共通処理が stderr にエラーを出し、終了コード `6` を返します。JSON 出力時は同じ失敗を JSON エラーとして出します（`strata_cli/cli.py:2119-2120`, `2176-2183`）。未知の引数は parser が usage とエラーを stderr に出し、終了コード `2` で終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser 定義と既定値: `strata_cli/cli.py:482-484`
- state directory の優先順位: `strata_cli/cli.py:1643-1650`
- POSIX / Windows のユーザー状態ルート: `strata_control/paths.py:13-21`
- `job.json` の走査・フィールド抽出・人間向け出力: `strata_cli/cli.py:1655-1676`
- JSON 成功出力: `strata_cli/cli.py:1669-1670`, `535-538`
- 共通の I/O 例外と parser 失敗処理: `strata_cli/cli.py:2176-2183`, `2223-2231`

## 調査範囲

同一 commit の Terminal CLI parser と実行経路、および `state_base()` の実装を確認しました。別環境の既存 CLI や Release artifact は実行・照合していません。環境変数文書はリンク先に示した別 revision が対象のため、この文書の挙動根拠には使用していません。
