# `strata components engines --model-config`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`。`argparse` の文字列引数。 |

## 役割

このコマンドでは `--model-config` は受理されますが、値はエンジン一覧の生成に使われません。`strata components engines` はインストール済みエンジンの一覧を読み取り専用で表示するコマンドであり、この option を省略した場合と指定した場合で一覧処理は変わりません。

## 使い方

```sh
# エンジン一覧を表示する。--model-config の値はこのコマンドでは使われない。
strata components engines --model-config /path/to/run-config.json
```

通常の一覧表示では option 自体を省略できます。

## 値と既定値

parser は `_common()` で `--model-config` を登録し、値の型変換や選択肢を指定せず、既定値を `None` にしています。そのため、指定時の値は文字列として受け取られます。パスの存在・JSON 形式・モデル設定としての妥当性は、このコマンドの一覧経路では検証されません。オプションを複数回指定した場合の独自処理もありません。

## 実行時の動作

共通の実行関数は `a.model_config` を `updater.Context.run_config` に渡します。しかし `components engines` の場合は、更新処理へ進む前に `_engines_command()` へ分岐します。同関数は `engine_library.list_engines(ctx)` の結果を人間向けまたは JSON 形式で出力し、`run_config` を読みません。従って、このコマンドでは値を指定してもモデル設定ファイルの読み込みやテスト起動は発生しません。

同じ共通 parser は `strata update` や `strata components update` にも使われます。それらの更新経路では `run_config` が更新後エンジンのテスト起動に使われますが、この動作は `strata components engines` には適用されません。

## 適用条件と副作用

`strata components engines` の処理でこの値が使われる条件は、確認できませんでした。`engine_library.list_engines()` はインストール済みパッケージを列挙し、稼働状態などを付加して返す読み取り処理です。`--model-config` によるファイル読み込み、ダウンロード、設定変更はありません。エンジンディレクトリや実行中プロセスの状態確認など、一覧表示自体の処理は行われます。

## 出力とエラー

この option 専用の出力・警告・エラー経路はありません。値は一覧表示で参照されないため、存在しないパスや JSON でないファイル名を渡した場合も、この値を理由とする検証エラーにはなりません（一覧処理そのものの環境依存エラーは別です）。一覧の通常出力は人間向けテキストで、`--output json` または `--output jsonl` を指定した場合は機械向け形式になります。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — `_common()` が `--model-config` を `default=None`、文字列値として登録。
- `terminal/strata_cli/update_cmd.py:303-321` — 共通実行関数が値を `Context.run_config` に格納。
- `terminal/strata_cli/update_cmd.py:337-338,445-465` — `engines` は `_engines_command()` に分岐し、`list_engines()` の結果を出力。
- `terminal/strata_control/engine_library.py:152-167` — `list_engines()` はパッケージを列挙し、読み取りのみを行う旨を定義。
- `terminal/strata_control/updater.py:421` — `Context.run_config` の用途をテスト起動用と定義。
- `terminal/strata_control/updater.py:1342-1358` — 更新のテスト起動経路では `run_config` を選択し、ファイルを読み込む。
