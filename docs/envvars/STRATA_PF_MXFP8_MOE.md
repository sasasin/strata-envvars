# `STRATA_PF_MXFP8_MOE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA Blackwell の MoE prompt prefill で、Strata 独自の MXFP8 (`mxf8f6f4`) Tensor Core expert kernel を選ぶための opt-in 変数。未設定または `atoi` の結果が 0 ならこの経路を選ばず、条件がそろった fused native prefill は通常の fused int8 expert kernel を使う。値が非 0 なら、対応 GPU・重み形式などの条件を満たす場合に MXFP8 経路を選ぶ。`wanted()` が値を判定し、`prefill.cpp` が activation の量子化と expert 計算を同経路へ振り分ける（`engine/src/prefill/moe_fp8_mxf_tc.cu:729-737`、`engine/src/prefill/prefill.cpp:5740-5771,5821-5829`）。

この変数は dense GEMM の MXFP8 経路を制御しない。別の実装・別変数である（`engine/src/prefill/gemm_mxfp8.cuh:439-500`）。

## 値と判定

CUDA 実装の `wanted()` が最初に呼ばれたとき、関数内 `static` 初期化で `std::getenv` を一度実行し、その結果をプロセス内でキャッシュする。未設定 (`nullptr`) と空文字は無効。空文字以外は `std::atoi` の戻り値が 0 かどうかで判定し、0 以外なら有効とする。文字列全体の数値妥当性チェックはなく、`atoi` が先頭から変換できた整数部分で決まる。したがって `1`、`2`、`-1` は有効、`0`、`0anything`、`true`、`false`、`anything` は無効。先頭の空白や符号の後に非 0 の整数があれば有効（例: `  +1tail`）。大文字小文字の比較はしない。数値変換範囲外の文字列についてはコードに独自の検査・fallback がない（`engine/src/prefill/moe_fp8_mxf_tc.cu:729-736`）。

| ビルド・実行条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| MXFP8 CUDA 実装を含むビルド | 無効 | `atoi` の結果が非 0（例: `1`, `-1`, `2`） | 空文字、`atoi` の結果 0（例: `0`, `0tail`, `true`） |
| absent stub を含むビルド | 無効 | なし。stub の `wanted()` は常に `false` | すべての値 |

## 有効になる条件

- CUDA build が CUDA compiler 13.0 以上で、CUDA architecture の対象に 120 または 121（あるいは `all` / `all-major`）が含まれ、MXFP8 実装が組み込まれていること。そうでない CUDA build と HIP build は absent stub を使い、この変数を読み取らない（`engine/cmake/backends/cuda.cmake:102-130`、`engine/cmake/backends/hip.cmake:32-47`、`engine/src/prefill/moe_fp8_mxf_tc_absent.cpp:10-15`）。
- 実行デバイスの compute capability が 12.0 または 12.1 で、形状条件を満たし、CUDA occupancy query が成功して occupancy が正であること。device の適合結果は device ごとに初回照会時に cache される（`engine/src/prefill/moe_fp8_mxf_tc.cu:675-712`）。
- prefill が `fused_l` 経路を通ること。通常の `STRATA_PF_FUSED` 選択を含む MMQ/fused-only plan、`stream_all`、no-peer 条件などを満たす必要がある。これらを満たさないと `wanted()` まで到達せず、この変数だけでは fused path を有効化しない（`engine/src/prefill/prefill.cpp:5688-5704,5740`）。
- レイヤーが native expert layout で `fused::native_supported()` に対応し、Hadamard folded gate/up・down を使わず、NVFP4 専用経路にも該当しないこと。NVFP4 条件が先に成立すれば `fp4_nat` が優先され、MXFP8 判定は呼ばれない（`engine/src/prefill/prefill.cpp:5696-5699,5741-5745`）。
- gate/up の重み型が `IQ3_S`, `IQ3_XXS`, `IQ2_S`, `IQ4_XS`, `Q4_K`, `Q5_K`, `Q8_0` のいずれか、down の重み型が `IQ4_NL`, `Q5_1`, `Q8_0` のいずれかであること（`engine/src/prefill/moe_fp8_mxf_tc.cu:714-720,735-736`）。

CLI 引数や別の環境変数がこの値を上書きする処理はこの読み取り箇所にはない。ただし fused path 自体は上記の plan・レイヤー条件に依存する。条件を満たして `fused_l` に入っても、本変数が無効または対応形式・デバイスでなければ MXFP8 の代わりに fused int8 の分岐へ進む（`engine/src/prefill/prefill.cpp:5740-5771`）。

## 実行時の詳細

対象名を読み取る箇所は `moe_fp8_mxf_tc::wanted()` の `std::getenv` 一箇所。最初に呼ばれた時点で値を `static const int` に保存し、以降のレイヤーやリクエストでも再読込しない。プロセス起動後に環境を変更しても判定へ反映されない。Strata がこの値を子プロセスへ設定・転送するコードは見つからなかった（`engine/src/prefill/moe_fp8_mxf_tc.cu:729-737`）。

値が有効でも `available()` と両方の重み型チェックを通らなければ `wanted()` は false を返す。選択されると prompt 入力を MXFP8 activation に量子化し、各 expert batch を `fp8_mxf_tc::experts()` へ渡して gate/up と down を計算する。選択されない fused native 形式では対応する fused int8 の量子化・expert 関数に進む（`engine/src/prefill/prefill.cpp:5763-5771,5821-5846`）。

## ログと測定値

MXFP8 経路に入った最初のレイヤーで stderr に一度だけ次を出す。

```text
strata: prompt experts on the Blackwell mxf8f6f4 tensor-core kernels (STRATA_PF_MXFP8_MOE=0 disables)
```

fused path が実行され、MXFP8/NVFP4 のどちらも選ばれない場合は、代わりに `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を一度出す。fused path 自体を通らない場合、この分岐のログは出ない（`engine/src/prefill/prefill.cpp:5746-5761`）。

`docs/DETAILS.md` に本変数固有の測定値は見つからなかったため、性能値は記載しない。

## 根拠

- `engine/src/prefill/moe_fp8_mxf_tc.cu:675-736` — device capability / occupancy cache、対応型、環境変数の値判定。
- `engine/src/prefill/moe_fp8_mxf_tc_absent.cpp:10-24` — 非対応 build の stub。
- `engine/cmake/backends/cuda.cmake:102-130`、`engine/cmake/backends/hip.cmake:32-47` — CUDA arch / compiler 条件と HIP stub の組み込み。
- `engine/src/prefill/prefill.cpp:5688-5704,5740-5775,5821-5846` — fused path の条件、MXFP8 判定、ログ、quantize と expert dispatch。
- `docs/SETTINGS.md:221` — 候補一覧には NVIDIA and AMD と記載されているが、実装上 HIP build は stub を使い、変数を読み取らない。
