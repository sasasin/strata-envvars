# `STRATA_VERIFY_FIND`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `strata generate` の expert cache 検証で、GGUF の expert blob と cache slot の内容に差があったとき、cache に入った誤データが別の expert blob の一部と一致するかを追加で探します。診断用フックです。この変数単独では検証を開始せず、検証結果や生成内容も変更しません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_VERIFY_FIND") != nullptr` だけで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 探索しない |
| 空文字を含む任意の設定値 | 探索を有効にする |

数値変換、文字列比較、大文字小文字の判定、範囲制限はありません。判定結果は static cache されず、不一致を処理するたびに環境を読みます。実装内でこの変数を設定・変更する箇所は見つかりませんでした。

## 有効になる条件

次の条件がそろった検証処理内でのみ参照されます。

- SYCL 実装の `strata generate` を使う。
- profile があり、expert cache の fill が GGUF からの pipelined 経路を使う。コード上、この経路は `srcp == &gguf_src`、per-layer admission ではないこと、および `STRATA_FILL_SERIAL` が未設定であることを条件とします。
- `STRATA_VERIFY_ALL_SLOTS` が設定されていて、全 filled slot の比較関数が登録される。
- 比較で不一致が検出され、累計カウンター `bad` が 2 以下である。`bad` はそれ以前の GGUF 読み出し失敗も数える。
- 最初の相違 byte `fd` の 4096 byte 後から 64 byte を調べられるよう、`fd + 4160 < nb` を満たす。

`STRATA_VERIFY_ALL_SLOTS` が未設定なら、この変数が設定されていても当該比較関数は登録されず、探索は行われません。CUDA/HIP のソースではこの名前の参照を確認できませんでした。

## 実行時の詳細

全 slot 比較は fill 直後と session 起動後に実行されます。各 slot の GGUF blob を `want_b`、cache slot の読み戻しを `got_b` として `memcmp` し、不一致なら `fd` は最初の相違 byte になります。条件を満たすと `got_b + fd + 4096` の 64 byte を probe として取り出し、filled expert 一覧を順に走査します。各 expert blob を GGUF から読み、`memmem` で probe が含まれるかを探します。一致した expert ごとに stderr へ layer、expert、slot、fill index、blob 内 byte offset を出力します。複数 expert に一致する probe なら複数行出力されます。

比較自体の不一致ログと集計ログは `STRATA_VERIFY_ALL_SLOTS` が担います。`STRATA_VERIFY_FIND` の探索で一致がなくても、それ自体のログやエラーにはなりません。この追加探索による終了コード変更もありません。全 slot の読み戻し比較は fill 直後と session up 後に行われるため、条件に合う不一致が残っていれば各回で診断される場合があります。

## 根拠

- `sycl/src/program/generate.cpp:4633-4648` — profile fill と pipelined 経路の条件。
- `sycl/src/program/generate.cpp:4704-4707,4711-4722` — `STRATA_VERIFY_ALL_SLOTS` による比較関数の登録と不一致判定。
- `sycl/src/program/generate.cpp:4722-4733` — `STRATA_VERIFY_FIND` の設定有無、探索条件、probe 検索、stderr の出力。
- `sycl/src/program/generate.cpp:4740-4748,5336-5338` — 不一致ログ、fill 直後と session up 後の比較呼び出し。
- `docs/INTEL.md:745-755` — Arc Pro B70 の cache aliasing 調査で `STRATA_VERIFY_ALL_SLOTS` と `STRATA_VERIFY_FIND` を用いた記録。動作の根拠は上記の現行実装。
