# `strata tune auto --serve-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--serve-dir` |
| 別名 | なし |
| 値 | `serve/` ディレクトリを含むフォルダーのパス（文字列） |

## 役割

自動チューニングが設定候補を測定するときに起動する worker の作業ディレクトリを指定します。worker は `python -m serve.server` として起動されるため、指定先には `serve/` パッケージが必要です。通常は Strata の Terminal CLI インストール先が使われます（`terminal/strata_cli/tune_commands.py:179-182, 371-376`、`terminal/strata_control/tune_session.py:563-569`）。

## 使い方

```sh
# 通常のインストール先ではなく、serve/ を含む checkout を使って測定する
strata tune auto my-model --serve-dir /path/to/Strata/terminal
```

## 値と既定値

値は文字列として受け取り、パスの存在・ディレクトリ種別や `serve/` の有無を事前検証しません。値が省略された場合、または空文字列の場合は、`strata_cli/tune_commands.py` の配置から求めた Terminal CLI インストール先（`Path(__file__).resolve().parent.parent`）を使います。指定値は `Path` に変換されますが、`expanduser()` や絶対パス化は行われません（`terminal/strata_cli/tune_commands.py:46, 179-182`）。

## 実行時の動作

`strata tune auto` の測定経路では、選ばれたパスが `WorkerSession` の `serve_dir` に渡され、各測定 worker の起動時に `cwd` として使われます。worker は `python -m serve.server --engine strata --config … --host 127.0.0.1 --port …` で起動し、測定用設定・engine log・worker log は `--work-dir` の下に作られます。`--work-dir` を省略した場合は一時ディレクトリが使われ、プロセス終了時に削除されます（`terminal/strata_cli/tune_commands.py:371-376`、`terminal/strata_control/tune_session.py:493-495, 547-569`）。

`--plan` を付けた場合は計画を表示して `WorkerSession` を作らず終了するため、このパスは worker 起動には使われません（`terminal/strata_cli/tune_commands.py:349-353, 371-376`）。

## 適用条件と副作用

指定先は worker のプロセス起動にだけ適用されます。別プロセスが使う相対パスはそのまま `cwd` に渡され、空でない指定値が不正な場合の独自 fallback はありません。パスが存在しないなど `cwd` を使った起動が失敗すると `OSError` が `StartFailed("FAIL_BOOT", …)` に変換され、チューナーは測定結果を `base_failed` として扱います。その場合、preset は保存されず、通常のコマンド終了コードは `6` です（`terminal/strata_control/tune_session.py:566-572`、`terminal/strata_control/autotune.py:338-354, 421-425`、`terminal/strata_cli/tune_commands.py:408-425`）。

## 出力とエラー

worker を起動できない場合、失敗理由は測定結果に入り、人間向け出力では `Your current settings could not be measured: …` の形式で表示されます。JSON 出力では結果オブジェクトに含まれます。個別の parser validation error はありません（`terminal/strata_control/autotune.py:421-425`、`terminal/strata_cli/tune_commands.py:445-467`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` parser。`--serve-dir` は値を取る文字列引数で、既定値は `None`。
- `terminal/strata_cli/tune_commands.py:179-182` — 指定値またはインストール先の選択。
- `terminal/strata_cli/tune_commands.py:309-353, 371-376` — target の読み込み後、計画表示を除く測定経路で worker session にパスを渡す。
- `terminal/strata_control/tune_session.py:547-572, 563-569` — 測定ファイルの作成、worker 起動コマンド、`cwd`、起動時 `OSError` の変換。
- `terminal/strata_control/autotune.py:338-354, 421-425` と `terminal/strata_cli/tune_commands.py:408-425, 445-467` — 起動失敗後の結果・終了コード・表示。
- `terminal/strata_cli/tune_commands.py:88-96` — 同じ文字列の `--serve-dir` は別スコープの `strata presets recheck` parser にもある。本書は索引で指定された `strata tune auto` の定義だけを扱う。
