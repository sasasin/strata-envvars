# `STRATA_PRIVATE_IQ4_HEAD_SOA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL の B60 private weight cache で kind `24` を選ぶスイッチです。kind `24` は IQ4 head weight の raw 配列を、16 行単位にパディングした SOA cache に変換して保存し、条件に合う Battlemage の IQ4 head MMVQ からその cache を使います。環境変数だけではこの経路は成立せず、head の形状・actor 状態・packed 状態なども必要です（`engine/sycl/include/b60_weight_cache.hpp:5-8`; `engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:136-173`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3716`）。

対象は SYCL 実装です。CPU/CUDA/HIP の同名読み取りは確認できませんでした。このスイッチ専用の CLI 引数やログはありません。

## 値と判定

`b60_cache_requested(24)` が環境変数名を選び、`std::getenv(name)` の結果が存在し、先頭文字が `'1'` の場合だけ true です。文字列全体や数値としての妥当性は検査しません。未設定・空文字・先頭が `1` 以外なら false です。比較は大文字小文字を変換しません（`engine/sycl/include/b60_weight_cache.hpp:5-8`）。

| ビルド / 経路 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| SYCL、kind `24` の cache 判定 | 無効 | `1`, `1anything`, `10` | 空文字, `0`, `true`, ` 1`, `True` |

この値判定自体に数値境界はありません。`1` で始まる任意の文字列が有効です。

## 有効になる条件

- **通常の出力 head cache:** B60 layout 準備が走り、`last == 48` であること。`Layouts::add_device` は `output.weight` を cache 候補にし、native head がロード済みで type `23`、row bytes `1360`、参照 weight の寸法が `ne0=2560, ne1=248320` であることを要求します。native head の device USM 所有者も対象 device と一致する必要があります。違反すると `B60 native head cache source` または `B60 native head cache USM device ownership` の例外になります（`engine/sycl/include/b60_layout_host.hpp:81-100`）。
- B60 layout は `STRATA_PRIVATE_B60_DECODE_LAYOUT` と `STRATA_PRIVATE_BMG_SINGLE_ACTOR` が両方有効な単一デバイス経路、または固定条件の 2-stage 経路で準備されます。単一デバイス経路は serve、native pack、単一 GPU、pipeline windows 無効、no-prefill-borrow、batch 0、prompt cache 0、spec `<=6`、48 layer / 512 expert / embedding 2560 / FFN 640 / HC 4 / HC-LR 320 に加え、`STRATA_VERIFY_NO_HOST=1`、`STRATA_VERIFY_DEVICE_PLAN=1`、`STRATA_PRIVATE_PACKED_REGISTER=1` を要求します。2-stage 経路も native pack、2 stage、no-prefill-borrow、batch 0、prompt cache 0、spec `<=6`、同じモデル形状などを要求し、`STRATA_PRIVATE_PACKED_REGISTER` の先頭が `1` であることを個別に検査します（`engine/sycl/src/program/generate.cpp:4590-4597,8035-8046`）。
- **MTP draft head cache:** draft vocab ファイルから部分 head を作成する経路で、部分 head が type `23`、106299 行、row bytes `1360` であり、`q4_head_` が false の場合に準備します。cache 要求があるのにこの固定形状に合わないと `B60 exact draft cache requires the fixed raw IQ4 subset` を投げます（`engine/sycl/src/core/mtp.cpp:820-865`）。
- **実際の kernel 選択:** `native_iq4_xs_mmvq` が Battlemage 上で、cache flag が有効、入力幅 `n_in=2560`、かつ actor / packed 条件と寸法が合う場合に cache lookup します。main actor は packed weight + `n_out=248320, ncols=4`、main 以外の actor は single-actor モード + `n_out=106299, ncols=1` が必要です。該当経路で cache が見つからない場合は `B60 missing exact head decode cache` を投げ、通常 kernel には fallback しません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3716`）。
- B60 layout や該当 MTP draft head の準備が行われないモデル・実行経路、Battlemage 以外、異なる head 寸法では、値が有効でもこの SOA kernel 選択は起きません。CPU backend などこの SYCL 実装を使わない経路にも適用されません。

## 実行時の詳細

この変数の判定関数は `static` に保存せず、`b60_cache_requested(24)` が呼ばれるたびに `getenv` します。main head では layout 準備中に cache 条件を調べ、MTP draft head では部分 head の生成時に調べます。値を変えた場合、その後の判定には反映され得ますが、すでに作成済みの cache は自動で作成・破棄し直されません。したがって準備時と MMVQ 実行時で値が食い違い、後から有効にしたのに cache がない場合は上記 missing-cache 例外になります（`engine/sycl/include/b60_weight_cache.hpp:5-8`; `engine/sycl/include/b60_layout_host.hpp:95-107`; `engine/sycl/src/core/mtp.cpp:858-864`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3716`）。

`b60_make_weight_cache` は kind `24` について列数 2560、行数 248320 または 106299 を受け付け、行数を 16 の倍数へ切り上げた領域を device memory に確保します。cache 用領域をゼロ初期化し、raw IQ4 bytes を SOA 配列へ並べ替え、ordered SYCL queue で完了を待ってから raw pointer と kind の組で登録します。allocation 失敗は `std::bad_alloc`、対応外の形状・queue などは例外になります。cache は対応する raw weight の owner が解放される際に release されます（`engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-183`; `engine/sycl/include/b60_layout_host.hpp:104-107,137`; `engine/sycl/src/core/mtp.cpp:199-206,858-864`）。

CLI 引数や別の値による優先上書きはありません。ただし `STRATA_PRIVATE_B60_DECODE_LAYOUT`、`STRATA_PRIVATE_BMG_SINGLE_ACTOR`、`STRATA_PRIVATE_PACKED_REGISTER`、`STRATA_PRIVATE_B60_NEXT_POOL` などの状態・設定が、cache 準備や使用可能な kernel 分岐に関わります。`STRATA_PRIVATE_B60_NEXT_POOL` が有効で、追加の device / actor 条件に合えば draft head は leaf-pairs、main head は leaf-quartets probe を選び、それ以外は head SOA probe を選びます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3716`）。

## ログと測定値

MTP draft cache の準備成功時は stderr に `B60_DRAFT_CACHE device=%d bytes=%llu` が出ます。B60 layout の cache 準備では一般ログ `B60_CACHE device=%d matrices=%zu cumulative_bytes=%llu` に cache 件数と累積 bytes が含まれますが、このログは当該変数だけの有効化を示しません（`engine/sycl/src/core/mtp.cpp:858-864`; `engine/sycl/include/b60_layout_host.hpp:104-107`）。

この変数固有の成功・無効値警告はありません。cache 準備形状の検査、allocation、kernel 内の cache 欠落は、それぞれ上記の例外経路で観測できます（`engine/sycl/include/b60_layout_host.hpp:95-100`; `engine/sycl/src/core/mtp.cpp:858-860`; `engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:136-148`; `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3711-3712`）。この checkout の資料には本変数による性能測定値を確認できませんでした。

## 根拠

- `engine/sycl/include/b60_weight_cache.hpp:5-8` — kind `24` と環境変数の対応、先頭文字判定。
- `engine/sycl/include/b60_layout_host.hpp:81-100,104-107,137` — native output head の選択・検査、cache 作成ログ、解放。
- `engine/sycl/src/core/mtp.cpp:199-206,820-865` — 部分 draft head の作成、形状検査、cache 作成とログ。
- `engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-183` — cache 登録、形状、変換、release。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3716` — Battlemage / actor / 形状条件と cache 使用。
- `engine/sycl/src/program/generate.cpp:4590-4597,8035-8046` — B60 layout の単一デバイス・2-stage 初期化条件。
