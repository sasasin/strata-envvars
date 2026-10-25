# `STRATA_I8_WG`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL の fused int8 expert カーネルで、gate/up 積と down 積に work-group（WG）版カーネルを選ぶかを制御します。対象は Battlemage 向け ESIMD DPAS int8 経路です。これは環境変数からカーネル全体を有効化するスイッチではありません。int8 経路自体が選ばれた後、各積の実装候補を選びます。

## 値と判定

最初に `wg_for()` が呼ばれた時の `std::getenv("STRATA_I8_WG")` を `std::atoi` で整数化し、関数内の `static const int` に保存します。文字列全体の妥当性検査はなく、`atoi` が先頭から変換できる整数部分を使います。空文字、数字で始まらない文字列、`"0suffix"` は 0、`"2suffix"` は 2、負の整数は負値になります。

| 値 | 判定 | カーネル選択への影響 |
|---|---|---|
| 未設定 | 既定値 1 | work-group 版を候補にする |
| 設定値の `atoi` 結果が 0 | 無効 | work-group 版を候補にしない |
| 設定値の `atoi` 結果が非 0 | 有効 | work-group 版を候補にする |

1 だけを有効値として比較するのではなく、整数化結果の真偽を使います。値は初回評価後にキャッシュされるため、同一プロセス内で環境を変更しても再評価されません。

## 有効になる条件

この変数が参照されるのは `sycl/src/prefill/esimd_moe.dp.cpp` の int8 gate/up または down カーネル選択時です。呼び出し側では、SYCL の prompt prefill が native expert を使い、対象形式・形状に対応し、カーネルがデバイスで利用可能な場合に int8 経路を選びます（`sycl/src/prefill/prefill.cpp:4227-4236`）。したがって `STRATA_I8_WG` だけでは int8 経路や Battlemage 対応カーネルを有効にしません。

WG 版を実際に選ぶには、さらに `a.nkb % 4 == 0` かつ `a.ntiles % WGT == 0` が必要です。gate/up はこれらに加えて `gu_type != T_IQ2S` が必要です。条件を満たさない場合は WG 版ではなく通常版を選びます。通常版では別変数 `STRATA_I8_GRF` の値が 128 のとき 128-register 版、それ以外は 256-register 版になります。down 側の WG 選択には IQ2_S の除外条件はありません。

## 実行時の詳細

`gate_up()` と `down()` はそれぞれ対象形状を検査し、行 tile 高 `MT` を決めた後に `wg_for()` を参照します。WG 分岐に入ると gate/up は IQ3_S または IQ3_XXS 用、down は IQ4_NL または Q2_0 用の WG カーネルを起動し、テンプレートの register 数は 256 です。WG 分岐に入らなければ対応する通常カーネルを起動します。`MT` が 2、4、8 以外なら dispatch が false を返し、積は完了せず呼び出し元の FP16 経路への fallback 対象になります（`sycl/src/prefill/esimd_moe.dp.cpp:978-1013,1015-1048,774-782`）。

この選択に伴う専用ログはありません。int8 積自体が未対応形式・workspace 不足・起動失敗などで完了しなければ、呼び出し元は stderr に理由を含む int8 失敗ログを出し、FP16 chain を使います（`sycl/src/prefill/prefill.cpp:4290-4314`）。

## 根拠

- `sycl/src/prefill/esimd_moe.dp.cpp:763-767`: 未設定時 1、`atoi`、static cache。
- `sycl/src/prefill/esimd_moe.dp.cpp:978-1013`: gate/up の WG 条件、IQ2_S 除外、通常版への分岐。
- `sycl/src/prefill/esimd_moe.dp.cpp:1015-1048`: down の WG 条件と通常版への分岐。
- `sycl/src/prefill/prefill.cpp:4227-4236,4290-4314`: 上位経路での int8 利用条件と失敗時の FP16 fallback。
- `docs/INTEL_INT8_EXPERTS.md:25-27` は `STRATA_I8_WG=0` を non-work-group kernels の指定として説明しています。コードに照らすと、この指定は `atoi` が 0 になる場合に WG 版を候補から外す、という範囲で正確です。非 0 値でも形状条件を満たさない場合と IQ2_S gate/up では通常版になります。
