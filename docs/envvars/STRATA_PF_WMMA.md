# `STRATA_PF_WMMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の prompt prefill にある MoE expert 計算で、条件を満たすレイヤーを MMQ の q8_1 活性値経路から FP16 活性値の grouped tensor-core kernel に切り替える opt-in です。`pf_wmma()` が有効と判定した後も、MMQ 計画に入る native expert layer のうち型と形状が対応するものだけが対象です。既定では無効です。FP16 活性値経路は MMQ と異なる計算なので、数値結果は既定経路と異なり得ます（`engine/src/prefill/prefill.cpp:1964-1969, 1970-1986, 6322-6326, 6474-6494`）。

## 値と判定

`pf_wmma()` は `std::getenv` の戻り値が null でないことに加え、最初の文字 `e[0]` が ASCII `'1'` であることだけを見ます。文字列全体の parse はせず、大文字小文字や数値妥当性の検証もありません。空文字は設定済みでも無効です。先頭の空白は `'1'` と一致しないため無効ですが、`1abc` や `10` のように先頭が `1` なら有効判定になります（`engine/src/prefill/prefill.cpp:1970-1977`）。

| ビルド・実行条件 | unset | 判定が有効になる値 | 判定が無効になる値 |
|---|---|---|---|
| HIP (`__HIPCC__` または `STRATA_USE_HIP`) / Metal (`STRATA_GPU_METAL`) | 無効 | なし。このビルド分岐では常に `false` | すべて |
| それ以外（CUDA 経路） | 無効 | 先頭文字が `1` で、後述の CUDA device 条件も満たす値（例: `1`, `1abc`, `10`） | 空文字、`0`, `true`, ` 1`、先頭が `1` 以外の値、および CUDA device 条件を満たさない値 |

CUDA 経路では `cudaGetDeviceCount` が成功して可視 device が 1 台以上あり、すべての可視 CUDA device について compute capability major の取得が成功し、その major が 7 以上の場合に限り true になります。取得失敗、device なし、または 1 台でも major が 7 未満なら無効です。minor version はこの判定に使いません（`engine/src/prefill/prefill.cpp:1977-1985`）。

## 有効になる条件

- CUDA ビルドであること。HIP / Metal 分岐では値を読まず false を返します。CUDA kernel 実装も `__HIPCC__` でない場合にだけ定義され、HIP 側の同名関数は false を返します（`engine/src/prefill/prefill.cpp:1970-1973`; `engine/src/kernels/cuda/iq_kernels.cu:7572-7577, 7974-7981`; Metal stub は `engine/metal/src/engine/stubs_0145.cpp:147-148`）。
- CUDA 経路では、環境値に加えて全可視 GPU が compute capability major 7 以上であること（`engine/src/prefill/prefill.cpp:1977-1985`）。
- 通常 build では MMQ が build され、`STRATA_PREFILL_MMQ` が unset または `atoi` の結果が 0 以外であり、MMQ plan が対象レイヤーを処理すること。`STRATA_PF_OWN_ONLY` build では plan の有効条件が `fused::built()` と同じ環境値判定になります。いずれも `STRATA_PREFILL_MMQ=0`、空文字、数値変換結果が 0 の文字列では plan が off です。`STRATA_PF_WMMA` はこの別変数の判定を上書きしません（`engine/src/prefill/prefill.cpp:2026-2037, 2048-2059`）。
- native expert layout で、レイヤーが MMQ grouping の対象になり、型・形状が grouped kernel に対応すること。plan 作成時には MMQ に tile がない型のうち、down type が Q2_0 (`42`) または IQ4_NL (`20`) で gate/up の row bytes が有効な場合に WMMA-only layer として登録します。実行時にも fused layer でないこと、tail scale がないことなどを確認します（`engine/src/prefill/prefill.cpp:2048-2061, 6322-6329`）。
- multi-GPU peer 経路では追加条件があります。WMMA layer は P2P peer が有効で compact buffer を使い、Hadamard fold が gate/up と down の双方にない場合に限って実行対象になります（`engine/src/prefill/prefill.cpp:6322-6326`）。
- `STRATA_PF_WMMA2` はこの変数の有効化条件ではありません。別の static 判定で先頭文字 `1` の場合、IQ2_S / IQ4_NL など kernel の追加条件を満たす grouped GEMM 呼び出しで WMMA2 kernel を先に選ぶことがあります（`engine/src/kernels/cuda/iq_kernels.cu:7915-7918, 7921-7944`）。
- `--prefill` など CLI 引数が `STRATA_PF_WMMA` を直接上書きする読み取り箇所は見つかりませんでした。実際に対象 layer を使えるかは上記の plan・format・peer 条件で決まります（対象名の全参照確認、および `engine/src/prefill/prefill.cpp:2026-2059, 6322-6329`）。

## 実行時の詳細

`pf_wmma()` 内の function-local `static const bool` が初回呼び出し時に環境値と CUDA device 情報を評価し、そのプロセス中は結果を cache します。`mmq_plan()` も function-local static plan を一度だけ作ります。したがって、プロセス起動後に環境値を変えても、この判定・plan には反映されません（`engine/src/prefill/prefill.cpp:1970-1986, 2026-2038`）。

WMMA-only layer は plan に記録され、実行時に `wmma_l` が成立すると、行を FP16 に gather し、grouped GEMM で gate/up を計算し、SwiGLU 後の FP16 値で down GEMM を行います。single-GPU 側は `engine/src/prefill/prefill.cpp:6474-6494, 7361-7374`、peer 側は `engine/src/prefill/prefill.cpp:6851-6864` です。kernel は CUDA device の major が 7 未満、形状や型が未対応などの場合に false を返す経路を持ちます（`engine/src/kernels/cuda/iq_kernels.cu:7921-7948`）。

WMMA-only として plan に記録された layer で、その chunk が `wmma_l` 条件を満たせない場合は `prefill: an IQ1_M layer in the MMQ grouping needs the WMMA tiles, which this chunk cannot take` をエラーにします（`engine/src/prefill/prefill.cpp:6327-6329`）。kernel 呼び出しが false を返した場合は single-GPU で `prefill: the WMMA expert tiles could not launch`、peer 側で `prefill: the peer WMMA expert tiles could not launch` をエラー文字列に設定します。`Prefill::run` が false を返すと generate は `strata generate: <error>` を stderr に出し、終了コード 1 で終了します（`engine/src/prefill/prefill.cpp:6860-6864, 7370-7374, 9705-9713`; `engine/src/program/generate.cpp:24164-24167`）。

## ログと測定値

この変数が有効になったことだけを通知する専用の通常ログは確認できませんでした。`STRATA_MANIFEST` が有効な場合、MMQ plan は対象 layer の経路を `mmq-grouping, FP16 WMMA tiles` として manifest に記録し、理由に `MMQ has no tile for these formats; STRATA_PF_WMMA=1 computes them on FP16 tensor cores` を含めます（`engine/src/prefill/prefill.cpp:2043-2047, 2051-2059`; manifest の環境読み取りは `engine/include/strata/core/run_manifest.hpp:185-193`）。kernel 起動失敗時のエラー文言と終了経路は「実行時の詳細」に記載しました。

Strata の `docs/NVIDIA_V100.md` には V100 での測定記録がありますが、現行 checkout の実装動作の根拠にはしていません。関連する benchmark README の「any CUDA card」という記載は、現行 `pf_wmma()` の全可視 CUDA device に対する major 7 以上の判定と一致しないため、ここでは性能値を一般化していません（現行判定: `engine/src/prefill/prefill.cpp:1977-1985`）。

## 根拠

- `engine/src/prefill/prefill.cpp:1964-1986` — 機能の説明、環境値の先頭文字判定、CUDA device 条件。
- `engine/src/prefill/prefill.cpp:2026-2059` — MMQ 計画、`STRATA_PREFILL_MMQ` との関係、WMMA-only layer の登録。
- `engine/src/prefill/prefill.cpp:6322-6329, 6474-6494, 7357-7374` — layer 適用条件、FP16 活性値経路と grouped GEMM の実行。
- `engine/src/prefill/prefill.cpp:6851-6864` — peer 経路とその失敗。
- `engine/src/kernels/cuda/iq_kernels.cu:7572-7577, 7921-7981` — CUDA grouped kernel の制約と非 CUDA stub。
- `engine/src/program/generate.cpp:24164-24167` — prefill 失敗時の stderr と終了コード。
