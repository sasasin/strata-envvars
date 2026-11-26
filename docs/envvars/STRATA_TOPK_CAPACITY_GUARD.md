# `STRATA_TOPK_CAPACITY_GUARD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA と SYCL の `qsa_block_topk` で、prompt など呼び出し側が渡す実 active-block 数を使った top-k dispatch を抑え、容量 (`max_blocks`) に基づく dispatch に戻すための切り替えです。環境変数を設定すると、active-block 数をもとにした `counted` 判定が必ず false になり、`reach` は `max_blocks` になります。したがって、入力上限に合わせて選ばれる register / wide / reference kernel の分岐が変わることがあります。`qsa_block_topk` は選択 ID を書き出す関数で、この変数はその kernel 選択に作用します（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3016-3021, 3042-3059, 3071-3105`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2017, 2028-2045, 2051-2103`）。

CUDA では active 数を使う最適化は Turing (sm_75) と、`STRATA_TOPK_ACTIVE_ANY` が先頭文字 `1` の場合に許されます。SYCL 側も同じ `counted` 判定を持ちますが、デバイス判定は major/minor が 7.5 の場合だけです。HIP では `__HIPCC__` 分岐によりこの環境変数を読まず、`active_blocks > 0` だけで `counted` を決めます（CUDA: `engine/src/kernels/cuda/qsa_select.cu:2461-2477, 3044-3057`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1878-1905, 2030-2042`）。

## 値と判定

両方の読み取り箇所は `std::getenv(...) != nullptr` の有無だけを見ます。未設定なら false、何らかの値が設定されていれば true です。空文字、`0`、`false`、不正な数値、前後の空白、大文字小文字の違いを解析・検証しません。境界値や clamp はありません。CLI 引数・設定ファイルによる値の上書きもこの判定箇所にはありません（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3051-3056`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2037-2042`）。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA (`__HIPCC__` なし) | `capacity_guard=false`。他条件が揃えば active 数を `reach` と `fit` に使用 | 空文字、`0`、`false`、`1`、任意の文字列。設定有無だけで guard が true | なし。値の内容は無視 |
| SYCL (`__HIPCC__` なし) | CUDA と同じ有無判定 | CUDA と同じ | なし。値の内容は無視 |
| HIP (`__HIPCC__` 定義) | この変数を参照しない | 該当なし | 該当なし。`counted` は `active_blocks > 0` で決まる |

## 有効になる条件

- CUDA / SYCL の該当ビルドで `qsa_block_topk` が `nq > 0` となり、関数内の guard 判定まで到達する必要があります。`nq <= 0` はその前に return します（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3016-3022`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2018`）。
- guard 判定より前に cluster または split kernel が成功して return した場合、この変数による dispatch 変更はありません。CUDA は cluster を先に試し、続いて条件を満たす split kernel を試します。SYCL の cluster 関数は現行コードで `false` を返し、selector はその後 guard 判定へ進みます（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3022-3041`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1907-1913, 2018-2027`）。
- CUDA で guard が未設定のとき `counted` が true になるには、`active_blocks > 0`、`active_blocks <= max_blocks`、および Turing デバイスか `STRATA_TOPK_ACTIVE_ANY` の先頭文字が `1` であることが必要です。デバイス判定は呼び出しスレッドごとに現在 device を cache し、sm_75 または `sm70_default_on(...)` を受理します（`engine/src/kernels/cuda/qsa_select.cu:2461-2477, 3052-3056`）。
- SYCL では `counted` の数値条件は同じで、通常のデバイス判定は major/minor `7.5` のみです。`STRATA_TOPK_ACTIVE_ANY` が先頭文字 `1` ならデバイス判定を迂回します（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1878-1905, 2038-2042`）。
- `active_blocks <= 0`、`active_blocks > max_blocks`、またはデバイス条件が満たされない場合は `counted=false` となり、guard の設定有無で `reach` は変わりません。
- `STRATA_TOPK_OLD` が設定されると後段で reference kernel を選ぶため、guard による後続 kernel 選択差は現れません（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3019-3021, 3069-3075`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2015-2017, 2046-2056`）。
- HIP はこの変数の設定に関係なく HIP 用分岐で active 数のみを使います。CUDA/SYCL 用のデバイス判定や `STRATA_TOPK_ACTIVE_ANY` を含む `#else` 分岐には入りません（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3044-3057`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2030-2042`）。
- 読み取り箇所にモデル状態、サーバーモード、CLI オプションによる追加条件はありません。実際に active 数を渡す prompt 経路の例では、prefill が batch の最後の query の `n_bid + 1` を算出して `qsa_block_topk` に渡します（`engine/src/prefill/prefill.cpp:5371-5393`）。

## 実行時の詳細

環境変数は `qsa_block_topk` 内の関数ローカル `static const bool` として初めて該当行に到達した時に読み、以降そのプロセス内で再読み込みしません。したがって、プロセス起動後でも最初に判定へ到達する前の変更は反映されますが、その後の変更は反映されません。CUDA と SYCL は別の実装・別の static 変数です（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3016-3022, 3051`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2018, 2037`）。

guard が false なら、条件を満たす CUDA/SYCL 経路で `counted=true` となり、`reach=min(active_blocks, max_blocks)` と `fit=TK_T * TK_PER_MAX` が使われます。guard が true、または他の条件で counted でない場合は `reach=max_blocks`、`fit=TK_T * TK_PER` です。その値を用いて reference / wide / register kernel の分岐が行われます。CUDA/SYCL では `STRATA_TOPK_STREAM` も wide kernel の分岐条件に関係します。HIP は独自の `kRegMinBlocks` 条件を使い、capacity guard の値は関与しません（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3055-3103`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2041-2103`）。

## ログと測定値

この変数を読んだことや guard が有効になったことを示す専用ログはありません。後続の共通失敗経路として、geometry / cap が未対応なら `qsa_block_topk: unsupported geometry or cap` を stderr に出して終了し、CUDA kernel launch エラーなら `qsa_block_topk: <CUDA error>` を出して終了します（CUDA: `engine/src/kernels/cuda/qsa_select.cu:3078-3105`; SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2058-2059`）。この変数固有の性能測定値は確認できません。`docs/DETAILS.md` にもこの名前や当該 guard の説明は見つからず、ここではソース上の dispatch だけを記述しています。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2461-2477, 3016-3105` — CUDA/HIP の device gate、値の読み取り、kernel dispatch と共通エラー経路。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1878-1905, 2012-2103` — SYCL の device gate、値の読み取り、kernel dispatch と共通エラー経路。
- `engine/src/prefill/prefill.cpp:5371-5393` — prefill 側で active-block 数を算出して selector に渡す経路。
- `engine/sycl/CMakeLists.txt:1-6` — SYCL build で CUDA 側ソースに対応する `.dp.cpp` の移植版を使う説明。
