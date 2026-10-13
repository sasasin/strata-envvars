# `STRATA_SELECT_WMMA`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査時の作業ツリーは `main...origin/main` で変更なし。

## 役割

QSA（query-selected attention）の prompt 処理で、各 query に対する block score の計算カーネルを選びます。HIP ビルドでこの環境変数が有効になり、対応 GPU と入力形状を満たすと、通常の warp scorer の代わりに WMMA（行列演算）scorer を使います。カーネルの浮動小数点演算順が異なり、block の選択結果も一部の query で変わり得ます。

## 値と判定

HIP 実装は文字列を数値として parse せず、最初の文字だけを検査します。判定結果は関数内の `static const bool` に保存され、最初の判定後はプロセス内で環境変数を変更しても更新されません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外の非空文字列 | 有効（例: `1`, `2`, `true`, `false`, 空白で始まる文字列） |

## 有効になる条件

- `qsa_block_scores_tc()` が呼ばれる HIP 実行経路であること。CUDA の `__HIPCC__` 以外の実装では、この変数は読まれず、CUDA の Tensor Core scorer の選択は別の条件で行われます。
- `qsa_block_scores_tc()` の共通入力条件を満たすこと: `nq > 0`, indexer geometry が `IDX_DIM`, `IDX_HEADS`, `R` と一致し、`nq <= 65535 * TC_QT` であること。満たさない場合は `false` を返し、呼び出し側が warp scorer に fallback します。
- WMMA scorer が対応する GPU であること。HIP 側の device 判定は `gfx1200` / `gfx1201` に加え、`gfx_arch_is_gfx11_wmma()` が対応とする gfx11 アーキテクチャも許可します。別の GPU、デバイス取得失敗、環境変数が無効の場合は `false` を返して warp scorer に fallback します。
- prompt の QSA selection 経路であること。ここで確認した `qsa_block_scores_tc()` の実利用箇所は `src/prefill/prefill.cpp` にあり、decode 側の `qsa_block_scores()` 呼び出しにはこの WMMA 環境変数による分岐はありません。

## 実行時の詳細

prefill は各 selection batch について `qsa_block_scores_tc()` を先に試します。戻り値が `false` の場合、呼び出し元は `qsa_block_scores()` を実行して warp scorer を使います。`STRATA_SELECT_OLD` が設定されている場合は、WMMA scorer の試行自体を飛ばします。この関連変数は設定値の内容でなく、設定の有無で判定します。

HIP で WMMA scorer が選択されると、pooled block score 用の `block_scores_wmma_kernel` と末尾 block 用の `block_scores_tail_kernel` を起動します。カーネル起動後の CUDA/HIP runtime エラーは `qsa_block_scores_tc: %s` と stderr に出し、プロセスを `exit(1)` で終了します。環境変数が未設定・無効、または GPU 非対応の場合に、この関数から専用のログは出ません。

`sycl/src/kernels/cuda/qsa_select.dp.cpp` にも同名のコード断片がありますが、変数読み取りは `#if defined(__HIPCC__)` 内です。SYCL 側の `#else` は tensor-core kernel が未移植として `false` を返すため、SYCL の通常経路ではこの環境変数による WMMA scorer 選択は行われず、呼び出し元が別 scorer を使います。

## 文書・測定値との照合

`docs/AMD_HIP.md` はこの変数を gfx12 向けの opt-in block scorer として説明し、R9700 で 16K prompt / 262K context の測定に +1.5% と記録しています。同文書は 254/256 queries の選択が warp scorer と同じだったとも記載しています。これは資料に記された条件下の値であり、この調査で性能測定を再実行したものではありません。ソースの device guard は gfx12 に加えて gfx11 WMMA 対応アーキテクチャも通すため、資料の「gfx12」よりコード上の許可範囲が広くなっています。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1118-1138` — 共通形状条件、HIP 時の環境変数判定、device guard、WMMA/tail kernel 起動とエラー処理。
- `src/kernels/cuda/qsa_select.cu:443-457` — gfx1200 / gfx1201 および gfx11 WMMA 対応 GPU の判定。
- `src/prefill/prefill.cpp:2760-2775` — prefill からの呼び出し、`STRATA_SELECT_OLD` による抑止、warp scorer への fallback。
- `src/core/layer.cpp:1128`、`src/core/verify.cpp:1370-1381` — decode 側が `qsa_block_scores()` を呼ぶ箇所。
- `sycl/src/kernels/cuda/qsa_select.dp.cpp:1646-1698`、`sycl/src/prefill/prefill.cpp:3018-3031` — SYCL 側の guard と fallback。
- `docs/AMD_HIP.md:352-356` — opt-in 説明と測定値。
