# `STRATA_QSA_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA のブロックスコア計算で、最大 4 行（query）のとき `block_scores_rows_kernel` を選び、各 query の indexer score を計算します。query の値をレジスタに保持して multi kernel と異なる reduction 配置を使います。ソースコメントは、各和の対応と head 順の加算から multi kernel と同じ score bit になる設計と説明しています。選択結果そのものを直接決める変数ではなく、計算した score を後続の top-k に渡します。主な実装は `engine/src/kernels/cuda/qsa_select.cu` の `qsa_block_scores` と `qsa_block_scores_slot_groups` です（同ファイルは CUDA/HIP 共通 GPU ビルドに含まれます）。【`engine/src/kernels/cuda/qsa_select.cu:1067-1076,1078-1149,2018-2052,2194-2229`; `engine/cmake/strata_gpu_engine.cmake:1-8,90-96`】

## 値と判定

実装は `getenv` の結果について「文字列がちょうど `1` か」を比較します。数値変換はせず、前後の空白も取り除きません。設定値が有効なのは ASCII `1` 一文字だけです。【`engine/src/kernels/cuda/qsa_select.cu:2031-2034,2201-2205`】

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP の `qsa_block_scores` 経路 | `false`（ただし CUDA NVIDIA の起動時既定値が設定される場合を除く） | `1` | 空文字、`0`、`01`、`1 `、`true`、`True`、`-1` など |
| CUDA/HIP の slot-group 経路 | `false`（同上） | `1` | 空文字、`0`、`01`、`1 `、`true`、`True`、`-1` など |

この変数に CLI 引数による上書きはありません。CUDA NVIDIA の起動時既定値は、変数が未設定の場合にだけ追加されます。ユーザーが空文字を含む何らかの値を設定していれば、その値が保持されます。そのため空文字や `true` は「設定済み」でもこの機能の判定では無効です。【`engine/src/core/nv_defaults.cpp:222-234`】

## 有効になる条件

- 通常の `qsa_block_scores` 経路では `STRATA_SCORES_MULTI` が有効（unset または `atoi(value) != 0`）で、`nq <= 8` かつ `active_blocks <= 0` の分岐に入る必要があります。`STRATA_SCORES_MULTI=0`、`nq > 8`、または正の `active_blocks` を渡す経路ではこの変数による切替は行われません。【`engine/src/kernels/cuda/qsa_select.cu:1607-1610,2194-2205,2231-2277`】
- この経路で rows kernel が受け付けるのは `nq=1..4` と対応 geometry（index dimension 128、4 heads、block size 4）です。`nq=5..8` なら rows helper は `false` を返し、呼び出し元は multi/他の scorer に進みます。rows helper の geometry 不一致も `false` ですが、通常の `qsa_block_scores` 自体は先に unsupported geometry を検出すると stderr に出して `exit(1)` します。`nq<=0` はスコア処理を行いません。【`engine/src/kernels/cuda/qsa_select.cu:2194-2205,2280-2293`】
- slot-group 経路は verify の batch recording で `STRATA_BATCH_QSA_STREAM_OPT` が有効、かつ `te > tb` で group が作られる場合にだけ呼ばれます。group 数超過や不正な `ntok` / null buffer 等では helper は `false` を返して通常の `qsa_block_scores` 呼び出しへ fallback します。一方、unsupported geometry は stderr に出して `exit(1)` します。ここで `STRATA_QSA_ROWS=1` が rows kernel を選ぶのは、全 group の最大 `ntok` が 4 以下の場合です。5..8 行なら grouped multi kernel です。【`engine/src/core/verify.cpp:2140-2168,2200-2215`; `engine/src/kernels/cuda/qsa_select.cu:2018-2052`】
- CUDA と HIP は `qsa_select.cu` を共有します。この環境変数の分岐は `__HIPCC__` 限定外にあり、明示設定は HIP 側でも同じ関数条件に達したときに評価されます。一方、NVIDIA arch の自動既定値設定は HIP ではなく CUDA 起動処理に限られます。【`engine/cmake/strata_gpu_engine.cmake:1-8,90-96`; `engine/src/kernels/cuda/qsa_select.cu:2194-2205`; `engine/src/program/generate.cpp:4421-4428`】
- CUDA の自動既定値は、起動時に CUDA device が 1 台以上あり、全可視 device の compute capability が同じ場合に `apply_nv_defaults` が呼ばれる条件に依存します。sm_86 では `STRATA_SM86_PERF` が先頭文字 `0` でなければ `1` を既定設定します（この sm_86 分岐は `STRATA_DEFAULTS=026` だけでは無効化されません）。sm_89 では `STRATA_SM89_PERF` が先頭文字 `0` でなく、`STRATA_DEFAULTS` が `026` 相当でない場合に `1` を設定します。sm_86/sm_89 以外、この既定値一覧にはこの変数がありません。環境変数をユーザーが先に設定すれば、値を問わず既定値より優先されます。【`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:15-18,37-42,51-58,75-100,222-234`; `engine/include/strata/core/defaults_026.hpp:21-29`】

## 実行時の詳細

通常経路と slot-group 経路はそれぞれ別の関数内 `static const bool` で環境値を初回評価時にキャッシュします。通常経路は `qsa_block_scores` の multi-kernel 分岐に初めて入り、slot-group 経路は `qsa_block_scores_slot_groups` が有効な geometry/group を確認した後に初めて通ったときに読みます。その後プロセス内で環境を変更しても、各経路のキャッシュ値には反映されません。【`engine/src/kernels/cuda/qsa_select.cu:2018-2034,2194-2205`】

通常経路で有効なら 1..4 query 用のテンプレート kernel を起動します。無効なら `STRATA_SCORES_HALVE` が有効な場合はその kernel、それ以外は `block_scores_multi_kernel` に進みます。rows kernel は pooled/dead indexer keys、query、step 情報から各 query/block の score を出力し、呼び出し元がその score を top-k に渡します。slot-group 経路では各 slot group ごとに rows kernel または grouped multi kernel を起動し、続いて batch rows 全体の top-k が実行されます。【`engine/src/kernels/cuda/qsa_select.cu:2201-2229,2280-2292,2018-2052`; `engine/src/core/verify.cpp:2200-2215`】

通常の prompt scorer は positive `active_blocks` を渡す経路で、この環境変数を判定する `active_blocks <= 0` 分岐を通りません。verify decode の呼び出し元は、通常の per-row/grouped selection から `qsa_block_scores` を呼びます。【`engine/src/prefill/prefill.cpp:5374-5392,9445-9456`; `engine/src/core/verify.cpp:2207-2212,2242-2249,2253-2274`】

例外として、prefill 内の `STRATA_IDX_FP16_CHECK` 診断は `qsa_block_scores` を `active_blocks` なしで呼ぶため、他の条件が合えばこの切替対象になります。【`engine/src/prefill/prefill.cpp:5468-5485`】

## ログと測定値

`STRATA_QSA_ROWS` 専用の有効・無効ログはありません。CUDA の NVIDIA 既定値を新たに注入した起動では `apply_nv_defaults` の一般ログが stderr に出て、設定一覧に `QSA_ROWS` と表示されます。ユーザーが値を設定済みの場合はその変数を一覧に含めません。【`engine/src/core/nv_defaults.cpp:222-255`】

kernel launch error は stderr に `qsa_block_scores rows: %s`、`qsa_block_scores_slot_groups: %s` などの形式で CUDA runtime error を出し、`exit(1)` します。環境値が無効・適用条件が不成立の場合に、この変数由来の警告やエラーはありません。【`engine/src/kernels/cuda/qsa_select.cu:2011-2015,2050-2052,2284-2292`】

Strata の `docs/QSAROWS.md` は RTX 2080 Ti と RTX 3060、131K context における `qsa_block_scores` の per-call 値を掲載しています（同文書の記載値: RTX 2080 Ti は multi 47.2/56.9/78.2/101.2 µs、rows 設定時 36.2/38.0/49.2/54.6 µs、RTX 3060 は multi 73.4/109.4/151.9/193.5 µs、rows 設定時 63.3/75.5/98.0/130.2 µs、各列 T=1..4）。これは文書中のマイクロベンチ値であり、本調査で再測定したものではありません。【`docs/QSAROWS.md:31-55`】

同文書の「opt-in」「HIP は対象外」という記述は現行実装と一致しません。CUDA 起動時は条件次第で未設定の値が自動的に `1` になり、HIP build も共有する `qsa_select.cu` に同じ明示値判定があります。また `qsa_block_scores` の判定分岐は prompt の通常 scorer ではなく、verify decode 側で使われます。【`engine/src/core/nv_defaults.cpp:41-58,75-100,222-234`; `engine/cmake/strata_gpu_engine.cmake:1-8,90-96`; `engine/src/kernels/cuda/qsa_select.cu:2194-2205`; `engine/src/prefill/prefill.cpp:5374-5392,9445-9456`; `docs/QSAROWS.md:1-5`】

## 根拠

- 実際の読み取り、判定、通常 kernel の fallback: `engine/src/kernels/cuda/qsa_select.cu:2018-2052,2194-2292`
- kernel の score 計算: `engine/src/kernels/cuda/qsa_select.cu:1067-1149`
- verify slot-group 呼び出し条件: `engine/src/core/verify.cpp:2140-2168,2200-2215`
- CUDA 起動時の既定値適用: `engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:15-18,37-103,222-255`
- CUDA/HIP 共通ビルド: `engine/cmake/strata_gpu_engine.cmake:1-8,90-96`
