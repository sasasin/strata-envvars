# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定時 `True` |

## 役割

標準出力に出る人間向け情報を抑制する共通 one-shot オプションです。このコマンドは operation journal から結果レコードを読み出すため、`--quiet` を指定すると成功時の標準出力を抑えます。

## 使い方

```sh
strata ops result 0123456789abcdef0123456789abcdef --profile default --quiet
```

`operation_id` は 32 桁の小文字 hexadecimal ID です。例では形式のみ示しており、その ID の存在を示すものではありません。

## 値と既定値

値や引数は付けません。`argparse` の `store_true` なので、省略時は偽、指定時は真です。重複指定を独自に検証する処理はありません。`strata ops result` は必須の `--profile`、位置引数 `operation_id`、`--output {human,json}`（既定値 `human`）も受け取ります。`--quiet` は各 ops parser を含む one-shot parser 群に後から追加されます。（`strata_cli/cli.py:258-268,512-515`）

## 実行時の動作

`--quiet` だけを指定した通常の human 出力経路では、`main()` が `_run()` の標準出力を一時バッファに捕捉し、終了コードが成功なら表示せず破棄します。`ops result` の成功処理は journal record を `_success()` に渡し、human 専用の文面を指定しないため既定の整形 JSON を標準出力へ出します。従って quiet はこの JSON を含む成功時 stdout を抑制します。標準エラー出力は捕捉対象ではありません。（`strata_cli/cli.py:535-542,1409-1411,2217-2248`）

`--output json` または `--json` と併用すると quiet 捕捉を行わず、JSON 結果を表示します。`--json` は one-shot parser 群に追加される alias で、`main()` により `output=json` に変換されます。（`strata_cli/cli.py:512-515,2232-2237`）

## 適用条件と副作用

このオプションは結果取得の表示経路にのみ作用し、journal の読み取り・検証や返されるデータ自体を変更しません。`journal.load()` は operation ID から journal ファイルを解決し、読み込んだ record を検証します。record の状態が `running` なら `completion_unverified: true` を加えます。（`strata_control/journal.py:60-63,185-244,247-251`）

## 出力とエラー

quiet がない場合、既定の human 出力は `record` を含む整形 JSON です。`--output json` / `--json` の場合は `schema_version` と `ok: true` を含む JSON envelope が標準出力に出ます。quiet 単独の成功時は stdout が抑制されます。（`strata_cli/cli.py:535-542,1409-1411,2236-2248`）

不正な ID（32 桁の小文字 hex でない）、記録が見つからない場合、または journal record の検証に失敗した場合はエラーになります。`ProfileError` は `_run()` の `ValueError` 経路で処理され、human モードでは `strata: ...` が stderr、JSON モードではエラー JSON が stdout に出て、例外に指定された終了コードを返します。quiet 時も stderr のエラーは抑制されません。parser の引数・選択肢エラーは `main()` の `parse_args` 段階で終了します。（`strata_control/journal.py:60-63,185-198,201-243`; `strata_cli/cli.py:527-532,2166-2173,2223-2231`）

## 根拠

- parser とコマンド階層、`--profile`・`--output`・ID 引数: `strata_cli/cli.py:255-268`
- one-shot parser への quiet/json 追加: `strata_cli/cli.py:508-515`
- `result` の journal 読み出しと成功出力: `strata_cli/cli.py:1409-1411`
- quiet の stdout 捕捉・成功時破棄・失敗時出力: `strata_cli/cli.py:2196-2248`
- JSON/ human 成功・失敗出力、例外経路: `strata_cli/cli.py:527-542,2166-2193`
- ID/path 検証、journal 内容検証と読み出し: `strata_control/journal.py:60-63,185-251`
