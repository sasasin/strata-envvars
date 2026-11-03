# `FNX_PRECAP_TRACE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX split engine の batched `verify_rows` で、既存 graph の cache hit ではなく新しい処理経路に入ったとき、実行経路（`capture` または `eager`）、総 row 数、lane ごとの row 数、ホスト側の経過時間を stderr に出す診断スイッチです。graph の保持・再利用を有効にするスイッチではなく、計算結果を変更する処理もありません。対象の名前は `src/split/src/engine_common.cu` にある環境読み取り 1 箇所だけで参照されます。

## 値と判定

`fnx::env_int("FNX_PRECAP_TRACE", 0)` が設定値全体を符号付き 10 進整数として読み、結果が 0 以外ならログを有効にします。

| 値 | 判定 |
|---|---|
| 未設定 | 既定値 `0`。ログなし |
| `0`, `+0`, `-0` | 変換結果が 0 のためログなし |
| 0 以外の範囲内整数（負数を含む） | ログあり |
| 空文字、空白、数字以外、整数の後ろに文字が続く値 | 変換失敗。`std::runtime_error` |
| `long long` の範囲外 | `strtoll` が `ERANGE` を返し、変換失敗。`std::runtime_error` |

先頭・末尾の空白や `1x` のような末尾文字は許容しません。先頭の `+` / `-` は許容されます。境界値は `long long` の最小値から最大値までです。エラー文字列は `FNX_PRECAP_TRACE: '<値>' is not a whole number` です。これは真偽値文字列を解釈する設定ではありません。

## 有効になる条件

- この読み取りは `src/split/src/engine_common.cu` の `Engine::verify_rows()` にあります。同ファイルはオプトインの `strata-split` 実行ファイルに含まれ、CMake 上の対象は Linux CUDA または Linux HIP 向けです。通常の Strata engine にこの設定の読み取りはありません。
- `verify_rows()` で `batch_graph_ready(T, key)` が false となり、新しい処理経路を準備するときだけ判定・出力します。graph slot/cache が hit した呼び出しではこの環境変数を読まず、ログも出しません。
- `FNX_PRECAP` は graph cache の利用可否を別に制御します。cache を無効にしても `batch_graph_ready()` は false を返すため、`verify_rows()` の新規処理経路では本変数によるログが出ます。cache が有効でも miss ならログ対象です。`FNX_CAPTURE_AFTER` などで処理経路が eager になった場合も、その経路名を `eager` として出します。

## 実行時の詳細

読み取りは `static const bool trace` の初回初期化時に一度だけ行われます。初期化のタイミングはプロセス起動時ではなく、`verify_rows()` が graph miss の分岐に初めて入った時点です。その後プロセス内で環境を変更しても判定は再評価されません。無効値をその分岐で初めて読むと例外になります。

有効時の出力形式は `fnx: eager|capture verify_rows T=<総row数> lanes:rows <lane>:<row数>... (<ミリ秒> ms)` で、`stderr` に書かれます。時間は準備処理開始時点からログ組み立て後までのホスト経過時間です。このログ自体は測定値を集計したり graph cache の状態を変えたりしません。sfnx の要求処理中に例外が発生すると、上位の失敗処理が `ERR <例外文字列>` を出力し、stderr に `sfnx: failed: <例外文字列>` を記録して終了コード 1 で終了します。

## 根拠

- `src/split/src/env.hpp:15-21,33-40`: 符号付き 10 進整数を文字列全体で parse し、`strtoll` のエラー・範囲外を拒否する `env_int` の実装。
- `src/split/src/engine_common.cu:1049-1058,1125-1135,1191-1197`: `verify_rows()` の入力確認、cache miss 側の分岐、static 読み取り、stderr 出力とログ項目。
- `src/split/src/engine_common.cu:238-245,260-277,279-288`: `FNX_PRECAP` の backend 別既定値と、cache hit/miss・遅延 capture の分岐。本変数とは独立した設定。
- `src/split/CMakeLists.txt:1-7,64-80,92-120`: split engine の用途、Linux CUDA/HIP のビルド条件、対象ソースと executable。
- `src/split/src/batch.cpp:125-141`: batch decode から `Engine::verify_rows()` を呼ぶ経路。
- `src/split/tools/sfnx.cpp:1027-1035,1084-1093`: 要求処理中の例外を `ERR` と stderr の失敗ログに出し、終了する経路。
