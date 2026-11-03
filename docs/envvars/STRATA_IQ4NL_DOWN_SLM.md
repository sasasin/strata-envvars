# `STRATA_IQ4NL_DOWN_SLM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の grouped native expert 処理で、IQ4_NL down projection が使う Q8_1 activation を work-group local memory（SLM）へ段階的にコピーしてから積和するカーネルを選びます。既定では無効です。候補名は `docs/envvars/000_envvers.md` にありますが、実際の読み取りは `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にある 1 箇所です。

## 値と判定

`strata::bm_default_on(name, device, false)` が環境変数を判定します。文字列全体の parse はせず、値が空でない場合は先頭文字だけを見ます。

| 環境変数の状態 | 判定 | 備考 |
|---|---|---|
| 未設定 | OFF | `bm_default=false` のため Battlemage でも既定 OFF |
| 空文字 | OFF | helper は空文字を未設定と同様に扱う |
| 先頭文字が `0` | OFF | 例: `0`, `0anything` |
| 空でなく先頭文字が `0` 以外 | ON | 例: `1`, `true`, `false`, `2`, `x` |

空白の除去、数値変換、大文字小文字の変換はしません。したがって `false` は先頭文字が `f` のため ON です。設定値がある場合は GPU 世代による既定判定を使わず、先頭文字の結果を採用します。

## 有効になる条件

値が ON でも、すべて次の条件を満たす場合に限り SLM カーネルを起動します。

- `native_expert_grouped()` から down kernel の dispatch に到達すること。モデルの layer が native expert layout を使う経路で呼ばれます。
- down weight type が `20`（IQ4_NL）であること。
- `STRATA_OLD_IQ_MMVQ` 等で設定される `g_old_kernels` が false であること。
- layout が `L.n_embd == 2560` かつ `L.n_ff == 640` であること。
- `STRATA_HIP_GFX906` の専用分岐で IQ4_NL down を処理していないこと。その分岐は AMD down kernel を起動して戻るため、通常の `launch_down<20>()` に到達しません。

これらを満たさないときは既存の down kernel dispatch が続きます。ソースには、この環境変数用の CLI 引数、ログ、警告、fallback 通知はありません。

## 実行時の詳細

読み取りは `launch_down<20>()` の初回実行時に `static const bool` として評価されます。同じ関数特殊化について以降の呼び出しで再読込しないため、実行中に環境を変えても判定は更新されません。CLI 引数による上書きもこのコードにはありません。

有効条件に合うと `launch_down_iq4nl_slm()` が呼ばれます。work-group は 256 item で、各グループが IQ4_NL down の activation 行を最大 `GRP_NC` 件ずつ local memory にコピーし、barrier 後に積和して出力へ書きます。合わない場合、通常の `launch_down_lanes<20>()` または split multi down kernel 側へ進みます。

この分岐が選択されなかった理由や、選択されたことを示す専用ログはありません。down dispatch 後には `check("native_expert_grouped/down")` が呼ばれますが、このファイルの `check()` は DPCT 移行コメントと dummy error 値を置く実装で、ここから環境変数固有のエラー文言や終了動作は確認できません。

## 根拠

- 環境変数の全参照は `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5061` の読み取り 1 箇所と、`docs/INTEL.md:539` の説明表 1 箇所です。候補一覧の記載は `docs/envvars/000_envvers.md:1330`。
- 先頭文字・空文字・既定値の判定: `sycl/include/strata/sycl_queue.hpp:159-166`。Battlemage 判定は `sycl/include/strata/sycl_queue.hpp:119-157` にありますが、この変数は `bm_default=false` を渡すため未設定時には使われません。
- 条件分岐と通常カーネルへの fallback: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5054-5073`。旧カーネル設定の読み取り: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3432-3437`。
- SLM カーネルの local memory コピー、barrier、IQ4_NL 積和と出力: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2545-2603`。起動 geometry: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5042-5051`。
- native grouped dispatch と IQ4_NL down type の分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6048-6055,6200-6234`。`STRATA_HIP_GFX906` 専用 down 分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6204-6227`。
- engine 呼び出し元: `sycl/src/core/verify.cpp:1531-1538` と `sycl/src/core/remote_experts.cpp:431-438`。
- down 後の `check()` 実装: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:42-54`。
