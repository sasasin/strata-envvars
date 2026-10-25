# `strata bench cancel --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。cancel サブコマンドの使用法と引数説明を表示する |

## 役割

`strata bench cancel` の構文を表示する argparse 標準のヘルプオプションです。トップレベルや他のサブコマンドのヘルプとは別スコープです。cancel は保存済み profile に属する実行中 benchmark への停止要求を扱い、このヘルプには必須の `--profile` と `--path`、および `--output` が表示されます（`strata_cli/cli.py:335-338`）。

## 使い方

```sh
strata bench cancel --help
```

短縮形は `strata bench cancel -h` です。ヘルプ表示では停止要求は行われません。argparse のパーサーは `ArgumentParser` と `add_parser` で構築され、`main` が引数を解析してからコマンド処理へ進みます（`strata_cli/cli.py:41-42, 335-338, 2217-2231`）。

## 値と既定値

`--help` 自体は値を取りません。Python `argparse` の標準 `-h` / `--help` action が各サブパーサーに有効で、表示後に通常の引数解析を終了します。Strata 独自の `help=` 文は cancel の説明を与えますが、ヘルプ action を個別登録してはいません（`strata_cli/cli.py:41-42, 335-338`）。

このコマンドの引数定義上、`--profile` と `--path` は必須、`--output` は `human` または `json` を受け取り、省略時は `human` です（`strata_cli/cli.py:336-338`）。`--help` を指定した呼び出しでは、これらの必須値がなくてもヘルプが先に表示されます。

## 実行時の動作

cancel パーサーのヘルプはコマンド専用の usage と説明を出します。通常の cancel 実行では `--path` が絶対パスであることを確認し、profile を読み込んでから、benchmarking 側に停止要求を委譲します（`strata_cli/cli.py:1175-1182`）。`--help` はこの処理分岐に到達しないため、benchmark の状態確認や `cancel.request` の作成をしません。

通常実行時の `--path` は絶対パス必須で、実行ディレクトリそのもの、または末尾名が `results.json` / `progress.json` のファイルパスを受け付けます。後者は親ディレクトリを対象にします。対象は owner-local の出力ディレクトリで、その profile に記録された lease が現在ロック中かつパス一致し、進捗が `running` の場合に限り停止 marker を作成します（`strata_cli/cli.py:1177-1180`; `strata_control/benchmarking.py:78-79, 105-135, 138-168`）。

## 適用条件と副作用

ヘルプは benchmark 実行状態や `--profile` / `--path` の実値に依存しません。ただし CLI の `main` は引数解析前に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセスの既定 owner / ACL を設定し、Windows 以外では何もしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-360, 372-385`）。

通常実行では `--profile` を `strata_control.profiles.load()` で読み込みます。profile ファイルの読み取りに伴い、管理者実行でロックされた Strata 管理ファイルのアクセス権を一度修復する場合があります（`strata_cli/cli.py:1179`; `strata_control/profiles.py:150-166`）。停止要求が受理されると、対象 run ディレクトリに排他的作成で `cancel.request` を作り、`1` を書き込んで同期します（`strata_control/benchmarking.py:149-163`）。

## 出力とエラー

`--help` は argparse が生成するヘルプを標準出力に表示し、通常のヘルプ終了（終了コード 0）となります。表示文字列は Python / argparse のバージョンや端末幅により整形が異なるため、ここでは固定文面を転記していません。

通常の cancel 実行で成功すると、`--output human` では「Cancellation requested; check the saved report for the final outcome.」を表示します。`--output json` では `schema_version`、`ok`、結果の `path` と `state` を含む JSON を出力します（`strata_cli/cli.py:535-542, 1180-1182`）。相対パスは終了コード 2 のエラーです。対象が active run でない場合、または既に最終 report が保存済みなら終了コード 6、ディレクトリの owner-only 条件や marker の形式に問題がある場合は終了コード 5 などの `ProfileError` になります。これらのエラーは通常 stderr、JSON 出力モードでは JSON エラーとして返ります（`strata_control/benchmarking.py:138-168`; `strata_cli/cli.py:2166-2173, 527-532`）。

## 根拠

- parser と対象コマンド階層: `strata_cli/cli.py:41-42, 290-292, 335-338`
- 引数解析、help がコマンド処理前に終了する構造: `strata_cli/cli.py:2217-2231`
- 通常の cancel 分岐、絶対パス検査、profile 読み込み、出力: `strata_cli/cli.py:1175-1182`
- profile 名・profile ファイル読み込み: `strata_control/profiles.py:25, 48-55, 150-166`
- lease による対象 run の特定: `strata_control/benchmarking.py:78-79, 105-135`
- 対象ディレクトリ検証、cancel marker、副作用、失敗条件: `strata_control/benchmarking.py:138-168`
- 成功・エラー出力と終了コード処理: `strata_cli/cli.py:527-542, 2166-2173`
- 引数解析前の Windows user defaults 処理: `strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`

調査範囲は指定 commit のソースコードです。同一 revision の実行可能 CLI による help 出力や Release 配布物との照合は行っていません。help の action と終了動作は標準 `argparse` の挙動に基づき、Strata 固有の parser 定義と照合しています。
