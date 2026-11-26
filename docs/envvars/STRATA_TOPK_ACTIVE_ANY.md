# `STRATA_TOPK_ACTIVE_ANY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA 系 QSA block top-k の active-block 数を使う dispatch を、Turing（Compute Capability 7.5）以外のデバイスでも有効にする内部 override です。通常は Turing 判定が true のときに限って、既知の active-block 数を top-k の探索範囲として使います。この変数が有効だと、そのデバイス判定を迂回します。探索範囲 `reach` と register kernel の収容判定 `fit` が変わり、register / wide kernel の選択に影響します（`engine/src/kernels/cuda/qsa_select.cu:3047-3059,3082-3103`、SYCL 移植版 `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2033-2045,2062-2070`）。

ソースコメントは parity test 用の強制スイッチとしています。通常のユーザー向け設定として案内されているものではありません。テストは active-bound 経路と capacity 経路の選択 ID を比較する目的で、この変数を設定します（`engine/src/kernels/qsa_topk_active_parity.cpp:53-64,81-100`、登録箇所 `engine/cmake/strata_gpu_engine.cmake:174-185`）。

この変数は top-k 選択条件や scores 自体を変更するものではなく、カーネル dispatch の入力範囲を選びます。テストコードは選択 ID の一致を検査していますが、その結果をあらゆる実行条件で保証する測定としては扱いません。

## 値と判定

CUDA 実装と SYCL 移植実装の読み取りは同じ規則です。`getenv` の結果が非 null で、先頭 1 byte が ASCII `'1'` のときだけ true です。数値・真偽値としての parse はせず、残りの文字を検査しません。未設定、空文字、先頭が `1` 以外なら false です（`engine/src/kernels/cuda/qsa_select.cu:3052-3056`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2038-2042`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA (`!__HIPCC__`) および同じ条件の SYCL 移植実装 | false | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `01` |
| HIP (`__HIPCC__`) | この変数を読み取らない。分岐は `active_blocks > 0` のみ | 該当なし | 該当なし |

空白除去、大文字小文字変換、文字列全体の妥当性検査はありません。したがって `1anything` も有効です。値が true でも `STRATA_TOPK_CAPACITY_GUARD` が設定されていれば active-block dispatch は無効です。こちらは値の内容ではなく設定有無で判定され、空文字も設定ありです（同上）。

## 有効になる条件

- CUDA 系の該当 QSA top-k 実装であること。`__HIPCC__` のビルドでは対象変数を読まず、active-block が正数かだけを使います（`engine/src/kernels/cuda/qsa_select.cu:3044-3056`）。
- 呼び出し側が `active_blocks` を渡し、その値が `0` より大きく `max_blocks` 以下であること。プロンプトの prefill はバッチ最後の query の block index から `active = index + 1` を作って渡します（`engine/src/prefill/prefill.cpp:5371-5376,5392-5393`）。
- `STRATA_TOPK_CAPACITY_GUARD` が未設定であること。設定されていると `counted` は false です（`engine/src/kernels/cuda/qsa_select.cu:3051-3056`）。
- 関数より前に別の経路が返らないこと。`nq <= 0` は即時 return、対応可能な CUDA cluster 経路は先に実行され得ます。また `active_blocks <= 0` の場合に条件を満たせば split 経路が先に実行されます（`engine/src/kernels/cuda/qsa_select.cu:3021-3040`）。
- `STRATA_TOPK_OLD` が設定されると最終的に reference kernel が選ばれ、この override による dispatch 差は使われません（設定有無の判定と fallback: `engine/src/kernels/cuda/qsa_select.cu:3020,3072-3076`）。

## 実行時の詳細

対象値は `qsa_block_topk` 内の関数ローカル `static const bool` として初回評価時に読み取られ、同じ実装内では以後再読込されません。したがってプロセス起動後に環境を書き換えても、初回の `qsa_block_topk` 呼び出し後には反映されません（`engine/src/kernels/cuda/qsa_select.cu:3016-3017,3052-3054`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:2012-2013,2038-2040`）。

有効時は、`capacity_guard` が無効で、`active_blocks` が `1..max_blocks` に収まると `counted` が true になります。すると `reach` は `active_blocks`（`max_blocks` より小さい場合）となり、`fit` は `TK_T * TK_PER_MAX` になります。以降、`reach > fit` や `STRATA_TOPK_STREAM`、固定のしきい値などで register / wide kernel または reference kernel を選びます。変数は kernel 選択に関わり、QSA block top-k が返す選択 ID の計算規則を書き換える処理はありません（`engine/src/kernels/cuda/qsa_select.cu:3055-3103`）。

通常の Turing デバイスでは `topk_active_turing_device()` がデバイスを判定し、呼び出しスレッドごとに現在デバイスの判定結果を cache します。`STRATA_TOPK_ACTIVE_ANY=1` はこの判定を任意の CUDA デバイスで true にします（`engine/src/kernels/cuda/qsa_select.cu:2461-2476,3054-3056`）。SYCL 移植版も現在デバイスの判定を cache しますが、同版の判定は compute capability 7.5 のみです（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1878-1905,2040-2042`）。

## ログと測定値

この変数の読み取りや有効化を知らせるログはありません。top-k kernel の起動エラー時には CUDA 実装が `qsa_block_topk: <CUDA error>`、split kernel では `qsa_block_topk (split): <CUDA error>` を stderr に出して終了コード 1 で終了します。geometry / cap が非対応の場合も `qsa_block_topk: unsupported geometry or cap` を出して終了します（`engine/src/kernels/cuda/qsa_select.cu:3078-3079,3104-3105`、split 経路 `3034-3039`）。

`docs/DETAILS.md` にはこの変数名の記載はありません（調査対象 HEAD で `STRATA_TOPK_ACTIVE_ANY` を検索して該当なし）。同資料とソースコメントには top-k 関連の一般説明・設計上の測定値がありますが、この override 自体を有効にした場合の独立した性能値は確認できませんでした。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2461-2476,3016-3105` — CUDA 実装、デバイス判定、active-bound と kernel dispatch。
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1878-1905,2012-2095` — SYCL 移植実装。
- `engine/src/prefill/prefill.cpp:5371-5393` — prefill から active-block 数を渡す経路。
- `engine/src/kernels/qsa_topk_active_parity.cpp:53-64,75-100` — test 内での設定と選択 ID の比較。
- `engine/cmake/strata_gpu_engine.cmake:174-185` — parity test のビルド・登録。
