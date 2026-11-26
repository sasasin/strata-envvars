# `FNX_PFX_ATTN_I8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

split engine の prompt attention で、NVIDIA sm_80 以上向けの INT8 tensor-core カーネルを使うか選びます。値が有効で K/V ページも int8 なら `k_pf_attn_i8` を起動し、それ以外は通常の `k_pf_attn` を起動します。対象は prompt chunk の attention で、decode attention の `attn()` 経路にはこの判定がありません（`engine/src/split/src/kernels.cu:1385-1400,1426-1451`）。

この変数は split engine 内だけで読み取られます。split engine は明示的な build opt-in が必要で、CUDA/HIP build のうち、この判定がコンパイルされるのは HIP ではない `FNX_ARCH >= 80` の場合です（`engine/src/split/CMakeLists.txt:1-5,20-27,68-74`; `engine/src/split/src/kernels.cu:1426-1432`）。

## 値と判定

`fnx::env_int` が環境から文字列全体を符号付き base-10 整数として読み、`long long` に収まる値だけを受け付けます。先頭の `+` / `-` は可、空文字・空白・末尾の文字・整数でない文字列・`long long` の範囲外は無効です。無効値では `<NAME>: '<値>' is not a whole number` の例外になります（`engine/src/split/src/env.hpp:15-21,33-40`）。

読み取った値を `int` に変換し、0 以上なら `0` は無効、非 0 は有効、負数ならモデル既定値を使います。範囲制限はなく、`long long` から `int` への変換も明示的に検査されません。`int` の範囲外の値の結果は移植可能な設定として扱えません（`engine/src/split/src/kernels.cu:1431-1433`）。

| 条件 | unset | 設定時に INT8 attention を選ぶ値 | 設定時に無効／既定値へ戻す値 |
|---|---|---|---|
| CUDA、`FNX_ARCH >= 80` | GGUF の routed-expert type 分類に従う | `1`, `+1`, `2` など、`int` 化後の正の整数 | `0`, `-0` は無効。`-1`, `-2` など負数はモデル既定値。空文字、`true`, `0anything`, `1 ` は整数全体として不正で例外 |
| HIP または `FNX_ARCH < 80` | この変数は読まれない | 該当なし | 設定値にかかわらずこのコードは使わない |

未設定時の既定値は、Engine 構築時に `m_.g.iq_experts()` から設定されます。GGUF 内に `T_IQ2_S`、`T_IQ3_XXS`、`T_IQ3_S`、`T_Q2_0` のいずれかの tensor があれば true、それ以外は false です（`engine/src/split/src/engine.cu:65`; `engine/src/split/src/gguf.cpp:139-144`）。したがって既定は、該当する IQ / 2-bit routed-expert ファイルで有効、それ以外で無効です。

## 有効になる条件

- split engine が build され実行されている必要があります。CUDA かつ `FNX_ARCH >= 80` のビルドだけがこの環境変数を参照します。HIP と sm_80 未満の build では f16 カーネルの経路です（`engine/src/split/CMakeLists.txt:1-5,20-27,68-74`; `engine/src/split/src/kernels.cu:1429-1451`）。
- prompt chunk の attention 呼び出しが必要です。空 chunk（`T == 0`）では関数冒頭で戻るため、環境変数も読みません（`engine/src/split/src/kernels.cu:1426-1432`）。通常の prompt chunk では `pf_attn_start` から呼び出されます（`engine/src/split/src/prefill.cu:772-780`）。
- `FNX_PFX_ATTN_I8` が有効でも、K/V ページが int8（`g.q8 == true`）でなければ INT8 attention は起動せず、通常の prompt attention に fallback します（`engine/src/split/src/kernels.cu:1432-1451`）。K/V の形式は別設定 `FNX_KV8` が決め、未設定時は int8、`FNX_KV8=0` なら f16 です（`engine/src/split/src/kernels.cu:1890-1897`; `engine/src/split/src/engine.cu:418-419`）。
- CLI 引数による優先・上書きの経路は、この名前の全参照にはありません。環境値が非負ならモデル既定値を置き換え、負数または未設定ならモデル既定値が選ばれます（`engine/src/split/src/kernels.cu:1431-1433`）。

## 実行時の詳細

Engine 構築時にモデル分類から既定値をセットします。その後、最初の非空 prompt attention 呼び出しで `static const int i8_env` が環境値を読み、プロセス内で cache します。その呼び出し時点でモデル既定値と合わせて分岐し、以降の chunk や request でも同じ環境値の判定を使います。実行中に環境を書き換えても再読込されません（`engine/src/split/src/engine.cu:65`; `engine/src/split/src/kernels.cu:1426-1433,1913-1920`）。

INT8 経路では、対象 device ごとに共有 memory carveout を設定し、`k_pf_attn_i8` を起動して `ck_launch("attn_prompt (int8)")` で確認後に戻ります。設定値が無効、または K/V が f16 なら `k_pf_attn` と `ck_launch("attn_prompt")` に進みます。どちらの経路も後続の prompt attention merge は共通です（`engine/src/split/src/kernels.cu:1433-1451`; `engine/src/split/src/prefill.cu:772-784`）。

## ログと測定値

この変数が有効かどうかを示す専用の成功ログはありません。形式不正なら env helper が例外 `FNX_PFX_ATTN_I8: '<値>' is not a whole number` を投げます（`engine/src/split/src/env.hpp:33-40`）。sfnx の実行中に prompt 経路で例外になった場合、失敗経路は `ERR <例外内容>` を出力し、stderr に `sfnx: failed: <例外内容>` を出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1103,1160-1166`）。`fnx_run` では stderr に `fnx_run: <例外内容>` を出して終了コード 1 です（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

`docs/DETAILS.md` にこの変数の測定値や実行条件を伴う説明は見つからなかったため、速度・精度の数値は記載しません。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数の厳密な parse、unset fallback、不正値の例外。
- `engine/src/split/src/engine.cu:65`、`engine/src/split/src/gguf.cpp:139-144` — モデル分類に基づく既定値。
- `engine/src/split/src/kernels.cu:1426-1451,1913-1920` — compile guard、環境値 cache、条件分岐、カーネル選択。
- `engine/src/split/src/kernels.cu:1890-1897, engine/src/split/src/engine.cu:418-419` — K/V page の形式と `FNX_KV8`。
- `engine/src/split/src/prefill.cu:772-780` — prompt 呼び出し元。
- `engine/src/split/tools/sfnx.cpp:1094-1103,1160-1166`、`engine/src/split/tools/fnx_run.cpp:1364-1373` — 例外の観測方法。
