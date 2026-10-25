# `--batch-telemetry`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--batch-telemetry` |
| 別名 | `--no-batch-telemetry`（無効化。`argparse.BooleanOptionalAction` が生成） |
| 値 | 値を取らない真偽値スイッチ |

## 役割

対応するネイティブ Strata engine に、batch decode window の低頻度サンプルを有効化します。サンプルは monitor 用の `BSTAT`（処理 verifier row 数と稼働 request slot 数）です。`--batch-groups` を使う pipelined path では、stage の host 側 in-flight 時間を表す `PSTAT` も有効になります。これらは GPU 使用率や生成 token 数を表す値ではありません（`src/program/generate.cpp:11364-11375,11739-11742,11852,11914-11920`; `include/strata/core/batch_telemetry.hpp:12-20,49-63`）。

## 使い方

```sh
strata serve --profile /path/to/run-config.json --batch-telemetry
strata serve --profile /path/to/run-config.json --no-batch-telemetry
```

`--profile` はこのコマンドでは run config のパスを受け取ります。オプションは `strata serve` に属し、値は付けません（`strata_cli/cli.py:45-58`）。

## 値と既定値

- `--batch-telemetry` が true、`--no-batch-telemetry` が false です。どちらも値引数を受け付けません。値を後ろに付けると余分な引数として拒否されます（`strata_cli/cli.py:57-58,2223-2231`）。
- parser 上の既定値は `None`（未指定）です。最終値の優先順位は、コマンド指定、保存 profile の override、run config の `batch_telemetry`、`STRATA_BATCH_TELEMETRY`、既定の false です。環境変数は未設定なら無視され、設定済みなら文字列が厳密に `1` のときだけ true、それ以外は false として解決されます（`strata_cli/cli.py:745-769`）。
- run config の `batch_telemetry` は JSON 真偽値でなければなりません。文字列や数値などは `batch_telemetry must be true or false` で拒否されます（`serve/server.py:8241-8254`）。保存 profile の値も bool に限られ、`profile set` では小文字 `true` / `false` を指定します（`strata_control/profiles.py:88-95,98-117`）。
- CLI で指定しなかった場合でも、優先順位の結果が run config 以外（profile または環境変数）なら、Terminal CLI は解決済み真偽値を server の `--batch-telemetry` / `--no-batch-telemetry` に明示して渡します。run config 値と組み込み既定値の場合は server 側で解決します（`strata_cli/cli.py:798-805`）。

## 実行時の動作

通常の単一 engine 起動では、server が親環境と run config の `env` をもとに子環境を作り、CLI 指定があれば config より優先して適用します。true は子環境の `STRATA_BATCH_TELEMETRY=1` にし、false はその変数を削除します。未指定時は config 値を使い、config も未指定なら継承環境を保ちます（`serve/server.py:914-920,3499-3512,8350-8351,8414-8418`）。

ネイティブ engine は batch 生成ループ開始時に `STRATA_BATCH_TELEMETRY` を一度読み、値全体が `1` のときだけ測定を有効にします（`src/program/generate.cpp:11364-11375`）。有効な batch window を集計し、おおむね1秒ごと、または全 slot が idle になった時点で最後の部分サンプルを出します。処理 row 数には pipeline padding や batch MTP の row が含まれる場合があり、単一 request の solo path には batch sample がありません（`include/strata/core/batch_telemetry.hpp:12-47`; `src/program/generate.cpp:11691,11852`）。

`PSTAT` は複数 stage の pipelined path だけで計測し、launch から完了 poll までの host 経過時間を含みます。GPU kernel occupancy と解釈できません（`src/program/generate.cpp:11739-11742,11801,11887-11920`; `include/strata/core/batch_telemetry.hpp:49-63,65-98`）。server は `BSTAT` / `PSTAT` 行を検証して telemetry sample として保持し、request の token stream には渡しません（`serve/server.py:923-935,1204-1213`）。

## 適用条件と副作用

- `--engine strata` のネイティブ engine が batch decode を行う場合にサンプルが得られます。`--engine mock` でも parser はこの option を受理しますが、MockEngine の生成分岐はこの telemetry 設定を使わず、ネイティブ `BSTAT` / `PSTAT` は出しません（`strata_cli/cli.py:48-50,57-58`; `serve/server.py:8343-8351,8425-8430`）。
- option は sampling を有効にして engine 標準出力へ制御行を追加します。Python server がその行を消費するため、request 本文には混ざりません。既定の false では sampler が無効で `BSTAT` は出力されません（`src/program/generate.cpp:11368-11375`; `include/strata/core/batch_telemetry.hpp:19-29`; `serve/server.py:1204-1213`）。
- **replica 起動には明示値が子 engine へ伝わらない経路があります。** server は通常起動用 `env` に option を反映しますが、replica 分岐は各子 engine 用に `child_env(rc, ...)` を作り直し、その後 `configure_batch_telemetry_env()` を呼びません。このため replica mode で CLI の `--batch-telemetry` / `--no-batch-telemetry` や run config の `batch_telemetry` だけに依存した場合、その値が各子へ反映されないことがあります。各 replica は親環境と replica config の `env` をもとに環境を作ります（`serve/server.py:8350-8351,8414-8418,7966-7983`; `serve/replicas.py:91-105`; `serve/server.py:3499-3512`）。
- CUDA/HIP/SYCL の実機でのビルド・計測結果はこのソース調査では確認していません。Telemetry 値の運用上の説明は [`STRATA_BATCH_TELEMETRY`](../../../STRATA_BATCH_TELEMETRY.md) も参照してください。

## 出力とエラー

- 無効な run config の型は server parser の `ap.error()` によって拒否されます。CLI から余分な値引数を付けた場合も argparse の unrecognized-arguments エラーになります（`serve/server.py:8253-8254`; `strata_cli/cli.py:2223-2231`）。
- ネイティブ engine は `BSTAT <windows> <processed_rows> <active_rows> <elapsed_ms>` の形式で出力します。server は長さ80文字以下、正数・上限・row/active 関係を満たす行だけ受理し、不正な行は無視します（`src/program/generate.cpp:11368-11375`; `serve/server.py:923-935,1204-1208`）。
- `PSTAT` の集計値は stage の launch / 完了 poll の時刻差です。sampler は stage 数2〜16の範囲で有効になります（`include/strata/core/batch_telemetry.hpp:54-63`）。

## 根拠

- `strata_cli/cli.py:45-58` — `strata serve` parser と option 定義、BooleanOptionalAction。
- `strata_cli/cli.py:745-779,798-805` — 値の優先順位、既定値、server 引数への反映。
- `serve/server.py:914-920,923-935,1204-1213,3499-3512,8241-8254,8343-8351,8414-8430` — 環境設定、protocol 処理、validation、単一・replica・mock 起動経路。
- `serve/replicas.py:91-105` — replica ごとの config / 環境差分。
- `src/program/generate.cpp:11364-11375,11691,11739-11742,11801,11852,11887-11920` — native sampler の有効化・BSTAT/PSTAT 出力と batch 経路。
- `include/strata/core/batch_telemetry.hpp:12-47,49-108` — batch window および stage host span の集計条件。
