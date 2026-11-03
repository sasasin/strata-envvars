# `FNX_PF_MOE_Q8`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next split engine の prompt prefill において、選択された MoE expert の gate/up 入力を f16 ではなく Q8_1 に量子化し、対応する big-job gate/up・down カーネル経路を使います。生成時の decode 経路を変更する設定ではありません。

## 値と判定

共通 helper `env_flag()` は `env_int(name, 0) != 0` です。未設定なら `false`。設定時は符号付き十進整数を文字列全体から読み、値が 0 以外なら有効、0 なら無効です。`+1`、`-1` も受理されて有効になります。空文字、空白、数字以外を含む値、整数範囲外は無効値として扱われず、`FNX_PF_MOE_Q8: '<値>' is not a whole number` の例外になります。`1x` のように数字の後ろに文字がある値も拒否されます。範囲 clamp はありません。

| 環境変数 | 判定 |
|---|---|
| unset | 無効（既定値 0） |
| `0`, `+0`, `-0` | 無効 |
| 数値として有効な整数で 0 以外 | 有効 |
| 空文字・非整数・整数範囲外 | 例外 |

CLI 引数や別の環境変数による上書きは、この変数の読み取り経路にはありません。

## 有効になる条件

- `src/split` の Flash-Next split engine が構築され、`Engine::prefill_alloc()` が実行されること。この設定の読み取りは同 engine の prompt buffer 準備時に限られます。
- prompt の FFN half で MoE expert を処理すること。prefill の各層・chunk で flag に応じて expert 入力を量子化し、MoE big-job kernels を呼びます。
- shared expert はこの分岐の対象外で、引き続き `xh` を使う f16 側の処理です。

このソースに OS や GPU 世代による追加の判定はありません。対象コードは CUDA/HIP split 実装内にあります。値を読む箇所は `prefill_alloc()` のカードごとの loop 内なので、環境値は prompt buffer の割り当て時に読み取られます。`Pf::moe_q8` に保存された後の prefill pass は保存値を使います。プロセス環境を後から変えても、既に作られた `Pf` の値は更新されません。

## 実行時の詳細

有効時は prompt の FFN で `pf_hc_read()` が作った `mixed` を `quantize_q8_1()` で Q8_1 に変換し、その値を `moe_gate_up_big()` に渡します。gate/up 出力から続けて `moe_down_big()` を実行します。無効時は `xh` の half 値を入力に `moe_gate_up_mma()` を呼び、出力を half に変換して `moe_down_mma()` を実行します。両経路とも router、top-10 expert 選択、job 作成、および後続の shared expert 処理は同じ周辺コードにあります。

この flag 専用のログや値の clamp/fallback はありません。無効な文字列は `env_int()` が `std::runtime_error` を投げます。sfnx の engine 初期化中に発生した例外は `sfnx: failed: ...` を stderr に出し、`ERR ...` をフロントエンド向けに出して終了コード 1 で終了します。

## 根拠

- `src/split/src/env.hpp:15-22,33-40,51-52` — 整数全体の parse、未設定既定値、無効値例外、flag 判定。
- `src/split/src/prefill.cu:318-328,625-645,717-727` — per-card prefill state と flag の読み取り・Q8 入力 buffer の確保。
- `src/split/src/prefill.cu:1264-1289,1292-1297` — prompt FFN の Q8_1 と f16 の分岐、および shared expert の f16 処理。
- `src/split/src/kernels.cu:1063-1069,2177-2182` — Q8_1 quantizer と big-job wrapper の呼び出し。
- `src/split/tools/sfnx.cpp:1027-1035,1040-1048` — engine 実行中例外の通知・終了経路。
