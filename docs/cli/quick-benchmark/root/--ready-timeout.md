# `--ready-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `python tools/strata_bench.py`（`bench.sh` / `BENCH.bat` から委譲） |
| オプション | `--ready-timeout` |
| 別名 | なし |
| 値 | 秒数。`float` に変換される数値 |

## 役割

ベンチマーク自身が起動した Strata サーバーについて、モデルのロード完了を待つ時間を指定します。既定値は 1800 秒（30 分）です。ベンチマークは準備完了を確認してから計測を始めるため、この値は計測スイートの実行時間ではなく起動後の準備待ちに適用されます。

## 使い方

```bash
python tools/strata_bench.py --ready-timeout 900
```

`./bench.sh --ready-timeout 900`（Linux）または `BENCH.bat --ready-timeout 900`（Windows）でも同じスクリプトに引数が渡されます。

## 値と既定値

- `argparse` の `type=float` で変換され、未指定時は `1800` です。整数・小数の秒数を指定できます。
- 独自の範囲検証や有限値検証はありません。float に変換できない文字列は `argparse` が引数エラーとして拒否します（通常の argparse usage/error 経路）。
- 0、負数、`nan` は待機ループの条件を満たさず、最初の反復前にタイムアウト扱いになります。`inf` は有限の期限を設けませんが、子サーバーの終了または準備完了で待機を抜けます。

## 実行時の動作

- この値が使われるのは、接続先に Strata が応答せず、`--url` も指定されていないため、ベンチマークが設定ファイルからサーバーを新規起動する経路です。`wait_ready` は期限内に最大 3 秒間隔で `/health` を確認し、応答 JSON の `service` が `strata` かつ `loaded` が真になったとき成功します。子プロセスが先に終了した場合も失敗します。
- 既に動いている Strata サーバーを使う場合、および `--url` を使う場合はこの待機関数を通らず、本オプションは実質的に使われません。`--compare-only` はサーバー処理より前に終了するため、同様に影響しません。
- 期限判定は各ループの先頭で行われます。1回の health 確認には最大 5 秒の HTTP timeout が設定され、その後に 3 秒 sleep するため、実際の待機が指定値を超えることがあります。

## 適用条件と副作用

- 新規サーバーの起動待ちだけを延長または短縮します。モデルのロード方法や設定値は変更しません。
- 準備完了にならない場合、ベンチマークはサーバーのログ末尾（最大 15 行）を stderr に出し、戻り値 1 で終了します。自身が起動したサーバーは `finally` で停止され、通常の terminate に 90 秒以内に応答しない場合は kill されます。
- `--quiet` を併用すると、待機中の「still loading」進捗表示は抑止されます。タイムアウト時のエラーとログ末尾は `print(..., file=sys.stderr)` で出力されるため抑止されません。

## 出力とエラー

- 待機中、通常モードでは初回およびその後約 30 秒ごとに経過秒数を stdout に表示します。
- タイムアウトまたは起動プロセスの早期終了では `The server did not become ready. Last log lines:` とログ末尾を stderr に出し、終了コード 1 を返します。
- 起動待ちに到達する前の引数変換エラーは argparse のエラー経路です。対象ソースでは `--ready-timeout` 自体の明示的な使用範囲チェックは確認できません。

## 根拠

- parser、既定値、型: `tools/strata_bench.py:946-948`
- 新規起動が必要な条件と ready 待機呼び出し: `tools/strata_bench.py:982-999`
- サーバー起動処理と子プロセスへの引数: `tools/strata_bench.py:688-705`
- health 応答・期限・poll 間隔・進捗表示: `tools/strata_bench.py:708-720`
- タイムアウト失敗時の stderr と終了コード: `tools/strata_bench.py:996-999`
- 起動したサーバーの停止処理: `tools/strata_bench.py:723-730`, `tools/strata_bench.py:1035-1037`
- quiet 時の進捗ログ抑止: `tools/strata_bench.py:948-949`
- 委譲ラッパー: `bench.sh:6-10`, `BENCH.bat:14-18`
- quick benchmark の実行方法と用途: `docs/COMMUNITY_BENCHMARKS.md:96-106`
