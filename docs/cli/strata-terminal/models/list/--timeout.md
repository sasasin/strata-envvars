# `--timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--timeout` |
| 別名 | なし |
| 値 | 秒数（`float`）。0 より大きく 30 以下 |

## 役割

`--served` で Strata サーバーに接続して現在の稼働モデルを照会するとき、各 HTTP request のタイムアウトを秒単位で指定します。ローカルのインストール済みモデル一覧には適用されません。

## 使い方

```sh
strata models list --served --url https://strata.example --timeout 8
```

ローカル接続では、たとえば `--url http://127.0.0.1:8095` を指定できます。リモート接続先には HTTPS が必要です。

## 値と既定値

- 値は `argparse` の `float` 変換を通ります。省略時は接続解決で `3.0` 秒が設定されます。
- 明示値は `0 < 秒数 <= 30` の範囲でなければなりません。0、負数、30 より大きい値は拒否されます。`NaN` や無限大も比較条件を満たさず拒否されます。
- 数値に変換できない値や値の欠落は parser error になります。
- timeout は接続設定ファイルや環境変数から読み込まず、このフラグが指定された場合だけ上書きします。

## 実行時の動作

`strata models list` の parser に `--timeout` が定義されています。実行時は `--served` が選ばれた場合に限り、URL・保存済み接続・credential 環境変数名とともに `connections.resolve()` へ渡し、返された秒数で `Endpoint` を作成します。`--served` と `--installed` は相互排他です。

`Endpoint.get()` は `/v1/telemetry`、`/metrics`、`/v1/status` 等の read-only endpoint への request に同じ timeout を使います。スナップショット取得は `/v1/telemetry` を優先し、404 の場合は旧形式 endpoint にフォールバックするため、複数の request が順次発生することがあります。この値は各 request に渡されるもので、スナップショット全体の総所要時間上限としては実装されていません。

`--timeout` を `--served` なしで指定すると、ローカル一覧経路で接続オプションは `--served` 専用というエラーになり、終了コード 2 です。`--served` では `--install-dir` は使えず、指定すると同じく終了コード 2 です。

## 適用条件と副作用

- 対象は `--served` によるリモート/ローカルサーバー照会です。コマンドは telemetry/status 情報を読むだけで、timeout 自体がファイルやサーバー設定を変更する処理はありません。
- 接続 URL は HTTP(S) のサーバールートに限られ、埋め込み認証情報・パス・query・fragment は受け付けません。非 HTTPS は localhost、loopback、またはローカルトンネル用途に限られます。
- 接続先が応答しない、または request が timeout した場合、client は接続エラーとして処理します。timeout 値は `urllib` の `opener.open(..., timeout=...)` に渡されます。

## 出力とエラー

- `float` 変換エラーは argparse の usage/error 表示となり、通常の parser error 終了コードは 2 です。
- 0 以下または 30 秒超の値は `timeout must be greater than zero and at most 30 seconds` として失敗します。これは `ValueError` 経由で、`--output json`（または `--json`）なら JSON error、通常出力なら `strata: ...` を stderr に出し、終了コード 2 です。
- HTTP request の timeout や接続不能は `cannot reach Strata server: <例外型>` の client error となり、既定の終了コード 3 です。HTTP status 401/403 は認証/権限エラーで終了コード 4 です。

## 根拠

- `strata_cli/cli.py:141-152` — `models list` の parser、相互排他 scope、`--timeout` の `float` 定義。
- `strata_cli/cli.py:564-588` — `--served` のときの resolve と Endpoint 作成、ローカル経路での接続オプション拒否。
- `strata_cli/connections.py:273-302` — URL/接続設定の選択、timeout の範囲検証と既定値 `3.0` 秒。
- `strata_cli/client.py:38-42,45-63` — client error の既定終了コード、および URL scheme・remote HTTPS 制約。
- `strata_cli/client.py:84-125` — Endpoint の timeout 検証、各 request への timeout 適用と通信失敗処理。
- `strata_cli/client.py:134-152` — telemetry endpoint と404時のフォールバック。
- `strata_cli/cli.py:527-542,2166-2188` — 人間向け/JSON のエラー出力、終了コードの伝播。
