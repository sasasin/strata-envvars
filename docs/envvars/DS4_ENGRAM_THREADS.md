# `DS4_ENGRAM_THREADS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンの Engram 行読み取りに使う reader thread 数を指定します。モデルに Engram layer が含まれる場合、行読み取り用の `EgReader` をこの数のスレッドで開始します。スレッドはキューに投入された行読み取りを分担します。

この機能は専用ターゲット `strata-dsv41` の経路です。`STRATA_BUILD_DSV41` は CMake で既定 OFF であり、通常の `strata` 実行経路とは別にビルドされます。

## 値と判定

値は `std::atoi` で整数へ変換し、結果に下限 1 を適用します。文字列全体の妥当性検査はありません。

| 環境変数の状態・値 | `nth`（reader thread 数） |
|---|---|
| unset | `hardware_concurrency()` を 1 以上としてから 2 で割り、4 以上 16 以下に制限した値。式は `min(16, max(4, max(1, hw) / 2))` |
| 空文字 | `atoi` が 0 を返し、下限により 1 |
| 数字で始まらない文字列 | `atoi` が 0 を返し、下限により 1 |
| 整数として読める文字列 | `max(1, atoi(value))`。たとえば `8tail` は 8、`-3` と `0` は 1 |

`atoi` のため、先頭の空白と符号は許容され、数値の後ろにある文字は判定されません。大文字小文字の比較はありません。`int` の範囲を超える値に対する `atoi` の結果は移植可能な仕様として保証されないため、使用できる値域として扱えません。

## 有効になる条件

- `strata-dsv41` がビルドされ、DeepSeek-V4.1 のモデル読み込み経路が実行される必要があります。CMake オプション `STRATA_BUILD_DSV41` は既定で OFF です。
- モデルに Engram layer がある場合（`pk.eg_layers > 0`) に限り、変数を読み取り、reader を開始します。Engram layer がないモデルではこの読み取り・スレッド起動ブロックを通りません。
- 設定値が 1 以上でも、Engram の読み取り要求が存在しない限り worker は仕事をしません。

## 実行時の詳細

モデル初期化中、Engram layer 数を確認した後に環境変数を読みます。未設定なら CPU の `hardware_concurrency()` を基にした既定値を使い、設定されていれば `atoi` 後の値を最低 1 にします。その値を `eg_io.start(paths, nth, eg_direct)` に渡し、`EgReader::start` が `nth` 個の `std::thread` を生成します。設定はモデル初期化時にこの箇所で読み取られるため、モデル読み込み後の環境変更は既に開始した reader のスレッド数を変えません。

Engram 行の読み取り要求は、行キャッシュにない行を reader の共有 FIFO キューへ入れ、worker thread がファイルから読みます。通常の処理ではトークンが分かった段階で読み取りを依頼し、該当レイヤーで結果を集めます。チャンク化 prompt 経路では次の chunk の Engram 行を非同期で読み、chunk の処理前に完了を待ちます。したがって、この環境変数が直接変えるのは読み取り worker 数です。キャッシュの容量は別変数 `DS4_ENGRAM_CACHE_MB` で決まります。

`-v` が有効なモデル読み込みでは、stderr に `ds4: Engram rows read on %d threads, issued with the tokens, collected before their layer; row cache %llu MB (%zu rows)` が出力され、採用された thread 数を確認できます。環境変数の不正値専用の警告やエラーは実装にありません。

## 根拠

- `CMakeLists.txt:797-810` — DSV41 用の独立ターゲットと `STRATA_BUILD_DSV41` の既定 OFF。
- `src/dsv41/ds4_model.cu:2497-2512` — Engram layer 条件、既定 thread 数、`getenv` / `atoi` / 下限、および reader 初期化。
- `src/dsv41/ds4_model.cu:2577-2580` — verbose 時の採用 thread 数を含む stderr ログ。
- `src/dsv41/ds4_engram_io.hpp:129-170,180-205` — 指定数の worker 生成、キュー処理とファイル読み取り。
- `src/dsv41/ds4_model.cu:5474-5478,5554-5558,5560-5593` — cache miss の読み取り依頼と完了待ち・キャッシュ格納。
- `src/dsv41/ds4_model.cu:7675-7689` — chunked prompt 経路での Engram 読み取りと chunk 処理前の待機。
