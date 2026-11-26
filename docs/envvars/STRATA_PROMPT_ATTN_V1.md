# `STRATA_PROMPT_ATTN_V1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA prompt attention が int8 K/V pool を処理するとき、通常の新しい int8 経路ではなく初期版の `launch<1>` を選ばせるデバッグ用スイッチです。初期版は同じ精度を意図しつつ和の順序が異なる、と実装コメントにあります。選択セルや pool は変えず、注意力計算の実装を切り替えます（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2541-2568`、`engine/include/strata/kernels/qsa_prompt_attn.hpp:8-18`）。

通常の CUDA prefill では、`STRATA_PROMPT_ATTN_OLD` が未設定で gated kernel が使われないときに batch kernel が呼ばれます。batch kernel が拒否した場合は decode attention のループへ進みます（`engine/src/prefill/prefill.cpp:5533-5570`、同ファイル `9459-9472`）。この変数自体が CLI 引数やサーバー設定から値を受け取る処理は見つかりません。

## 値と判定

CUDA 実装は `std::getenv(...) != nullptr` の結果を関数内 `static const bool` に保存します。文字列を読み取らないため、設定値の数値・真偽値としての妥当性、空白、大文字小文字、後続文字は判定しません（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2541-2546`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA、後述の int8 K/V 条件を通る経路 | `v1=false`。Turing は別条件で初期版を選ぶことがある | 空文字、`0`、`1`、`false`、`0anything` など、値が存在するすべての文字列で `v1=true` | なし。無効にするには未設定にする |
| HIP ビルド | 対象分岐まで到達しない | なし | なし |
| SYCL ビルド | 対象分岐まで到達しない | なし | なし |

## 有効になる条件

- CUDA 実装であること。HIP コンパイル時は `__HIPCC__` 分岐が WMMA を試して `return` するため、この変数の判定箇所に到達しません（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2509-2518`）。SYCL 版にも同名の `getenv` 式がありますが、ESIMD/XMX を試した後に必ず `return false` するブロックの後ろにあり、実行時には到達しません（`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2017,2045-2053`）。
- batch 関数が `n_q > 0` で、デバイス判定と形状・引数検査を通ること。形状は `head_dim == HD` かつ query/KV head 数が実装の `G` と一致し、`cap > 0`、`ids`、`steps`、page table が必要です（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2508,2519-2521`）。
- 対象 pool は純粋な int8 K/V です。`pools.k_q`、`pools.v_q`、`pools.k_scale`、`pools.v_scale` が必要で、先行する Q4_0 または K8V4 分岐には該当しないことが条件です（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2522-2546`）。
- Volta と判定された場合は `launch70<1>` に進み、この変数で経路は変わりません。`STRATA_EXPERIMENTAL_SM60` の有無とデバイス capability がこの判定に関わります（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2501-2508,2546-2549`）。
- `STRATA_PROMPT_ATTN_OLD` が設定されていると prefill 呼び出し元が batch kernel 自体を迂回して decode attention を使うため、この変数は効きません。ここも値ではなく設定有無の判定です（`engine/src/prefill/prefill.cpp:5540-5544,5556-5570,9462-9472`）。
- Turing では未設定でも `STRATA_PA_V2T` の先頭文字が `1` でなければ通常すでに初期版です。先頭文字が `1` の場合に Turing の v2 経路を選べますが、本変数が設定されていればその分岐より先に初期版を選びます（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2546-2556`）。
- Volta 以外で本変数が未設定なら、Turing は上記 v2t 判定後に初期版となり、それ以外は `STRATA_PROMPT_ATTN_IMMA` の値・既定条件に応じて INT8 tensor-core v3 または v2 を使います。本変数が設定されている場合はその判定より先に初期版へ進むため、IMMA の選択を上書きします（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2548-2568`）。

## 実行時の詳細

`qsa_prompt_attn_batch` が int8 K/V 分岐に初めて入ったときに環境変数を評価し、`static const bool` に保持します。その後プロセス内で環境を変更しても再評価されません。関数が呼ばれない、`n_q <= 0`、別 pool 分岐、または前段条件で拒否される場合はこの評価に至りません（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2473,2522-2546`）。

本変数が有効で Volta 以外なら `launch<1>` を選びます。初期版の任意の prefetch 形態は別の `STRATA_PA_V1_PREFETCH` と Turing/SM75 条件で決まり、本変数はその選択自体を変えません（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2550-2556`）。本変数が未設定で Turing でもなければ、`STRATA_PROMPT_ATTN_IMMA` の明示値または既定条件によって `launch_i8v3`、それ以外では `launch_i8` が選ばれます（同ファイル `2558-2568`）。

`launch<1>` が共有メモリ属性の設定に失敗すると `false` を返し、呼び出し元は `qsa_pattn_batch` が利用可能な場合にそれを試し、その後 decode attention に fallback します（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1434-1448`、`engine/src/prefill/prefill.cpp:5556-5570`）。

## ログと測定値

この変数の読み取りや分岐だけを知らせるログはありません。選択した初期版の CUDA kernel launch がエラーを返すと、stderr に `qsa_prompt_attn_batch: <CUDA error string>` を出して `exit(1)` します（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1457-1462`）。

## 根拠

- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2573` — CUDA batch attention の入口、backend・device・pool 判定、環境変数と kernel 選択。
- `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1973-2058` — SYCL 複製実装。同名の読み取り位置より前で必ず return する。
- `engine/src/prefill/prefill.cpp:5533-5574,9459-9477` — prefill からの呼び出し、旧経路の迂回、fallback。
- `engine/include/strata/kernels/qsa_prompt_attn.hpp:8-18,27-30` — prompt attention の計算上の位置づけと呼び出し契約。
