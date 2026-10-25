# `STRATA_VERIFY_ARENA`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena をロードした後、その読み込み内容の FNV-1a 64-bit checksum を stderr に表示する診断用フックです。値を検証したり読み込みを拒否したりはせず、checksum と arena サイズを出力するだけです。コメント上も checksum を比較するテスト用とされています。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_VERIFY_ARENA") != nullptr` だけで判定します。

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | checksum を出さない |
| 設定済み（空文字を含む） | checksum を出す |

`0`、`false` なども、空文字も、設定されていれば同じ扱いです。数値変換、大小文字比較、値域制限はありません。

## 有効になる条件

CUDA/HIP では `--mmap-experts` を使わず、`ArenaExpertSource::open()` で arena を読み込む経路で有効です。`--mmap-experts` の経路は `FileExpertSource` を使うため、この環境変数による checksum は出ません。SYCL でも `--mmap-experts` の経路と、`--stream-experts` かつ `--mmap-experts` なしで GGUF から直接 stream する経路では arena を開かないため対象外です。

対象の arena 読み込みは、pack の `experts.bin` から、または native pack でそのファイルがなく GGUF shard から行われます。レイアウト不一致、入力ファイルのサイズ不一致、arena の確保失敗、読み込み失敗、読み込み byte 数の不一致がある場合は `open()` がそこで失敗するため checksum 出力まで到達しません。CUDA/HIP、SYCL の両実装に同じ設定有無判定があります。

## 実行時の詳細

`ArenaExpertSource::open()` は読み込み処理の後に環境変数を参照し、成功した読み込み byte 数が期待値 `want` と一致した場合だけ checksum を計算します。arena の `want` byte 全体を FNV-1a 64-bit（初期値 `1469598103934665603`、乗数 `1099511628211`）で走査します。ログ形式は次のとおりです。

```text
strata generate: expert arena checksum %016llx (%.2f GiB)
```

checksum は16桁の16進表記、サイズは GiB 単位の小数2桁です。値は読み込みデータの出力後にだけ計算され、arena の内容、pinning、I/O 経路、モデル実行を変えません。判定結果を static cache せず `open()` ごとに環境を読みます。Strata 内の他の箇所からこの名前を読むコードは確認できません。

## 根拠

- CUDA/HIP: `src/core/expert_source.cpp:4713-4721`（byte 数確認、環境判定、ログ）、`src/program/generate.cpp:4821-4838,4901-4902`（arena 経路と mmap 経路の選択）。
- SYCL: `sycl/src/core/expert_source.cpp:3504-3512`（byte 数確認、環境判定、ログ）、`sycl/src/program/generate.cpp:4273-4291,4323-4344`（stream/mmap/arena 経路の選択）。
- checksum: `include/strata/core/pinned.hpp:171`（初期値）、`src/core/pinned.cu:332-339`（FNV-1a 64-bit の処理）。SYCL 実装も `sycl/src/core/pinned.dp.cpp:287-294` にあります。
- `docs/DETAILS.md` と README 類に、この環境変数の利用者向け説明は見つかりませんでした。
