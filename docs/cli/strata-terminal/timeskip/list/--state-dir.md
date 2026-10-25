# `--state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main`。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip list` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリのパスを表す文字列。省略可能。 |

## 役割

一覧表示の対象となる Time-skip 実行記録の保存ディレクトリを指定します。`list` はその場所にある各 `run.json` を読み、記録された実行を表示します。

## 使い方

```sh
strata timeskip list --state-dir ./time-skip-state
```

パスは `strata timeskip list` に対する指定です。同じ名前のオプションは `timeskip run`、`status`、`apply` にもそれぞれ定義されていますが、ここでは `list` の動作を説明します。コマンド階層と索引上の scope は [`docs/cli/README.md`](../../../README.md) を参照してください。

## 値と既定値

- parser は値を必須とする通常の文字列引数として受け取り、型変換や選択肢・範囲の validation は定義していません。オプションを指定して値を省くと `argparse` の引数エラーになります。値が `None`（未指定）または空文字列の場合、実行時にはこの指定を使わず次の既定値解決へ進みます。
- 優先順位は、空でない `--state-dir`、空でない `STRATA_TIMESKIP_DIR`、既定の `state_base() / "time-skip"` です。指定値は `Path(...)` に渡されます。`~` の展開や絶対パス化はこの処理では行われません。
- POSIX の `state_base()` は `$XDG_STATE_HOME/strata`（未設定または空なら `~/.local/state/strata`）、Windows は `%LOCALAPPDATA%\Strata`（未設定または空ならユーザープロファイル下の `AppData\Local\Strata`）です。

## 実行時の動作

`--state-dir` は `Path` に変換されて `TimeSkipStore` に渡され、list の読み取り root になります。store の初期化は `mkdir(parents=True, exist_ok=True)` を行うため、指定先がまだない場合は親ディレクトリを含めて作成します。その後の一覧処理は root 直下の項目を名前順に調べ、各項目の `run.json` が通常ファイルであれば UTF-8 JSON として読み込みます。成功した記録から `id`、`state`、`workspace`、`prompt`、開始・終了時刻、`decision` を抽出します。

`run.json` の読み取りで `OSError` または JSON decode error が起きた記録は一覧から黙って除外されます。list は記録ファイルを書き換えませんが、上記のとおり保存 root がなければディレクトリを作成します。

`--output` と併用できます。既定の `human` 出力では記録がない場合 `no Time-skip runs recorded` を表示し、ある場合は ID の先頭12文字、状態、decision outcome、prompt の先頭48文字を1行ずつ表示します。`--output json` では `runs` 配列を含む成功 JSON を出力します。

## 適用条件と副作用

このオプションは `list` の store root だけを選びます。`run`、`status`、`apply` の記録先には自動で伝播しません。それぞれのコマンドに個別の parser 引数があります。ディレクトリの作成や記録の読み取りには、指定パスへの filesystem 権限が必要です。

## 出力とエラー

- 既定の human 出力で記録がない場合も終了コードは `0` です。JSON 出力も `_success` 経由で終了コード `0` になります。
- 保存先の作成・列挙などで `OSError` が発生した場合、共通 CLI handler はファイルエラー文を出して終了コード `6` を返します。PermissionError は既知のユーザー領域に対するアクセスエラーとして1回の修復・再試行を試みる経路があります。
- 値なしなど parser エラーは `argparse` が処理し、終了コード `2` です。

## 根拠

- parser、値の既定値、`--output` の選択肢: `strata_cli/cli.py:376-378`
- `--state-dir`・環境変数・OS 別既定値の優先順位、store 初期化、list の出力: `strata_cli/cli.py:1476-1498`
- 保存 root の作成、`run.json` の列挙・読み取り・JSON decode error の扱い、抽出フィールド: `strata_control/time_skip.py:695-713`
- POSIX/Windows の state base と fallback: `strata_control/paths.py:13-21`
- 成功 JSON・human 出力および exit code: `strata_cli/cli.py:527-542`
- 共通 `ValueError` / `OSError` の失敗処理と終了コード: `strata_cli/cli.py:2166-2183`
- PermissionError の修復・再試行経路: `strata_cli/cli.py:2085-2104`
