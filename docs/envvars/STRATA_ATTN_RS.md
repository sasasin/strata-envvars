# `STRATA_ATTN_RS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 QSA の batched decode attention (`qsa_decode_attn_batch`) で、score/probability の共有メモリ配置と score の head 次元 reduction 実装を選びます。既定の `2` は probability を `[cell][head]` で置き、value phase で各 cell の12 head分を3回の `float4` 読み込みにします。`1` は同じ配置に加えて score の12 head分を reduce-scatter で合計します。どちらも元の演算順を保つ意図の実装で、`0` やその他の値は従来の `[head][cell]` 配置と score reduction に戻します。これは実験用の実装選択であり、ユーザー向け設定としての性能保証はありません。

この環境変数を読む箇所は `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp` の `qsa_decode_attn_batch` だけです。CUDA/HIP の同名機能や `qsa_decode_attn_step` にはこの読み取りはありません。SYCL の verifier、MTP および通常の layer 経路が `qsa_decode_attn_batch` を呼ぶ場合に適用されます。

## 値と判定

値は `std::atoi` で整数に変換され、結果が `1` または `2` と等しい場合だけ対応する専用 kernel を選びます。`atoi` は文字列全体の厳密な検証ではなく、先頭の空白と符号を許し、数字の prefix を整数にします。変換可能な数字がない空文字や `"on"` は `0` 相当です。負値や `1`/`2` 以外の整数、`"2x"` のように prefix が `2` となる文字列は、それぞれの変換結果に従います。

| 設定 | 判定結果 | 選ばれる処理 |
|---|---:|---|
| unset | `2`（既定値） | `[cell][head]` 配置、value phase の3回の vector load |
| `1` または `"1suffix"` | `1` | 上記に加え、score の12 head reduction を reduce-scatter 化 |
| `2` または `"2suffix"` | `2` | `[cell][head]` 配置、score は通常の warp reduction |
| 空文字、`0`、変換結果が1/2以外 | その他 | 従来の `[head][cell]` 配置と通常の warp reduction |

## 有効になる条件

- この読み取りは SYCL 実装の `qsa_decode_attn_batch` 内にあります。ビルドでこの SYCL 実装が使われ、その関数が呼ばれた場合にのみ影響します。
- 同じ関数が `STRATA_ATTN_LANECELL` を先に確認します。そちらが設定され、先頭文字が `'1'` なら lane-cell kernel を選び、`STRATA_ATTN_RS` の `1`/`2` による分岐は使われません。`STRATA_ATTN_LANECELL` はこの関数内で別途 static cache されます。
- `kv_mode` は KV pool pointer から選ばれ、選択された RS kernel は mode 0–3 ごとに特殊化されます。環境変数が変えるのはこの kernel 分岐であり、KV mode 自体ではありません。
- `qsa_decode_attn_batch` の入力 geometry/buffer 検査を通過する必要があります。不正な geometry や必要 buffer の欠落時は stderr に `qsa_decode_attn_batch: unsupported geometry or missing buffers` を出して終了します。

## 実行時の詳細

`rs_on` は関数内の `static const int` です。最初に `qsa_decode_attn_batch` に入ったとき環境変数を一度読み、以降の呼び出しでは値を再読しません。したがって、その初回呼び出し後にプロセス環境を変更しても反映されません。

`rs_on == 1` と `rs_on == 2` はそれぞれ `attn_chunk_kernel<M, false, V>` の SYCL kernel を起動します（`M` は検出された KV mode、`V` は RS variant）。`RS != 0` の kernel は score/probability 配列を `[cell][head]` として扱い、value phase で head 12個分の確率を3つの `float4` として読みます。`RS == 1` の score phase は、12 head の warp sum を16 shuffle の reduce-scatter で実行します。`RS == 2` は各 head に対して通常の warp sum を行います。それ以外の値では共通の従来 kernel を KV mode ごとに起動します。環境変数の値自体に対するログ出力は見つかりません。

## 文書と測定値

`docs/INTEL.md` は Arc Pro B70、IQ3_S の 4,095-token prompt、32K config、`--prefill 4096`、3ラウンド interleaved median の記録として、RS=2 が 1,254→1,265 prompt tok/s（+0.9%、3/3 round）、RS=1 が 1,254→1,236（-1.5%）と記載しています。同じ表は RS=2 の first-token logits md5 が 4K/16K で一致したと記載します。これは当該資料の測定記録であり、他の GPU、モデル、設定での性能・一致性を保証するものではありません。

## 根拠

- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:648-669`: 対象関数、入力検査、KV mode、`STRATA_ATTN_LANECELL` の読み取り。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:707-764`: `STRATA_ATTN_RS` の `atoi` 読み取り、既定値2、RS=1/2と lane-cell 優先分岐。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:151-152,222-294,357-370`: probability 配置、RS=1 の reduce-scatter、従来 score reduction、RS variant の value accumulation。
- `sycl/src/core/verify.cpp:1256,1270`, `sycl/src/core/mtp.cpp:968`, `sycl/src/core/layer.cpp:1311`: SYCL の呼び出し経路。
- `docs/INTEL.md:1009-1019`: B70 の測定条件と結果。
