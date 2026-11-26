# `STRATA_IO_STATS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ファイル層から expert blob を読むとき、読み出し時点で各ページが OS のページキャッシュにあった量と、なかった量を集計する診断用スイッチです。Linux では `mincore` によるページ常駐確認を有効にし、生成時の `io path` 集計や serve 中のリクエスト別 I/O ログに反映します。読み取り元や expert の選択、生成結果を変える設定ではありません。`FileExpertSource::set_io_stats` と、そのカウンター参照箇所が実装です（`engine/include/strata/core/expert_source.hpp:1027-1030`、`engine/src/core/expert_source.cpp:1086-1097`、`1896-1904`、`engine/src/program/generate.cpp:25328-25346`）。

リポジトリ全体の完全一致検索では、実行時の値読み取りは次節記載の engine 箇所だけでした。`terminal/data/settings-register.json` は読み取り箇所の台帳で、ベンチ用 `run_pairs.py` は設定 JSON にこの診断変数が含まれる実験を拒否します（`terminal/data/settings-register.json:18397-18425`、`docs/bench-results/2026-10-08-community-r9700-linux/harness/run_pairs.py:88-92`）。これらは engine の環境読み取りではありません。

## 値と判定

設定値を使う箇所は `std::getenv` で取得し、値が null でないことに加えて `std::atoi(value) != 0` を条件にします。整数全体の厳密な検証や範囲制限はありません。`atoi` の規則により、先頭の空白と符号を許し、数値として読める先頭部分を変換します。したがって `1`、`2`、`-1`、`1tail` は真、`0`、`0tail`、`true`、`false`、空文字は偽です。数値に変換できない先頭部分は 0 になります。`atoi` で `int` の範囲を超える文字列の結果は規格上保証されません（`engine/src/program/generate.cpp:8742-8744`、`10281-10282`、`10356-10357`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| ファイル層の初期化で I/O prefetch が有効でない | `io_stats` は無効 | `atoi` が 0 以外を返す値。例: `1`、`-1`、`1tail` | `atoi` が 0 を返す値。例: 空文字、`0`、`0tail`、`true` |
| Linux の既定 I/O prefetch が有効 | `set_io_prefetch` が有効化できれば統計も有効 | `STRATA_IO_STATS` の値に関係なく、prefetch が統計を有効化 | 該当なし（prefetch が有効な間は `io_stats_ = on || io_pf_`） |
| Linux の file-tier idle 方針で既定 prefetch を停止・再開 | 停止時に unset なら統計を無効化。再開時は prefetch が統計を有効化 | 停止時、上記の `atoi != 0` | 停止時、上記の `atoi == 0` |

初期化では `STRATA_IO_PREFETCH` が有効、または Linux file-tier 既定値が有効な分岐に入ると、prefetch の設定を試みます。その分岐に入った場合、prefetch が実際には有効にならなくても `STRATA_IO_STATS` を独立に読む `else if` には進みません。prefetch 分岐に入らない場合だけ、`STRATA_IO_STATS` を評価して有効化します（`engine/src/program/generate.cpp:8693-8704`、`8742-8744`）。prefetch が動作中なら `set_io_stats(on)` は prefetch を優先して統計を有効に保ちます（`engine/include/strata/core/expert_source.hpp:1027-1030`）。

## 有効になる条件

- file-tier の `FileExpertSource` が使われること。通常は `--mmap-experts`、または RAM 不足時の file-tier fallback です。arena から読む経路では、この変数による file-tier 集計は行いません（`engine/src/program/generate.cpp:8595-8603`、`8621-8647`）。
- ページキャッシュの resident / nonresident byte 集計は Linux の `copy_from_files` と mapped blob の読み出し経路にコンパイルされています。Linux 以外ではこの `mincore` 集計ブロックは実行されません（`engine/src/core/expert_source.cpp:1896-1924`、`5220-5231`）。
- 既定 I/O prefetch はページキャッシュ統計も有効にします。全 expert が GPU cache に収まり、file-tier の Linux 既定 prefetch が停止されると、`STRATA_IO_STATS` の値を読み直して統計の有効・無効を設定します。明示的に有効化した prefetch はこの既定 idle 方針の停止対象ではありません（`engine/src/program/generate.cpp:10275-10285`、`10341-10368`）。
- generate 実行の最終 `io path` 行は file-tier source の集計節でのみ出ます。serve のリクエスト別 `file tier I/O` 行は同じ file-tier source で OS I/O サンプルが有効な場合に出て、その行の `page cache held ... not ...` 部分は `src.io_stats()` が真の場合だけ追記されます（`engine/src/program/generate.cpp:23825-23846`、`25328-25346`）。
- この値を優先・上書きする CLI 引数はありません。`STRATA_IO_PREFETCH` が prefetch を有効にしている間は prefetch 側が統計を有効化します。file-tier idle 方針が既定 prefetch を止めるときだけ、この変数を再評価します（`engine/src/program/generate.cpp:8693-8704`、`10275-10285`、`10351-10368`）。

## 実行時の詳細

初期値は `io_stats_ = false` です。file-tier 初期化で設定値を評価し、prefetch が有効なら `set_io_prefetch` 内で `io_stats_ = true` にします。I/O prefetch がない場合は `STRATA_IO_STATS` の parse 結果を `set_io_stats` に渡します（`engine/include/strata/core/expert_source.hpp:1027-1030`、`engine/src/core/expert_source.cpp:1283-1291`、`engine/src/program/generate.cpp:8742-8744`）。

Linux のファイル読み出しでは `io_stats_` が真のとき、expert の各 span について `mincore` でページ常駐数を調べ、cached / uncached byte カウンターに加算します。prefetch が有効な場合も同じカウンターを取りますが、統計計測は file read の経路で行うもので、prefetch の有無とは別に集計値として出します（`engine/src/core/expert_source.cpp:1086-1097`、`1896-1920`）。

serve 中は `STRATA_IO_STATS` の初期判定を毎リクエストは行いません。初期化時の値を保持し、GPU cache が全 expert を保持したことで Linux の既定 prefetch を止める場合と、後に file-tier が再び必要になった場合に再評価します。そのため、プロセス起動後に環境変数だけを変更しても直ちには反映されず、その idle 方針の切り替わり時に限って再読込されます（`engine/src/program/generate.cpp:10275-10285`、`10341-10368`）。子プロセスへの転送処理はありません。

同じ名前の別参照 `cold_log` は、値を parse せず `getenv(...) != nullptr` だけを確認し、初回に `static` 保存します。空文字や `0` でも設定されていれば cold-read の詳細ログを許可します。この参照だけでは `io_stats_` は有効になりません。ログ自体には `drive.d.cold_mode != 0` も必要です（`engine/src/program/generate.cpp:23879-23896`）。

## ログと測定値

generate 終了時、統計が有効なら stdout に `io path` 行を出し、ページキャッシュにあった MB と無かった MB、prefetch 状態、prefetch の読み取り・利用・スキップ件数、`pread` の量と所要時間、decode の待ち時間を表示します（`engine/src/program/generate.cpp:25336-25346`）。

serve では stderr の `strata serve: file tier I/O this request: ...` 行に、OS が storage から読んだ量と major fault 数、expert read 量が記録されます。統計が有効なら `; page cache held ... at the read, not ...` が加わります。OS I/O サンプルが無効な場合、この行自体が出ません（`engine/src/program/generate.cpp:23831-23846`）。cold mode が有効で `STRATA_IO_STATS` が設定済みなら、統計値が 0 でも `strata serve: cold reads (STRATA_COLD_OVERLAP=...) ...` の詳細行が許可されます（`engine/src/program/generate.cpp:23879-23893`）。

## 根拠

- `engine/src/program/generate.cpp:8693-8704` — file-tier I/O prefetch と Linux 既定動作。
- `engine/src/program/generate.cpp:8742-8744` — 初期化時の `STRATA_IO_STATS` 値判定。
- `engine/src/program/generate.cpp:10275-10285`、`10341-10368` — 全 GPU cache 時の既定 prefetch 停止・再開と再評価。
- `engine/src/program/generate.cpp:23831-23846`、`23879-23896` — serve のリクエスト別 I/O / cold-read ログ。
- `engine/src/program/generate.cpp:25328-25346` — generate 終了時の I/O 統計出力。
- `engine/src/core/expert_source.cpp:1086-1097`、`1261-1291`、`1896-1924`、`5200-5231` — Linux の `mincore`、prefetch による統計有効化、ページキャッシュ集計。
- `engine/include/strata/core/expert_source.hpp:1027-1035`、`1222-1227` — 統計 API と初期状態。
