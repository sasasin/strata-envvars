# `--mtp-q4`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--mtp-q4` |
| 別名 | なし |
| 値 | `all`、`proj`、`head` のいずれか。値は必須 |
| 既定値 | 未指定時は無効（空文字列） |

## 役割

MTP draft 層の一部の重みを Q4_0 に変換したコピーで実行し、draft 1 ステップあたりに読むデータ量を減らすための opt-in 設定です。draft 層だけに作用し、target 側の検証処理が各 token を決定します。したがって、このオプションが target の重みや検証窓を Q4_0 にするわけではありません（`include/strata/core/mtp.hpp:64-67`）。

## 使い方

```sh
strata --pack PACK --native MODEL.gguf --mtp MTP_DIR --spec 4 --mtp-q4 all --tokens "1,2,3"
```

`PACK`、`MODEL.gguf`、`MTP_DIR`、token 列は実行環境に合わせて置き換えます。`--mtp` で MTP を指定し、`--spec` を 2 以上にして MTP を使う実行で指定してください。

## 値と既定値

- `all`: Q8_0 の draft projection と、利用可能な draft head の token subset の両方を Q4_0 化します。
- `proj`: Q8_0 の projection を Q4_0 化します。
- `head`: draft head の token subset を Q4_0 化します。
- オプションを省略すると無効です。parser は繰り返し指定を蓄積せず値を代入するため、複数回指定した場合は最後の値が残ります（`src/program/generate.cpp:3271-3276`）。
- 値がない場合は `--mtp-q4 needs a value` を stderr に出して終了コード 2、上記以外の値は `strata generate: --mtp-q4 takes all, proj or head` を stderr に出して parser が 2 を返します（`src/program/generate.cpp:3005-3007,3271-3276`）。SYCL parser も同じ値を受理し、同様に終了コード 2 で拒否します（`sycl/src/program/generate.cpp:1780-1782,1994-1999`）。

## 実行時の動作

`--mtp` がある経路で、`--spec < 2` の場合は MTP 自体を無効化して `o.mtp` を空にします。その後、MTP が残っている場合に `--mtp-q4` の値から projection 用・head 用のフラグを設定し、MTP のロードへ進みます。従って `--mtp-q4` 単独、または `--spec` が 2 未満で MTP が無効になった実行では、この設定による変換は行われません（`src/program/generate.cpp:6281-6298`）。

`all` は projection と head の両フラグ、`proj` は projection のみ、`head` は head のみを有効にします。通常版の `src/core/mtp.cpp` と SYCL 版の `sycl/src/core/mtp.cpp` は、`dense.bin` 内の `q8_0` かつ列数が 32 の倍数の tensor を読み、Q8_0 から float へ展開して Q4_0 に量子化した device buffer を作成します。MTP の projection 読み出しは Q4_0 コピーがある名前についてそのコピーを選び、ない場合は Q8_0 原本を使います（`src/core/mtp.cpp:195-230,323`; `src/core/mtp.cpp:197-201,928-933`; SYCL: `sycl/src/core/mtp.cpp:195-221,343`; `include/strata/core/mtp.hpp:64-67`）。このコピーは追加 device memory を使います。

head 側は draft vocabulary の subset をロードして作る経路で、その subset 行を Q4_0 に変換します。subset が見つからず head の全体を使う経路では `make_q4_head` の呼び出しに入らないため、`head` を指定しても head の変換が行われない場合があります（`src/core/mtp.cpp:730-779`; SYCL: `sycl/src/core/mtp.cpp:750-788`）。変換後の draft head は Q4_0 として読み出されます（`src/core/mtp.cpp:253-257,1240-1243`; SYCL: `sycl/src/core/mtp.cpp:253-258,1140-1144`）。

MTP の prompt 用 batched K/V pass は Q8_0 原本を維持します。Q4_0 コピーを使うのは draft step の重み読み出しです（`include/strata/core/mtp.hpp:64-67`; `src/core/mtp.cpp:928-933`; `sycl/src/core/mtp.cpp:945-948`）。

## 適用条件と副作用

- MTP をロードするには `--mtp` と `--spec` が必要で、`--spec` が 2 未満だと MTP は無効になります（`src/program/generate.cpp:6281-6298`; SYCL: `sycl/src/program/generate.cpp:4286-4303`）。
- `all` と `proj` は `dense.bin` の Q8_0 projection を変換します。ビルドに `STRATA_NATIVE_EXPERTS` / ggml support がない場合は `mtp: --mtp-q4 needs a build with native experts (ggml)` で失敗します（`src/core/mtp.cpp:205-236`; SYCL: `sycl/src/core/mtp.cpp:195-227`）。同じ build 条件は head 変換にも適用されます（`src/core/mtp.cpp:240-263`; SYCL: `sycl/src/core/mtp.cpp:231-263`）。
- 変換用 device memory の確保に失敗すると `mtp: the Q4_0 projections do not fit`、Q4_0 head subset の変換時には入力形式を読めない場合、head の読み取り・書き込みに失敗した場合にそれぞれ対応する `mtp:` エラーを返します（`src/core/mtp.cpp:227-260`; SYCL: `sycl/src/core/mtp.cpp:217-261`）。
- SYCL 版で `head` または `all` を使い、head が planar Q6_K の場合、誤った subset を黙って使わないよう `STRATA_Q6_PLANAR=0` を要求してロードを拒否します。エラーは `mtp: --mtp-q4 head needs the packed Q6_K head layout (STRATA_Q6_PLANAR=0)` です（`sycl/src/core/mtp.cpp:231-243`）。関連設定は [STRATA_Q6_PLANAR 文書](../../../envvars/STRATA_Q6_PLANAR.md) を参照してください。
- 通常版 `src/core/mtp.cpp` と SYCL 版でコード経路・制約が異なります。Metal build は通常版 loader 内で `metal_engine::mtp_load` に委譲しており、この経路から `--mtp-q4` の処理を確認できないため、Metal での効果は本調査では確定していません（`src/core/mtp.cpp:265-273`）。

## 出力とエラー

Q4_0 projection 変換に成功すると stderr に `strata mtp: --mtp-q4: <件数> projections as Q4_0 (<MiB> MiB)`、head subset の変換に成功すると対象 token 数と 1 step あたりの読み込み量を示す行を出力します（`src/core/mtp.cpp:227-230,253-257`; SYCL: `sycl/src/core/mtp.cpp:217-221,253-258`）。MTP load が失敗した場合、呼び出し側は `strata generate: <mtp error>` を stderr に出して終了コード 1 を返します（`src/program/generate.cpp:6298`; SYCL: `sycl/src/program/generate.cpp:4303`）。

## 根拠

- `src/program/generate.cpp:912-914,1071,3271-3276,6281-6298` — option の既定値・help・parser・MTP 設定と load。
- `include/strata/core/mtp.hpp:64-67` — Q4_0 コピーの目的、draft-only の範囲、prompt K/V pass の例外。
- `src/core/mtp.cpp:195-263,323,699-790,928-933,1240-1243` — 通常版の projection/head 変換と使用箇所。
- `sycl/src/program/generate.cpp:731-733,862,1994-1999,4286-4303` — SYCL parser と MTP load。
- `sycl/src/core/mtp.cpp:195-263,343,750-799,945-948,1140-1144` — SYCL projection/head 変換、planar Q6_K 制約と使用箇所。

調査範囲は上記 revision の parser とソース上の実行経路です。同一 revision の CLI バイナリ help、各 backend の実機挙動、Release 配布物は確認していません。
