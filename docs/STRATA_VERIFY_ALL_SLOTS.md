# `STRATA_VERIFY_ALL_SLOTS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

SYCL 版 `strata generate` のプロファイルから GPU expert cache をパイプライン充填した後、充填した各 slot の内容を GGUF の元データと照合する診断用フックです。通常の生成機能や cache 方針を切り替える変数ではなく、読み戻し・比較と stderr の診断出力を追加します。検査対象は cache 全容量ではなく、この fill で実際に登録された `fills` の各 slot です。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 検査関数を設定しない |
| 空文字を含む、何らかの値が設定済み | 検査を有効化 |

判定は `std::getenv("STRATA_VERIFY_ALL_SLOTS") != nullptr` のみです。値の内容、先頭文字、数値としての妥当性は調べません。したがって `0`、`false`、空文字も有効です。値の parse、無効値時の fallback、clamp はありません。

## 有効になる条件

SYCL の生成コードで、プロファイルが空でなく、expert source が GGUF source (`srcp == &gguf_src`) である場合に fill 処理へ進みます。そのうち、次のすべてを満たすパイプライン fill の場合だけ、この変数が検査関数を設定します。

- `--stream-experts` が有効で `--mmap-experts` が無効のため、`gguf_src` が fill 元として選ばれている。
- per-layer admission が無効 (`!per_layer`)。
- `STRATA_FILL_SERIAL` が未設定。これは値ではなく設定有無で serial fill を選ぶため、空文字でも piped 経路から外れます。

このため、変数を設定しても、非 SYCL の実装、GGUF 以外を fill 元にする経路、per-layer admission、serial fill ではこの検査は行われません。`STRATA_VERIFY_ALL_SLOTS` の読み取り箇所は `sycl/src/program/generate.cpp` の一か所です。

## 実行時の詳細

パイプライン fill 完了後に `verify_all_slots("after the fill")` を呼び、さらに session の初期化が済んだ位置で `verify_all_slots("session up")` を呼びます。各回で SYCL queue を待ってから、各 slot について GGUF の expert blob を host buffer に読み、device slot を別の host buffer へ同期コピーし、`memcmp` で全 byte を比較します。GPU cache への読み出し結果が元 GGUF と同一かを見る byte 単位の確認です。検査が有効な場合は、この読み直しと device からの全 slot readback が2回分発生します。

差異があれば、fill 順の index、layer/expert、slot、slot address、異なる byte 数、最初と最後の差異位置を stderr に出します。各回の最後には GGUF と異なる slot 数と最初の不一致 fill index を出します。該当ログの形式は `strata generate: STRATA_VERIFY_ALL_SLOTS (%s): ...` です。GGUF の再読み込みに失敗した場合も bad slot 数に加算されますが、その失敗自体の専用行は出さず、最終集計に反映されます。

不一致時には、別変数 `STRATA_VERIFY_FIND` が設定されていれば最初の2件まで blob 内を走査し、誤ったデータが別 expert にあるかを診断します。また `STRATA_VERIFY_DUMP` が設定されていれば、最初の不一致 slot について `<値>/slot<slot番号>.got` と `.want` を書こうとします。これらは本変数の比較処理内で参照される補助診断です。

## 資料との照合

`docs/INTEL.md` は Arc A770 で expert cache の高位 slot が NaN になる事象について、`STRATA_VERIFY_ALL_SLOTS` による readback が GGUF の bytes と一致したと記述しています。また Arc Pro B70 のページエイリアス調査で、この変数と補助変数を使って alias を発見した経緯を記載しています。これらは同文書にある調査記録であり、ここでは測定や再現を行っていません。

## 根拠

- `sycl/src/program/generate.cpp:4273-4290` — `--stream-experts` かつ `!--mmap-experts` で `gguf_src` が選ばれる条件。
- `sycl/src/program/generate.cpp:4721-4735` — `verify_all_slots` の宣言、profile fill の前提、pipelined fill 条件と `STRATA_FILL_SERIAL` の判定。
- `sycl/src/program/generate.cpp:4791-4835` — 設定有無による有効化、全 `fills` の GGUF / device slot 比較、不一致・集計ログ、fill 直後の呼び出し。
- `sycl/src/program/generate.cpp:4809-4825` — `STRATA_VERIFY_FIND` と `STRATA_VERIFY_DUMP` の補助処理。
- `sycl/src/program/generate.cpp:5423-5425` — session 初期化後の2回目の検査呼び出し。
- `docs/INTEL.md:718-725,759-767` — SYCL expert cache の readback 検証に関する調査記録。
