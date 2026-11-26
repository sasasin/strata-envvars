# `STRATA_PROMPT_ATTN_Q4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA prompt attention で、Q4_0 KV を mode 4 のカーネルで処理するかを切り替える。未設定時は mode 4 を許可し、値の先頭文字が `0` なら使わない。OFF またはカーネルが適用条件を満たさない場合、呼び出し元は decode attention の経路へ進む。KV の保存形式自体はこの変数では変わらず、Q4_0 KV を選ぶのは `--kv q4_0`（または `--kv q4`）である。`generate.cpp` はその指定を `qsa_set_kv_q4` に渡し、Q4 状態では K/V の pool を Q4_0 用ポインターとして構成する（`engine/src/program/generate.cpp:5014-5020`, `engine/src/core/layer.cpp:813-823`, `engine/src/core/layer.cpp:1021-1027`）。

CUDA の mode 4 は Q4_0 の nibble を `code - 8` の int8 値に展開し、各 32 要素ブロックの FP16 scale を保持して attention 計算に使う（`engine/src/kernels/cuda/qsa_prompt_attn.cu:219-250`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:450-464`）。この分岐は CUDA 実装の `qsa_prompt_attn_batch` にある。SYCL にも同名の読み取りコードはあるが、現行制御フローでは到達しない（「有効になる条件」参照）。

## 値と判定

CUDA 実装は Q4 pool の分岐に初めて入ったとき `std::getenv` を呼び、値が存在し、かつ `v[0] == '0'` の場合だけ OFF とする。文字列全体の parse や空白除去、数値検査はない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2522-2526`）。

| 条件 | unset | 設定時に mode 4 が有効になる値 | 設定時に mode 4 が無効になる値 |
|---|---|---|---|
| CUDA の Q4 pool 分岐に到達 | `q4_off == false`（mode 4 を許可） | 先頭文字が `0` 以外。例: `1`, `true`, 空白付きの ` 0`, 空文字以外の任意文字列 | 先頭文字が `0`。例: `0`, `0anything`, `00` |

空文字は設定済みですが長さ 0 のため `v[0] == '0'` は成立せず、mode 4 を許可する値として扱われる。大文字小文字の区別や、全体が真偽値・数値として妥当かの確認はない。`STRATA_PROMPT_ATTN_Q4=1` のような明示的な ON 値は不要である。これは `STRATA_PROMPT_ATTN_Q4_TC` とは別の変数であり、後者は CUDA の Turing で追加 opt-in として評価される（同ファイル `:2527-2534`）。

## 有効になる条件

- 実際に Q4_0 KV を使い、attention pool の `k_q4` が非 null であること。通常は `--kv q4_0`（別名 `--kv q4`）がこの状態を選ぶ。`--kv` の値検査と状態設定は `engine/src/program/generate.cpp:5014-5020`、pool の構築は `engine/src/core/layer.cpp:1021-1027` にある。
- CUDA の `qsa_prompt_attn_batch` が呼ばれ、head shape がコンパイル済み条件（head_dim 256、head 数の関係）に合い、`cap`、`ids`、`steps`、page table が有効であること。満たさなければ環境変数の読み取り前に `false` を返す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2519-2526`）。
- 現在 device の compute capability が 70 以上であること。device 情報を取得できない場合、または capability が 70 未満なら `false` を返すため、この値は読まれない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2482-2500`）。
- Q4 pool 分岐で `q4_off` が false、Volta 判定が false、かつ `v_q4` が非 null であること。どれかを満たさない場合は mode 4 を起動せず `false` を返す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2522-2534`）。
- 有効 compute capability が 80 未満（Turing を含む）ではさらに `STRATA_PROMPT_ATTN_Q4_TC` の先頭文字が `1` であることが必要。未設定・空文字を含め、それ以外は Q4 mode 4 を拒否する。80 以上にはこの追加条件はない。判定は `turing = cc[dev] < 80` に基づく（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2506-2507`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:2527-2534`）。
- 有効 compute capability は実 device 値と異なることがある。`STRATA_EMULATE_CC` は `atoi` 値が 75..119 の場合に優先し、`STRATA_QSA_WARP` が完全一致 `1` または `attn` で実 capability が 75 以上なら 75 に設定する。さらに `STRATA_VOLTA_FOREVER` / `VOLTA_FOREVER`、`LD_PRELOAD`、ロード済み shim の検出は sm_75 を 70 に remap し得る。これらは本変数の値を変換するものではなく、上記 device 条件を左右する（`engine/include/strata/core/emulate.hpp:58-75`, `engine/include/strata/core/volta_forever.hpp:40-65`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:2492-2507`）。
- CUDA ビルド macro `STRATA_EXPERIMENTAL_SM60` が有効なら有効 capability 75 未満を `volta` と判定し、Q4 分岐は mode 4 を拒否する。有効でなければ `volta` は常に false だが、mode 4 の MMA 自体は sm_75 未満向けビルドで trap になる実装である。対象 checkout の実際の build architecture はこのソース調査では実行・検証していない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:42-60`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:2501-2507`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:2533-2534`）。
- HIP では Q4 mode 4 に進まず、対象の prompt attention 関数は WMMA の int8 条件が合わなければ `false` を返す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2509-2517`）。SYCL では関数前半が ESIMD、次に XMX を試し、それらが処理しなければ `false` を返して関数を終了する。両実装とも Q4 pool を拒否するため、後方にある `STRATA_PROMPT_ATTN_Q4` 読み取り箇所（`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2031-2038`）には到達しない。ESIMD の拒否条件は `:406-413`、XMX は `engine/sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:369-376`、先行して戻る分岐は `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2017`。
- `STRATA_PROMPT_ATTN_OLD` が設定されていると（空文字を含め `getenv != nullptr`）、prefill 呼び出し元がこの prompt attention 関数を迂回し、decode attention の経路を使う（`engine/src/prefill/prefill.cpp:5537-5544`, `engine/src/prefill/prefill.cpp:5556-5569`）。Q4 は `kv_rot` 状態になるため gated attention の条件も満たさない（`engine/src/core/layer.cpp:813-823`, `engine/src/prefill/prefill.cpp:5540-5544`）。

## 実行時の詳細

prefill は QSA pool を得た後、gated path が成立しなければ `qsa_prompt_attn_batch` を呼ぶ。環境変数が `0` である場合、または CUDA 側の適用条件を満たさずこの関数が `false` を返した場合、呼び出し元の条件式は decode attention を選び、`m.attn_batch` ごとに `qsa_decode_attn_batch` を実行する（`engine/src/prefill/prefill.cpp:5533-5544`, `engine/src/prefill/prefill.cpp:5556-5569`）。もう一つの prefill 経路にも同じ fallback がある（`engine/src/prefill/prefill.cpp:9459-9472`）。

値はプロセス起動時には読まれない。CUDA の関数内 `static const bool q4_off` として、Q4 pool 分岐を初めて通った時に一度評価され、その後はキャッシュされる。同じ関数内の Turing 用 `q4_tc` も同様である。したがって、初回評価後に環境を変更してもこのプロセス内の判定には反映されない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2522-2532`）。CLI 引数や別変数による `q4_off` の上書きはない。CLI の KV 形式指定は、判定対象となる Q4 pool を使うかどうかを決める前提条件である。

## ログと測定値

この変数の ON/OFF 判定や fallback 自体を知らせる専用ログはない。通常の mode 4 選択も専用ログを出さない。mode 4 の kernel launch に失敗した場合、CUDA 実装は stderr に `qsa_prompt_attn_batch: <CUDA error string>` を出して `exit(1)` する。一方、動的 shared memory の属性設定に失敗した場合は `false` を返し、呼び出し元の decode fallback に進む（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1435-1462`, `engine/src/prefill/prefill.cpp:5556-5569`）。

対象変数の値による性能・精度の測定値は、調査対象ソース内で条件付きの根拠を確認できなかったため記載しない。

## 根拠

- CUDA での値判定・mode 4 選択: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2519-2534`
- CUDA device 条件と HIP 分岐: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2482-2517`
- mode 4 の Q4 block 展開と積和: `engine/src/kernels/cuda/qsa_prompt_attn.cu:219-250`, `engine/src/kernels/cuda/qsa_prompt_attn.cu:450-464`
- prefill の prompt attention と fallback: `engine/src/prefill/prefill.cpp:5533-5569`, `engine/src/prefill/prefill.cpp:9459-9472`
- Q4 KV の指定、状態、pool: `engine/src/program/generate.cpp:5014-5020`, `engine/src/core/layer.cpp:813-823`, `engine/src/core/layer.cpp:1021-1027`
- SYCL で読み取りに到達しない制御フローと Q4 拒否: `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2012-2017`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2031-2038`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:406-413`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:369-376`
