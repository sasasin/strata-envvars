# `STRATA_INJECT_FATAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の GPU エンジンで、指定した正の回数に達した fatal GPU error 確認時に、実際の illegal memory access と同じ終了経路を意図的に発生させる診断・テスト用フック。コメントも `test hook` と説明している。成功した decode 結果を加工する設定ではなく、発火すると現在の engine プロセスを終了させる。実装は `exit_if_gpu_fatal` と `exit_gpu_fatal`（`engine/src/program/generate.cpp:3622-3645`）。

## 値と判定

`exit_if_gpu_fatal` 内の関数ローカル `static const long` を初期化するとき、`std::getenv` の結果を `std::atol` に渡す。環境変数が未設定なら `0L`。設定済みの空文字も `atol("")` が 0 となる。変換後の値が `> 0` の場合だけカウンターを進めて一致を判定する。`atol` は10進数として先頭の空白と符号を許し、数字の後ろの文字列を検査しないため、`2abc` は 2、`  +2` は 2、`true`・`false`・`abc`・空文字・`0anything` は 0。`-2` は負値なので発火しない。数値変換エラーの検査や範囲検査はなく、`long` の範囲を超える文字列の結果はコード上保証されない。大文字小文字の比較は行わない。

| 条件 | unset | 有効になる値 | 発火しない値 |
|---|---|---|---|
| CUDA/HIP 系 `strata` の `--serve` engine | 0（無効） | 変換結果が正の `long`（例: `1`, `+2`, `2abc`） | 0 以下（例: 空文字、`0`, `0anything`, `-1`, `true`, `abc`） |
| 独立した SYCL / Metal engine | 対象ソースに読み取り実装なし | 該当なし | 変数名を読む処理がない |

根拠: `engine/src/program/generate.cpp:3634-3637`、CUDA/HIP 側で同ファイルを `strata` 実行ファイルにする箇所 `engine/cmake/strata_gpu_engine.cmake:548-551`。SYCL は独立したプロジェクトとして分岐し `engine/sycl/` を使い、Metal も別プロジェクト（`engine/CMakeLists.txt:23-32`）。候補名の全参照検索では実装読み取りは `generate.cpp:3635` の一箇所で、SYCL / Metal のコピーには見つからない。

## 有効になる条件

- `generate.cpp` の CUDA/HIP 系 `strata` を使用する。変数名の読み取り実装は独立した SYCL / Metal engine にはない（`engine/CMakeLists.txt:20-32`、`engine/cmake/strata_gpu_engine.cmake:548-551`）。
- `exit_if_gpu_fatal` が呼ばれる `--serve` の engine 経路に入り、読み取り値が正で、カウンターがその値に一致する必要がある。通常の decode では各 window の `ver.run` 前に呼ばれる（`engine/src/program/generate.cpp:22986-22993`）。
- 一致時に `STRATA_INJECT_FATAL_ONCE` が設定され、かつその値が空でない場合、値をファイルパスとして扱う。ファイルがすでに開ければ注入を抑止する。ファイルが開けず、新規作成も失敗した場合でも `fire` は true のままなので注入する。ファイルが存在せず作成できれば、作成して今回注入する（`engine/src/program/generate.cpp:3637-3645`）。この補助変数は本変数の正値判定後にだけ読まれる。
- CLI 引数や設定ファイルによる上書きはこの読み取り処理にはない。環境変数は helper の初回呼び出し時に一度だけ読み込まれ、同じプロセス内での環境変更は反映されない（`engine/src/program/generate.cpp:3634-3637`）。

## 実行時の詳細

値が正なら、`exit_if_gpu_fatal` の呼び出しごとに `windows` が増え、一致時に CUDA runtime の sticky error を確認する前に注入分岐へ入る。通常の decode は `ver.run` 前の一回が decode-window カウンターとして働くが、同じ関数は warm-up 失敗時、decode 失敗時、commit 失敗時などにも呼ばれる。そのため異常経路では呼び出し回数が decode window 数と一致しないことがある。注入後は `ver.run` を実行せず、その engine プロセスを即時終了する（`engine/src/program/generate.cpp:3636-3648, 16383-16387, 22986-22993, 23066-23070, 23346-23350`）。

発火時の stderr は `strata serve: fatal GPU error (injected (STRATA_INJECT_FATAL): an illegal memory access was encountered): the engine ends so that the server can start it again`、stdout は `ERR fatal GPU error: injected (STRATA_INJECT_FATAL): an illegal memory access was encountered`。両ストリームを flush して `std::_Exit(3)` するため、通常の stack unwinding / destructors は行われない（`engine/src/program/generate.cpp:3627-3632, 3645`）。server は engine の終了を request failure として扱い、次の request で engine を再起動する経路を持つ（`terminal/serve/server.py:1181, 2851, 2898`）。

## ログと測定値

上記の stderr / stdout の文言と終了コード 3 が発火時に観測できる。性能値や生成 token の差を測定・記載する対象ではない。フックが有効でも発火条件に達する前は通常の処理が続く。

## 根拠

- 値の読み取り、変換、static cache、カウンター、補助変数、発火条件: `engine/src/program/generate.cpp:3634-3648`
- fatal 時のログ、flush、即時終了: `engine/src/program/generate.cpp:3627-3632`
- decode 前の呼び出しと失敗・commit 経路: `engine/src/program/generate.cpp:22986-22993, 23066-23070, 23346-23350`
- CUDA/HIP `strata` target と別 backend の構成: `engine/cmake/strata_gpu_engine.cmake:548-551`, `engine/CMakeLists.txt:20-32`
- server の engine death と再起動メッセージ: `terminal/serve/server.py:1181, 2851, 2898`
