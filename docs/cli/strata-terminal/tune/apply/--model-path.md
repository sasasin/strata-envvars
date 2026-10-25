# `--model-path`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--model-path` |
| 別名 | なし |
| 値 | モデルファイルのパス（`argparse` の文字列。拡張子・存在確認は parser では検証しない） |

## 役割

apply 対象の tuning job が測定したモデルと、現在指定したモデルファイルの内容 identity を照合します。ファイル名ではなく digest を使い、測定時と異なるモデルに推奨設定を適用することを防ぐ用途です。

## 使い方

```sh
strata tune apply <job-id> --model-path ./models/model.gguf
```

このオプションは apply 時に照合するモデルを指定します。測定 job を作った `strata tune run` にも同じモデルファイルを `--model-path` で渡し、同一のファイルを apply 時にも指定してください。例は現在の作業ディレクトリからの相対パスです。

## 値と既定値

- 値は必須の文字列で、既定値は `None`（未指定）です。短縮 alias はありません。parser に `type`、`choices`、独自 validator はなく、形式や拡張子の検査は後段のファイル identity 計算で行われます（`strata_cli/cli.py:461-470`）。
- 同じオプションを複数回指定した場合は通常の `argparse` の `store` 動作で最後の値が残ります。空文字列は parser では受理されますが、利用側の truthiness 判定では未指定と同じ扱いになります（`strata_cli/cli.py:1868-1875`）。
- 相対パスはプロセスの現在ディレクトリ基準です。apply は `Path(a.model_path)` をそのまま identity 関数に渡し、`~` の展開や絶対パス化はしていません（`strata_cli/cli.py:1871-1875`）。

## 実行時の動作

apply は job の保存済み plan から engine、backend、context を取り出し、指定パスのファイル identity と workload を組み合わせた comparison key を作ります。model の比較には digest、byte 数、digest 方式が含まれます（`strata_cli/cli.py:1868-1879`; `strata_control/tune_history.py:99-118`）。

通常はサンプル方式の SHA-256 を計算します。12 MiB 以下のファイルでは全体を読み、より大きいファイルではサイズと先頭・中央・末尾の各 4 MiB を hash します（`strata_control/tune_history.py:39-45,48-81`）。測定時の identity と比較して、model digest や digest 方式を含む engine・backend・workload・context・machine 情報に差があれば適用を拒否します（`strata_control/tune_history.py:121-143`; `strata_control/tune_apply.py:272-283`）。

測定時に `strata tune run --full-digests` を使った場合は full SHA-256 が保存されますが、apply parser に同モードの指定はなく、apply 側の identity 計算は既定の sampled digest です。そのため同じファイルを指定しても digest/method が一致せず、identity 不一致として拒否される場合があります（`strata_cli/cli.py:453-455,1868-1879`; `strata_control/tuning.py:753-761`; `strata_control/tune_history.py:60-80,132-135`）。

job の report に model digest がない場合、apply はこのオプションの有無にかかわらず終了コード 2 で拒否します。したがって測定時にも `--model-path` が必要です。job に identity があり、このオプションを省略した場合、apply 側は digest のない model identity を照合に使うため、記録済み digest と一致せず拒否されます（`strata_cli/cli.py:1883-1898`）。

## 適用条件と副作用

- 指定ファイルが存在しない場合、`file_identity` は digest を返さず、CLI は `no model file at ...` を stderr（human 出力）または JSON エラーとして出し、終了コード 2 を返します（`strata_control/tune_history.py:56-58`; `strata_cli/cli.py:1893-1894,527-532`）。読み取り不能やディレクトリ指定など identity の再計算中に例外が起きた場合は identity を `None` とし、再計算不能として終了コード 2 で拒否します（`strata_cli/cli.py:1870-1881,1895-1898`）。
- identity が一致しても、job が完了していない、推奨がない、測定中に大きな drift があった、設定に差分がない等の場合は apply を拒否します（`strata_control/tune_apply.py:240-267`）。
- 適用成功時は推奨 flag を run configuration の `args` に反映し、以前の設定を application record に保存してから設定ファイルを atomic replace します。`--model-path` 自体は設定へ書き込まれません（`strata_control/tune_apply.py:118-166,343-370`）。
- CLI は `apply_recommendation(..., verify=None)` を呼ぶため、候補設定でモデルを起動して token 生成を確認する処理は行われません。human 出力にも実機検証されていない旨が表示されます。設定変更前に候補の実行を検証する機能は、この CLI 経路では提供されていません（`strata_cli/cli.py:1900-1905,1918-1920`; `strata_control/tune_apply.py:306-337`）。

## 出力とエラー

- 成功時、human 出力は変更先、追加・削除 flag、設定の変更前後 SHA-256 の先頭 16 文字、rollback 用 application ID を表示します。`--output json` では成功 payload を JSON で出力します（`strata_cli/cli.py:1907-1916,535-542`）。
- job が見つからない、設定ファイルがない、model identity を再計算できない、または測定済み identity と異なる場合は終了コード 2 または `ApplyError` の code で失敗します。human エラーは stderr、JSON モードは標準出力の error object です（`strata_cli/cli.py:1859-1866,1883-1905,527-532`; `strata_control/tune_apply.py:50-55,319-320`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:461-470`。索引上の配置は `strata-envvars` 側 `docs/cli/README.md:769-778`。
- apply handler の identity 再計算、必須 digest 判定、エラー経路: `strata_cli/cli.py:1850-1905`。
- digest の方式と比較項目: `strata_control/tune_history.py:39-81,99-143`。
- plan 時 identity と full digest オプションの転送: `strata_cli/cli.py:447-455,1763-1768`; `strata_control/tuning.py:723-761`。
- 設定変更、拒否条件、candidate verification 引数の処理: `strata_control/tune_apply.py:227-290,306-370`。

## 調査範囲

指定された Strata checkout のソースを確認しました。CLI `--help`、Release 配布物、各 OS での実行は確認していません。挙動の記述は上記 revision の parser と処理コードに基づきます。
