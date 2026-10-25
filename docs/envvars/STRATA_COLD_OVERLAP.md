# `STRATA_COLD_OVERLAP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CPU が担当する expert のファイル読み込みを、同じ layer の ready な expert の計算と重ねるか、GGUF のページキャッシュに全体が載っている expert を staging buffer にコピーせずマッピングから計算するかを選びます。適用箇所は multi-token expert pool の dispatch です。CPU が計算する expert がない layer では、この処理は呼ばれません。

環境変数は dispatch と `FileExpertSource::prefetch_begin()` でそれぞれ `static` に一度読み取られます。通常は値が同じでも、プロセス内で環境を書き換えた場合、各読み取りが初めて行われる時期の違いで値が異なる可能性があります。

## 値と判定

非空の値は `atoi()` で整数に変換されます。文字列全体の検証はなく、先頭の空白や符号を許し、数字列の後ろは無視します（例: `2junk` は2、数字に変換できない文字列は0）。明示的な空文字は unset と同じ既定値です。

| 設定 | dispatch のモード | 動作 |
|---|---:|---|
| unset / 空文字 | Linux の GGUF read-in-place なら4、それ以外0 | 条件付きで zero-copy のみ。既定4の条件は下記参照 |
| 0 | 0 | 従来どおり、CPU が使う expert の読み込みを同期 prefetch してから計算 |
| 1 | 1 | 読み込みを背景スレッドで開始し、ready な expert を計算してから、読み込み完了した expert を順次計算 |
| 2 | 2 | 測定用。背景読み込みを開始した直後に join してから計算するため、読み込みと計算は重ならない。読み込み時間を別計測 |
| 3 | 3 | 1 の overlap に、条件を満たす expert の zero-copy を加える |
| 4 | 4 | zero-copy を有効にし、残りの読み込みは同期で行う |
| 5以上 | 4 | dispatch は `atoi` の結果を0〜4に clamp するため、zero-copy 判定では4として扱う。ただし `prefetch_begin()` は clamp 前の値を使い、値が4と等しくないため非同期読み込みも開始する。従って実際は3相当の overlap + zero-copy になる |
| 負数 | 0 | dispatch が0に clamp する |

この値は文字列全体比較ではなく `atoi()` によるため、大文字小文字は関係しません。dispatch の mode は `src/core/expert_source.cpp:4816-4820`、FileExpertSource の読み込み側は `src/core/expert_source.cpp:2202-2208` で判定されます。5以上の差はこの二つの変換処理の相違によります。

## 有効になる条件

- overlap は CPU 側で処理する未 ready expert があり、`d.src` が非同期 prefetch を実装する `FileExpertSource` である場合に限り実際の読み込みと重なります。基底 `ExpertSource::prefetch_begin()` は通常の `prefetch()` を同期実行し、pending を作りません（`include/strata/core/expert_source.hpp:252-260`）。
- FileExpertSource でも staged source でない場合、layer / expert 範囲外、対象がない場合は `prefetch_begin()` が読み込みを開始しません（`src/core/expert_source.cpp:2192-2199`）。RAM complement や override にある expert、既に staging 済みの expert も読み込み対象になりません（同: `2125-2185`）。
- mode 3/4 の zero-copy は Linux の `cached_bytes()` によるページ常駐確認が必要です。GGUF の role mapping があり、mapping が開いた状態、unbuffered/direct 読み込みでないこと、native expert layout で対象 layer の `tail_off == 0` が条件です。expert の3 tensorすべての span がページキャッシュに載っていると確認でき、既存 staging entry がない場合に限り、マッピングを直接使います（`src/core/expert_source.cpp:1000-1015,2125-2171`）。Linux 以外では `cached_bytes()` は0を返すため zero-copy にはなりません。
- unset / 空文字の既定4は `FileExpertSource::linux_file_defaults()` が true の場合だけです。Linux かつ GGUF read-in-place（`role_ptr_` がある場合）に true となり、`experts.bin` pack には適用されません（`include/strata/core/expert_source.hpp:1010-1012`）。明示値1〜4はこの既定判定を経ず dispatch mode になりますが、上記のsource / CPU処理条件は残ります。

## 実行時の詳細

mode 0 は `prefetch()` で必要な blob を埋めてから CPU pool が計算します。mode 1/3 は `prefetch_begin()` が pending blob を背景スレッドで読み、dispatch はまず ready expert の job を pool で実行します。読み込みが着地するたびにその expert の job を追加実行し、最後に読み込み thread を join します。direct I/O の場合は最大4 threadで16件単位、それ以外は `fetch_threads_` を上限に thread を作ります（`src/core/expert_source.cpp:2220-2255,2258-2272,5128-5173`）。mode 2 は最初の読み込みをすべて join して所要時間を記録してから、ready / 読み込み済みの expert を計算します。mode 4 は `prefetch_begin()` 内で同期 `fill_many()` を行い、pendingを0にして返します（同: `2208-2218`）。

zero-copy の対象は `claim_todo()` が page-cache resident と判定すると staging 対象から外し、`zc_roles()` が gate / up / down の各 role pointer を返します。native CPU kernel の job にそのポインタと role 間 offset を渡して、マッピング上のデータを直接計算します（`src/core/expert_source.cpp:2168-2171,2275-2287,5093-5119`）。mode 3/4 の設定だけで全 expert が zero-copy になるわけではありません。

`STRATA_COLD_OVERLAP` が設定されていれば（空文字を含む）、または `STRATA_IO_STATS` が設定されていれば、mode が0以外のとき request ごとの cold read 集計を stderr に出します。出力には mode、mappingから直接計算したexpert数、読み込み対象layer/expert数、ready expert数、pool batch数、読み込み・計算・待機時間が含まれます（`src/program/generate.cpp:15445-15462`）。Linux file-tier既定の起動ログにも、cold overlap値と関連する read-ahead の状態が含まれます（同: `5655-5684`）。

## 根拠

- `src/core/expert_source.cpp:4814-4820` — dispatchでの `atoi()`、clamp、未設定時の既定値。
- `src/core/expert_source.cpp:2192-2255` — `prefetch_begin()` の早期条件、既定値、mode 4 の同期読み込み、その他modeの非同期読み込み。
- `src/core/expert_source.cpp:1000-1015,2125-2171` — Linux page-cache resident byte確認とzero-copy対象の選定。
- `src/core/expert_source.cpp:5029-5045,5128-5173` — CPU missの収集、mode 0/2/その他のdispatch処理、着地待ち。
- `src/core/expert_source.cpp:5093-5119,2275-2287` — native jobへのmapping pointer引き渡し。
- `include/strata/core/expert_source.hpp:252-260,1010-1012` — 基底実装とLinux既定適用範囲。
- `docs/DETAILS.md:272-295` — Linux GGUF read-in-placeではzero-copy、I/O prefetch、decode gateを既定有効とする説明、および測定条件。記載測定は機能群をまとめて比較したもので、STRATA_COLD_OVERLAP単体の性能値としては扱わない。
