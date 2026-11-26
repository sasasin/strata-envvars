# `STRATA_BATCH_TELEMETRY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

engine の batch decode window の計測を有効にする opt-in 変数。設定が有効でも変わるのは stdout の `BSTAT`（batch window の件数・処理 row 数・active slot 数・計測 span）と、パイプライン時の `PSTAT`（stage の host-side in-flight span）の出力であり、生成 token や request の選択を変える処理ではない。読み取りは `generate()` 内の batch 処理初期化時に行う。`engine/src/program/generate.cpp:16827-16846`、`engine/src/program/generate.cpp:17529-17533`、`engine/src/program/generate.cpp:18349-18356`。

標準の server 起動では、CLI、saved profile、run config、環境変数から解決された boolean を server が engine 子プロセスの環境へ反映する。terminal CLI からの値の解決は `terminal/strata_cli/cli.py:783-803`、server の環境反映は `terminal/serve/server.py:711-718, 9391-9395`。

## 値と判定

engine は `std::getenv` で取得した文字列が、1 文字の `"1"` と完全一致する場合だけ有効にする。未設定、空文字、`"0"`、`"true"`、`"01"`、`"1x"` は無効。数値変換や大文字小文字変換は行わない。`engine/src/program/generate.cpp:16827-16830`。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| engine の読み取り | 無効 | `1` のみ | 空文字、`0`、`true`、`01`、`1anything` など。文字列全体が `1` でなければ無効 |
| `strata serve` CLI の `_effective` 解決 | 最終既定値は `false` | 環境変数由来としては値が厳密に `1` のとき `true` | 変数が存在して空文字または `1` 以外なら `false` |

`strata serve` CLI の優先順位は、明示 CLI (`--batch-telemetry` / `--no-batch-telemetry`)、saved profile override、run config、環境変数、既定 `false` の順。`terminal/strata_cli/cli.py:78-79, 783-803`。直接 `terminal/serve/server.py` を起動する場合は、明示 CLI override があればそれを、なければ config の `batch_telemetry` を使い、どちらも未指定なら継承環境を保つ。`true` は子環境に `"1"` を設定し、`false` は変数を削除する。`terminal/serve/server.py:711-718`。run config の値は bool でなければ `batch_telemetry must be true or false` で拒否される。`terminal/serve/server.py:9283-9284`。

## 有効になる条件

- engine の実行環境に文字列 `1` が渡されていること。engine は起動後にこの値を一度読み、その後の環境変更は反映しない。`engine/src/program/generate.cpp:16827-16830`。
- batch decode window を処理すること。通常の単独 request 経路には `report_batch_window` の呼び出しがなく、batch sampler のサンプルも出ない。batch と pipelined batch の呼び出し箇所は `engine/src/program/generate.cpp:17470` と `engine/src/program/generate.cpp:18118-18122`。
- `BSTAT` の計測は OS / backend 分岐を伴わない engine の共通 batch 処理にある。`PSTAT` はさらに `piped`（`o.batch > 0 && o.batch_groups > 1 && stages.size()+1 > 1`）の場合だけ sampler を有効にする。stage 数は 2..16 の範囲で sampler が有効になる。`engine/src/program/generate.cpp:17529-17533`、`engine/include/strata/core/batch_telemetry.hpp:60-63`。
- server の通常単一 engine 経路では CLI/config 値を子環境に反映する。replica 経路と split 経路は `child_env(...)` を直接渡し、`configure_batch_telemetry_env` を呼ばないため、CLI/config の値だけでは子 engine を切り替えない。親プロセスから継承した `STRATA_BATCH_TELEMETRY=1` は `child_env` が `os.environ` をコピーするため残る。`terminal/serve/server.py:4007-4010, 8845-8852, 8912-8919, 9391-9395, 9472-9477`。
- mock engine は native engine ではないため、この C++ 計測の対象外。`terminal/strata_cli/cli.py:69-71`。

## 実行時の詳細

engine は batch 処理初期化時に環境を読み、`batch_telemetry_enabled` と `BatchWindowSampler` をその処理中の値として保持する。関数内の `static` cache や request ごとの再読込はなく、実行中に値を書き換えても切り替わらない。`engine/src/program/generate.cpp:16827-16830`。

`BatchWindowSampler` は有効な完了 window（`processed_rows >= 1`、`active_rows >= 1`、`active_rows <= processed_rows`、完了時刻が開始以降）を集計する。最初に含めた window の開始から 1 秒以上経過したとき、または全 slot が idle になったときに sample を返す。idle 時は 1 秒未満でも最終 partial sample を返し、span は最低 1 ms。出力後に集計値を初期化する。`engine/include/strata/core/batch_telemetry.hpp:19-40`。sample があると engine は stdout に `BSTAT <windows> <processed_rows> <active_rows> <elapsed_ms>` を書いて flush する。`engine/src/program/generate.cpp:16839-16846`。

パイプラインでは同じ opt-in により stage launch から完了 poll までの host 時間も集計し、間隔または idle 時に `PSTAT` 行を stdout に出す。これは GPU kernel 利用率の測定ではない。`engine/include/strata/core/batch_telemetry.hpp:54-99`、`engine/src/program/generate.cpp:18065, 18266, 18278, 18349-18356`。

server は `BSTAT` / `PSTAT` を engine の stdout protocol から読み、request の token 行には渡さず、形式・値域が不正な sample は無視する。`BSTAT` は通常 engine の `/v1/telemetry` snapshot に、replica では replica ごとの値に載る。`terminal/serve/server.py:1051-1060, 7484-7512`、`terminal/serve/server_parts/engines.py:522-534`。

## ログと測定値

engine の観測出力は stderr の診断文ではなく stdout protocol 行 `BSTAT <windows> <processed_rows> <active_rows> <elapsed_ms>`。パイプラインでは追加で `PSTAT <stages> <elapsed_us> <stage_0_us> ...` が出る。無効時、単独 request 経路、または sampler がまだ 1 秒間隔にも idle 終端にも達していない間は該当行が出ない。`engine/src/program/generate.cpp:16839-16846, 18349-18356`、`engine/include/strata/core/batch_telemetry.hpp:27-40, 80-99`。

server は `BSTAT` を `/v1/telemetry` の `effective_rows_window`（sample 中の processed rows / windows）と `batch_active_rows_window` などに変換する。不正な行は server が黙って破棄する。`terminal/serve/server.py:1051-1055, 7501-7512`、`terminal/serve/server_parts/engines.py:522-534`。この調査では build・GPU 実行・性能測定を行っていない。

## 根拠

- C++ 環境読み取り、判定、BSTAT 出力: `engine/src/program/generate.cpp:16827-16846`
- batch / pipelined batch の計測呼び出しと PSTAT 出力: `engine/src/program/generate.cpp:17470, 17529-17533, 18065, 18118-18122, 18266, 18278, 18349-18356`
- sampler の集計条件と周期: `engine/include/strata/core/batch_telemetry.hpp:19-47, 54-108`
- terminal CLI の優先順位: `terminal/strata_cli/cli.py:78-79, 783-803, 837-844`
- server の子環境反映・config 検証・経路差: `terminal/serve/server.py:4007-4028, 711-718, 8845-8852, 8912-8919, 9283-9284, 9391-9395, 9472-9477`
- server の sample 取り込みと telemetry 化: `terminal/serve/server.py:1051-1060, 7484-7512`; parser `terminal/serve/server_parts/engines.py:522-534`
