# `STRATA_QSA_EARLY_EXIT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

QSA の block score 計算で使う複数クエリ用 CUDA カーネルにおいて、処理対象 block が batch 内の最大 `n_bid` より先にある CTA を、query データの shared memory へのロード前に return させます。無効にすると従来の順序で、全 CTA が先に query をロードしてから不要な CTA も終了します。スコアの計算式や選択方式を切り替える変数ではありません。

## 値と判定

値は文字列比較ではなく C の `std::atoi` で整数に変換し、変換結果が 0 かどうかで判定します。

| 環境変数の状態・値 | `early` |
|---|---:|
| 未設定 | 有効（既定値 `true`） |
| 空文字 | 無効（`atoi("") == 0`） |
| `0`、`00`、`junk`、`0junk` | 無効（変換結果が 0） |
| `1`、`-1`、`2`、`1junk` | 有効（変換結果が非 0） |

`atoi` が整数変換を始められない文字列は 0 として扱われ、変換後の値だけを見るため、数値の後ろに文字があっても先頭の整数が非 0 なら有効です。空白や符号も `atoi` の整数変換規則に従います。コードは範囲外入力を別途検査していません。

読み取り結果は関数内の `static const bool` に保存されます。該当経路で初めて評価された後は、同じプロセスで環境値を変更しても再評価されません。

## 有効になる条件

`qsa_block_scores()` が次をすべて満たす場合にだけ、この変数の判定が行われ、設定がカーネルへ渡ります。

- `STRATA_SCORES_MULTI` が有効である。こちらも未設定なら既定有効で、設定時は `atoi(value) != 0`。
- クエリ数 `nq` が `MQ` 以下。`MQ` は 8。
- `active_blocks <= 0` である（通常の decode / pooled16 経路など、呼び出し側が active-block 数を指定していない経路）。

いずれかを満たさない場合は通常の `block_scores_kernel` が選ばれ、この変数の値はその呼び出しには作用しません。たとえば prefill の通常選択は active block 数を渡すため対象外です。decode の QSA 呼び出しや `STRATA_IDX_FP16_CHECK` の pooled16 再計算は active count なしで呼ばれ、`nq <= 8` なら対象の分岐に入ります。

## 実行時の詳細

複数クエリ用カーネルは固定 256 CTA で起動します。各 CTA はまず query ごとの `n_kv` / `n_bid` を shared memory に読み、同期後に batch 内最大 `n_bid`（`top`）を求めます。有効時は `blockIdx.x * SCORE_WARPS > top` の CTA が return します。この条件は CTA 内で一様なので、return しない CTA ではその後 query 配列を shared memory にロードして同期し、score 計算へ進みます。無効時は query 配列のロードと同期を先に行い、その後 `top` を求めます。

カーネル内のコメントは、早期 return で固定 grid のうち仕事のない CTA が query staging を避けられること、また両経路の score は同じ bit になることを記しています。これは実装コメント上の説明であり、この調査では実行や性能測定による独立検証はしていません。環境変数によるログ出力はありません。カーネル起動直後に CUDA の起動エラーを検出した場合は、既存コードが `qsa_block_scores multi: ...` を stderr に出し `exit(1)` しますが、このエラー処理は同変数固有ではありません。

SYCL ディレクトリ内の DPCT 生成ファイルにも同じ env 判定と分岐が含まれています。ただし調査手順の対象外である生成済みコードは根拠として扱わず、上記の詳細は Strata の CUDA ソースに基づいています。`docs/DETAILS.md` は QSA decode 選択の cluster 切替などを記載していますが、この変数の説明や性能測定値は掲載していません。

## 根拠

- `src/kernels/cuda/qsa_select.cu:810-866`: 複数クエリ用カーネル、query staging の順序、`top` を超える CTA の早期 return。
- `src/kernels/cuda/qsa_select.cu:1092-1115`: Strata 所有の非生成実装における唯一の読み取り箇所、値の判定、分岐条件、カーネルへの引き渡し、起動エラー処理。
- `include/strata/kernels/qsa_select.hpp:26-30`: `active_blocks` の API 契約。
- `src/core/verify.cpp:1367-1384`, `src/core/layer.cpp:1122-1129`: decode 側の呼び出し。
- `src/prefill/prefill.cpp:2760-2775`: 通常 prefill の呼び出しが active block 数を指定すること。
- `src/prefill/prefill.cpp:2797-2822`: pooled16 の検査経路が active block 数なしで呼ぶこと。
- `docs/DETAILS.md:24-29`: QSA decode 選択の概要。`STRATA_QSA_EARLY_EXIT` 自体の説明はありません。
