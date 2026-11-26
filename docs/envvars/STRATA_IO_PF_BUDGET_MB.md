# `STRATA_IO_PF_BUDGET_MB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux のファイル層 I/O プリフェッチで、スケジューラが各 decode window に投機読み込みする予算を MiB 単位で固定する。正の値は MiB をバイトへ換算した予算として使われ、予測 expert の blob が予算内に収まらない場合はその読み込みを採用しない。これはプリフェッチ量の上限であり、通常の expert 選択や生成値を変える処理ではない。実装は `FileExpertSource::set_io_prefetch`、`io_budget_now`、`warm_scored` にある（`engine/src/core/expert_source.cpp:1195-1199,1228-1258,1261-1312`）。

## 値と判定

`set_io_prefetch` の Linux 実装で、他のプリフェッチ設定とともに設定時に読み取る。`std::atof` で数値の先頭部分を double に変換し、`max(0.0, value * 1048576.0)` を `uint64_t` に変換する。文字列全体の妥当性検査はなく、`atof` が読める数値の後ろは無視される。変換後の小数バイトは整数化で切り捨てられる。未設定ならメンバー既定値の 0 のまま。固定値が 0 の場合は自動予算を使う（`engine/src/core/expert_source.cpp:1292-1298,1195-1199`; `engine/include/strata/core/expert_source.hpp:1235-1238`）。

| 条件 | unset | 有効になる値（例） | 自動予算になる値（例） |
|---|---|---|---|
| Linux のスケジューラ付き I/O プリフェッチ | `io_budget_fixed_` は 0。自動算出 | `1` → 1 MiB、`2.5` → 2.5 MiB、`12MB` → `atof` が読む `12` に相当 | 空文字、`0`、`0anything`、`abc` は 0。`-1` も 0 に clamp。`0.0000001` のように MiB 換算後 1 byte 未満となる値も整数化後 0 |
| スケジューラ無効、または Linux 以外 | この変数の値は予算計算に使われない | 該当なし | 該当なし |

数値として読めない先頭文字は `atof` により 0 相当になる。空白を含む文字列の扱いも `atof` の変換に従い、コードは独自の空白・大文字小文字検査をしない。浮動小数点から `uint64_t` への変換範囲を超える入力に対する明示的な検査やエラー経路はないため、その範囲の値は規定しない（`engine/src/core/expert_source.cpp:1296`）。

## 有効になる条件

- Linux ビルドで `FileExpertSource::set_io_prefetch(true, ...)` が成功すること。非 Linux では本体が空で、環境変数を読み取らない。Linux でも `base_ == nullptr`、ファイルパスなし、または unbuffered 読み込みの場合は、読み取り前に戻る（`engine/src/core/expert_source.cpp:1261-1277,1310-1312`）。
- I/O プリフェッチ自体が有効であること。`generate.cpp` は `STRATA_IO_PREFETCH` が非空で `atoi` 非ゼロなら明示有効にし、未設定または空文字なら Linux の既定条件を使う。Linux 既定では GGUF をその場で読む経路は有効、`experts.bin` は page cache に expert 全体の 55% 以上の余裕がある場合に有効（`engine/src/program/generate.cpp:8693-8703`; `engine/include/strata/core/expert_source.hpp:1084-1093`）。
- `STRATA_IO_PF_SCHED` が設定され、`atoi` が非ゼロであること。未設定、空文字、`0`、数字で始まらない文字列はスケジューラ無効となり、この予算値は通常のプリフェッチ経路に影響しない（`engine/src/core/expert_source.cpp:1292-1297`; `engine/src/core/expert_source.cpp:1228-1229`）。
- 予算が実際の予測読み込みを制限するには、router lookahead から scored prediction が届くこと。スケジューラと I/O プリフェッチが両方有効なとき `wants_scores()` が真になる。direct/unbuffered 経路、`STRATA_IO_PF_AHEAD=0`、decode gate 閉鎖時など `warm_scored` の条件を満たさない場合は通常の `warm` にフォールバックする（`engine/include/strata/core/expert_source.hpp:995-1001`; `engine/src/core/expert_source.cpp:1228-1229,1284-1285`）。
- `STRATA_IO_PF_BUDGET_FRAC` は自動予算に使う割合（既定 0.5、clamp 0.01–4.0）。固定予算が正なら `io_budget_now()` はこれと測定レート・window 時間・feedback scale を使わず固定値を返す。未設定や 0 の場合は、測定値が揃うまで 256 MiB、その後は worker 1 本あたりの EWMA read rate × worker 数 × window 時間 × fraction × feedback scale を使い、下限 16 MiB を適用する（`engine/src/core/expert_source.cpp:1192-1199`; `engine/include/strata/core/expert_source.hpp:1237-1248`）。
- CLI 引数によるこの予算の上書きは見つからなかった。`STRATA_IO_PF_THREADS` は自動予算の worker 数には関係するが、正の固定予算は変更しない（`engine/src/program/generate.cpp:8701-8703`; `engine/src/core/expert_source.cpp:1283,1296-1297`）。

## 実行時の詳細

値は `set_io_prefetch(true, ...)` ごとに環境から読み、`io_budget_fixed_` に保存する。通常は初期化時に一度読み、その `FileExpertSource` が動いている間は環境の変更を再読しない。ただし file-tier idle policy が既定のプリフェッチを停止し、後の request / VRAM 状態変化で再有効化するときは同じ関数が再度呼ばれるため、その時点の値を読み直す（`engine/src/core/expert_source.cpp:1261-1304`; `engine/src/program/generate.cpp:10275-10285,10341-10377`）。

スケジューラが有効な場合、各 decode window の予測 expert ごとに blob サイズを加算し、`io_win_bytes_ + bytes > budget` なら予測を採用せず budget reject counter を増やす。読み込みは通常の demand read を優先し、残った予測 job は deadline が早いものから処理する。固定予算が正なら window ごとの測定・feedback 変化にかかわらず同じバイト数が上限になる（`engine/src/core/expert_source.cpp:1202-1223,1228-1258,1355-1389`; `engine/src/core/expert_source.cpp:3818-3819`）。

この変数は unset と明示的な 0 のどちらも「自動」にする。予算が尽きた場合に Strata は予測 read-ahead を見送り、需要時の expert 読み込みへ進む。予算超過そのものによる警告、エラー終了、timeout は実装されていない（`engine/src/core/expert_source.cpp:1243-1258`）。

## ログと測定値

`STRATA_IO_PREFETCH` とスケジューラが有効なら、stderr に `strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)` を出す。serve の request I/O ログでは `read ahead ... (budget %.0f MB/window)` として現在の予算値と budget reject 数を表示する。スケジューラ無効時は counter の予算値が設定されないため、この表示は 0.0 MB/window になる（`engine/src/program/generate.cpp:8719-8721,23847-23873`; `engine/src/core/expert_source.cpp:1184-1188`）。

`docs/DETAILS.md` の file-tier I/O 節には I/O prefetch、decode gate、staging 等の測定があるが、この固定予算値の比較測定は確認できなかった。本書では性能効果を推定しない。

## 根拠

- `engine/src/core/expert_source.cpp:1192-1199` — 固定予算と自動算出の規則。
- `engine/src/core/expert_source.cpp:1228-1258,1261-1312` — scored warm の制御、値の読み取り、Linux プリフェッチ初期化。
- `engine/src/core/expert_source.cpp:1355-1389,3818-3819` — worker の job 処理と window 更新。
- `engine/include/strata/core/expert_source.hpp:995-1001,1233-1253` — scored prediction の条件と予算状態。
- `engine/src/program/generate.cpp:8693-8724,10275-10285,10341-10377,23847-23873` — 初期化条件、idle policy による再初期化、ログ。
- `engine/include/strata/core/expert_source.hpp:1084-1093` — Linux 既定の適用条件。
- `docs/DETAILS.md:309-317` — file-tier I/O の関連説明との照合。
