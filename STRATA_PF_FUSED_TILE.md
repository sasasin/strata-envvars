# `STRATA_PF_FUSED_TILE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

native fused prefill の expert kernel が、一つの work item で扱う routed row 数を選びます。対応する値は 64 行または 128 行です。値を設定しても fused 経路自体は有効にならず、その経路が選ばれたときのタイル幅だけを指定します。

## 値と判定

CUDA と SYCL の native kernel 実装は、`pick_ww()` 内で `std::getenv()` の結果を `std::atoi()` に渡し、結果が 64 なら64行、128なら128行を強制します。それ以外は自動選択です。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 自動選択 |
| 空文字、数値として始まらない文字列 | `atoi` が 0 を返すため自動選択 |
| 数値変換結果が 64 | 64行を強制 |
| 数値変換結果が 128 | 128行を強制 |
| それ以外（負数を含む） | 自動選択 |

文字列全体の一致ではなく、`atoi` が先頭の空白と符号を処理した後に読み取る整数部分で判定します。そのため、たとえば `64suffix` や `128suffix` もそれぞれ該当する値として扱われます。数値部分の後ろは検査されません。int の範囲外の文字列に対する `atoi` の結果は、この実装では別途検査・保証されていません。判定結果は `static const int` に保存されます。

自動選択では、バッチ全体の routed row 数 `n` を expert 数 `n_expert`（最低1として扱う）で割った平均値が **56より大きく112以下**なら128行、それ以外は64行です。

根拠: `src/prefill/moe_fused_iq.cu:1105-1114`、`sycl/src/prefill/moe_fused_iq.dp.cpp:1348-1357`。

## 有効になる条件

- native fused prefill が対象の層で選ばれること。CUDA/SYCL の prefill 呼び出し側では、MMQ または fused-only 対象の層であり、expert の全件を streamed walk で処理でき（`stream_all`）、peer-device 経路ではなく、native layout と型・デバイスが native kernel に対応する場合に native kernel を選びます。
- `stream_all` は ring に STAGE より多くの slot があり、chunk が `stream_all_min()` 以上で、source がある場合に成立します。
- fused native kernel が選ばれた場合も、HIP コンパイル時の W11 kernel 分岐では `pick_ww()` を呼ばず、`STRATA_PF_FUSED_TILE` は効きません。該当するのは `experts_native()` の通常分岐です。

したがって、この変数は CPU 経路、Q2_0 向けの別 fused kernel、native fused prefill が選ばれない層や chunk には適用されません。native fused 経路を有効にする `STRATA_PF_FUSED` などの設定・条件は別に必要です。

根拠: `src/prefill/prefill.cpp:2302,2984-2987,3053-3060`、`sycl/src/prefill/prefill.cpp:3231-3234,3291-3298`、`src/prefill/moe_fused_iq.cu:1158-1204`、`sycl/src/prefill/moe_fused_iq.dp.cpp:1406-1446`。

## 実行時の詳細

CUDA と SYCL の各 native kernel 実装で `experts_native()` が通常分岐に入ると、`pick_ww(n, n_expert)` が選んだ幅を gate/up と down の kernel launch に渡します。64行指定時は内部値 `ww=4`、128行指定時は `ww=2` です。実装上、work item はそれぞれ「256 weight rows × 64 routed rows」と「128 weight rows × 128 routed rows」の形になります。この値は work item の形、shared-memory サイズ、および launch grid の計算に使われます。

`pick_ww()` の static 値は、その通常分岐で最初に呼ばれたときに一度だけ評価されます。以後、プロセス内で環境変数を変更しても反映されません。コードにはこの変数固有のログ出力や、無効値に対する警告はありません。

根拠: `src/prefill/moe_fused_iq.cu:53-60,94-96,1105-1114,1203-1218`、`sycl/src/prefill/moe_fused_iq.dp.cpp:49-55,90-92,1348-1357,1445-1460`。

## 文書・測定値との照合

`docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。実装コメントには、RTX 5070 上で64行と128行を比較した測定値が記されていますが、型・プロンプト長ごとに結果が異なります。これは実装コメントに記載された測定結果であり、一般的な性能向上を示すものではありません（`src/prefill/moe_fused_iq.cu:1100-1104`、SYCL 側にも同じコメント: `sycl/src/prefill/moe_fused_iq.dp.cpp:1343-1347`）。
