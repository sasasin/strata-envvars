# `STRATA_SYCL_IQ4_T4_ESIMD`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の native MMVQ が IQ4_XS（GGML type 23）を処理するとき、条件が揃えば 4 列用の ESIMD カーネル `launch_iq4_esimd_t4` を選びます。これはモデル全体や IQ4_XS の全呼び出しを切り替える設定ではなく、Battlemage 上の特定 shape・配置を持つ呼び出しに限った opt-in のカーネル選択です。type 23 は `native_mmvq` から `native_iq4_xs_mmvq` へ渡されます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4220`）。

## 値と判定

`native_iq4_xs_mmvq` 内の関数ローカル `static const bool` 初期化子で `std::getenv` を呼び、環境変数が存在し、かつ先頭バイトが文字 `'1'` の場合だけ true になります。文字列全体の比較や数値変換はありません。未設定・空文字は無効です。大文字小文字、後続文字、空白、数値としての妥当性は検査されません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3758`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL native MMVQ の IQ4_XS dispatch | 無効 | `1`、`1anything` | 空文字、`0`、`01`、`true`、` 1`、`-1` |

## 有効になる条件

- SYCL の `native_iq4_xs_mmvq` に IQ4_XS が渡されること。CUDA 実装や他の量子化型を切り替えるものではありません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3700,4203-4220`）。
- 対象デバイスの世代が Battlemage で、`ncols == 4`、`n_in` が `2560` または `6144`、weights と Q8_1 activation の各ポインターが 64-byte 境界に整列していること。出力行数 `n_out` はこの分岐では個別に制限されませんが、先行する native MMVQ の入力検証では正数である必要があります（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3694-3700,3748-3762`）。
- 先行する Battlemage の packed-weight / cache / exact-int4 分岐に一致しないこと。これらはこの環境変数を調べる前に kernel を起動して return します。該当する設定には `STRATA_PRIVATE_IQ4_SSM_SOA=1`、`STRATA_PRIVATE_IQ4_HEAD_SOA=1`、`STRATA_PRIVATE_IQ4_INT4_DPAS=1` があり、packed-weight 経路は `STRATA_PRIVATE_B60_DECODE_LAYOUT=1` または `STRATA_PRIVATE_BMG_SINGLE_ACTOR=1` による actor / layout 状態などにも依存します（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3735`、`sycl/include/b60_weight_cache.hpp:5-8`、`sycl/include/b60_layout_state.hpp:7-20`）。
- `STRATA_SYCL_IQ4_PAIR_REUSE` がこの呼び出しで有効にならないこと。pair-reuse 分岐は対象と同じ Battlemage・4 列・K・alignment 条件を先に満たして return します。この変数は未設定なら有効で、先頭文字が `'1'` なら有効です。したがって通常は `STRATA_SYCL_IQ4_PAIR_REUSE=0` など先頭文字が `'1'` 以外の設定が必要です（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3736-3756`）。
- core layer の `gemv_quantized` が呼ぶ経路では `native_mmvq` に `ncols=1` を渡すため、その呼び出しは 4 列条件を満たしません。実際に 4 列で `native_mmvq` が呼ばれる経路に限って候補になります（`sycl/src/core/layer.cpp:145-157`）。

条件が揃わなければ、この変数による ESIMD 選択は行われず、後続の IQ4 lookup / wide / wave / multi / scalar 系 dispatch が通常の条件で選ばれます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3764-3843`）。また、対象分岐の後には `STRATA_SYCL_IQ4_T4_XMX` の分岐がありますが、対象の ESIMD 分岐に入れば先に return するため、そこで後続分岐は実行されません（同 `:3758-3770`）。

## 実行時の詳細

環境変数はプロセス起動時ではなく、`native_iq4_xs_mmvq` の実行が `esimd_t4` 宣言まで初めて到達したときに読み取られます。C++ の関数ローカル static に保存されるため、その後の呼び出しでは環境を再読せず、実行中に値を変更しても判定は変わりません。pair-reuse 等の先行分岐が先に return する呼び出しでは、この static 初期化自体に到達しません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3762`）。

選択時は K=2560 なら `iq4_e_T<10>`、K=6144 なら `iq4_e_T<24>` を `T=4` で起動します。カーネル本体は IQ4_XS weights と Q8_1 activations を読み、ESIMD の DPAS と reduction を使って出力を書き込みます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4225-4317`、起動選択と K 別 dispatch は同 `:4319-4329`）。この環境変数は演算経路の選択を行います。ソースから出力の同一性や性能差を保証することはできません。

## ログと測定値

この変数の判定や選択を示す専用ログはありません。選択分岐はカーネル起動後に `launch_check()` を呼びますが、その関数内の `error` は `0` に固定されており、この呼び出しで実際の起動エラーを判定する経路はありません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3761-3762,2311-2334`）。Strata の `docs/DETAILS.md` および関連資料に、この変数の条件付き性能測定値は見つかりませんでした。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3758-3762` — 値の読み取り、条件、起動。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3756` — 先行する Battlemage 分岐と pair-reuse の優先順位。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4220,4225-4329` — type 23 dispatch、ESIMD カーネルと K 別起動。
- `sycl/src/core/layer.cpp:145-162` — core layer 呼び出しの列数とエラー伝播。
