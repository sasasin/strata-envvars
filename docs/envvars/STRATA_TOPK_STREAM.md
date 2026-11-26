# `STRATA_TOPK_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

QSA の block top-k 選択で、register kernel の収まる範囲内にある一部の大きな選択を wide kernel にする分岐を制御する。未設定時はこの分岐が有効で、値の先頭文字が `0` のときだけ無効になる。無効にすると対象範囲では register kernel に戻るが、register kernel の容量を超える選択は引き続き wide kernel を使う。選択 ID の意味を切り替える設定ではなく、kernel の選択を変える。実装は CUDA/HIP 共用の `qsa_block_topk` と SYCL 移植版にある（`engine/src/kernels/cuda/qsa_select.cu:3082-3103`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2062-2115`）。

## 値と判定

両実装とも関数内 `static const bool` の初回初期化時に `std::getenv` を呼び、未設定なら有効、設定済みなら `v[0] != '0'` を有効条件とする。文字列全体の数値変換・比較はしない。

| ビルド | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP (`engine/src/kernels/cuda/qsa_select.cu`) と SYCL 移植版 (`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp`) | 有効 | 空文字、`1`、`true`、`00` 以外で先頭が `0` でない値（例: `true`、` 0`、`0x` は有効） | 先頭が ASCII `0` の値（例: `0`、`00anything`） |

大文字小文字・後続文字・数値としての妥当性は判定しない。空文字は未設定ではなく設定済みだが、空文字列の先頭 `\0` は `'0'` ではないため有効になる（`engine/src/kernels/cuda/qsa_select.cu:3087-3090`, `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2066-2069`）。

## 有効になる条件

- `qsa_block_topk` に到達する QSA block top-k 経路であること。QSA layer では `g_fast_select` が有効な分岐がこの関数を呼ぶ（`engine/src/core/layer.cpp:1277-1285`）。prefill の選択経路も active block 数を渡して呼ぶ（例: `engine/src/prefill/prefill.cpp:5371-5393`）。
- `STRATA_TOPK_OLD` が設定されていないこと。これは値の内容を問わず旧 reference kernel に戻すため、stream の判定に先行してこの変数を無効化する（`engine/src/kernels/cuda/qsa_select.cu:3016-3021,3067-3075`）。
- この切替が影響するのは `counted` が真で `reach > 22528` のとき、かつ wide kernel の容量超過だけを理由に wide kernel が選ばれる場合ではない範囲。`reach` は有効な active block 数（それが `max_blocks` 未満の場合）または `max_blocks`、`fit` は `TK_T * TK_PER_MAX`（counted 時）または `TK_T * TK_PER`（非 counted 時）である（`engine/src/kernels/cuda/qsa_select.cu:3042-3059,3087-3103`）。
- CUDA と SYCL では `counted` は `STRATA_TOPK_CAPACITY_GUARD` が未設定で、active block 数が正かつ容量以下、さらに Turing/SM70 世代（または `STRATA_TOPK_ACTIVE_ANY` の先頭文字が `1`）のときに成立する。`STRATA_TOPK_CAPACITY_GUARD` は値を問わず設定されると `counted` を無効にする。`STRATA_TOPK_ACTIVE_ANY` は先頭文字が `1` の場合だけ任意の CUDA device で counted を許す（`engine/src/kernels/cuda/qsa_select.cu:3046-3056`; SYCL 移植版: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2032-2042`）。
- HIP では `counted` は `active_blocks > 0` のみで決まる。register kernel の閾値は `TK_T * TK_PER_MAX = 1024 * 66` blocks で、CUDA の `1024 * 33` blocks より広い（`engine/src/kernels/cuda/qsa_select.cu:702-710,3044-3059`）。
- CUDA では `reach > fit` のときは `STRATA_TOPK_STREAM=0` 相当でも wide kernel が必要なため、この変数はそれを register kernel に戻さない。HIP も容量超過時は wide kernel を使う（同: `3060-3103`）。逆に counted が偽の呼び出しでは `reach > 22528` だけでは有効にならず、容量超過時の wide kernel 選択だけが残る。
- NVIDIA の SM90 以降で cluster kernel が対応し、`STRATA_QSA_CLUSTER` が有効、かつ query 数などの条件を満たす場合は先に cluster kernel が実行され、この変数の判定に進まない。cluster は既定で有効で、`STRATA_QSA_CLUSTER=0` なら無効（`engine/src/kernels/cuda/qsa_select.cu:3022-3030,2479-2505`）。
- CUDA の decode で split kernel が成功する呼び出しも先に return する（`active_blocks <= 0` などが条件）。したがってこの設定の主な効きどころは counted な prompt selection であり、全 decode・全 top-k 呼び出しに適用されるものではない（`engine/src/kernels/cuda/qsa_select.cu:3032-3040`）。
- `STRATA_EXPERIMENTAL_SM60` build で `qsa_block_topk_long` の multi kernel 条件を満たし、その呼び出しが成功すると `qsa_block_topk` に進まないため、この変数はその呼び出しにも影響しない（`engine/src/kernels/cuda/qsa_select.cu:3219-3245`）。

## 実行時の詳細

CUDA/HIP の `qsa_block_topk` は、旧 kernel・CUDA の cluster/split 経路を先に判定した後、`counted`、`reach`、`fit` を計算する。旧 kernel や HIP の小さすぎる選択は reference kernel に戻る。続いて `reach > fit` なら wide kernel、または stream 判定が有効で `counted && reach > 22528` なら wide kernel を起動する。それ以外は `reach <= 1024 * 33` で register kernel、残りでは `TK_PER_MAX` の register kernel を使う。設定が `0` で threshold band にいる場合は、この通常の register kernel 分岐へ進む（`engine/src/kernels/cuda/qsa_select.cu:3058-3105`）。SYCL 移植版にも同じ `reach` / `fit` / `22528` 判定がある（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2044-2115`）。

閾値の `22528` blocks は、block あたり 4 cells のこの選択形状では 90,112 cells に相当する。CUDA では counted 時の register 上限が 33,792 blocks、HIP では 67,584 blocks なので、`0` が切り替えられる band はそれぞれ `22528 < reach <= fit`。閾値と `TK_PER` はソースの定数・分岐からの換算である（`engine/src/kernels/cuda/qsa_select.cu:24,702-710,3058-3103`）。

環境変数は `qsa_block_topk` の初回呼び出しで `static` にキャッシュされ、同一プロセス内で後から環境を書き換えても再評価されない。CLI 引数や設定ファイルとの優先順位・子プロセスへの転送を行う Strata 所有コードは確認できなかった。`qsa_block_topk` は kernel を選んで ID バッファに出力し、その後の QSA 処理がその ID を使って KV block を解決する（`engine/src/core/layer.cpp:1277-1289`）。

## ログと測定値

この変数の値や選んだ kernel を報告するログはない。選択関数には geometry/capacity 不整合時の `qsa_block_topk: unsupported geometry or cap`、CUDA kernel 起動エラー時の `qsa_block_topk: %s` と終了処理があるが、これは stream 値固有の警告ではない（`engine/src/kernels/cuda/qsa_select.cu:3078-3105`）。

`docs/TROUBLESHOOTING.md:251-252` は Turing（RTX 20）の約 90K tokens 超の prompt について、同じ ID を保ち wide kernel を使い、`STRATA_TOPK_STREAM=0` で旧 kernel に戻すと説明する。ソースコメントにも 131K での計測値があるが、機種・実行条件が特定できる詳細がないため、一般的な性能値としては記載しない（`engine/src/kernels/cuda/qsa_select.cu:3082-3086`）。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3016-3105` — CUDA/HIP の読み取り、dispatch 条件、kernel 起動、失敗経路。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2115` — SYCL 移植版の読み取りと dispatch。
- `engine/src/kernels/cuda/qsa_select.cu:699-710` — register kernel の thread 数・容量定数。
- `engine/src/core/layer.cpp:1277-1289` — QSA layer の block selection と後続利用。
- `engine/src/prefill/prefill.cpp:5371-5393` — prefill 呼び出し時の active block 数。
- `docs/TROUBLESHOOTING.md:251-252` — Strata 資料の利用者向け記述。
