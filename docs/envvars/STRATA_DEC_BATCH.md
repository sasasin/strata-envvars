# `STRATA_DEC_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系と SYCL の verifier が、複数行をまとめて処理する decode/verify window の経路を使うかを制御する。未設定では有効、`0` 相当では対象の処理をトークン単位に戻す。window の query/key/value 投影・RoPE・KV/indexer 追記、router、expert combine、hyper-connection write など複数の箇所に適用される（CUDA/HIP 系: `engine/src/core/verify.cpp:1489,2059-2060,2105-2110,2352-2355,2636-2660,2956-2964,2984-2988`; SYCL: `engine/sycl/src/core/verify.cpp:1048,1342-1352,1367-1418,1576-1605,1815-1823,1839-1843`）。また native shared expert の gate projection も複数行で実行する分岐があり、expert source の mapped-hit 行を GPU 側でゼロ化済みとして扱う条件にも使われる（`engine/src/kernels/cuda/shared_expert.cu:263-280`; `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:379-420`; `engine/src/core/expert_source.cpp:5727-5735,5827-5835`; `engine/sycl/src/core/expert_source.cpp:2724-2728,2762-2769`）。

この変数は出力や選択結果を直接指定する CLI 引数ではない。multi-row kernel が選べるかを変える。個々のコードコメントは一部の演算について行ごとの算術が single-token 経路と同じと説明するが、このフラグが全モデル・全機能で出力同一性を保証するという記述はない（CUDA/HIP: `engine/src/core/verify.cpp:2047-2059,2629-2655`; SYCL: `engine/sycl/src/core/verify.cpp:1341-1347,1576-1601`）。

## 値と判定

読み取りは `std::getenv("STRATA_DEC_BATCH")` の後 `std::atoi`。各読み取り箇所で「未設定なら true、設定されていれば `atoi(value) != 0`」を判定する。したがって空文字、数字で始まらない文字列、`0`、`0anything` は false。`1`、`-1`、`2`、`1anything` は true（`atoi` が数値として変換する先頭部分を使う）。先頭空白は `atoi` の規則で読み飛ばされる。`true`/`false` は文字列として認識されず、どちらも `atoi` は 0 を返す。大文字小文字の比較はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP verifier、SYCL verifier、expert source、native shared expert の各読み取り | 有効 (`true`) | `1`, `2`, `-1`, `1junk` | 空文字, `0`, `0anything`, `false`, `junk` |

既定値と判定は読み取り箇所ごとに同じで、CLI 引数や設定ファイルによる上書き処理はこれらの箇所にない。`STRATA_NO_BATCH_KV_STEP=1` は verifier の KV/indexer 追記を別途逐次化し、`STRATA_NO_MULTI_GR=1` は GR write を別途逐次化するため、`STRATA_DEC_BATCH` が有効でも該当処理はまとめられない（`engine/src/core/verify.cpp:348-349,2105-2110,2352-2355,2984-2988`; SYCL: `engine/sycl/src/core/verify.cpp:1369-1389,1409-1418,1839-1843`）。

## 有効になる条件

- 実行経路が該当 verifier または native shared expert に到達すること。環境変数を読むだけで、別の通常 decode 経路を強制的に batch 化するものではない（CUDA/HIP verifier の `Verifier::record_window`: `engine/src/core/verify.cpp:1468-1489`; SYCL: `engine/sycl/src/core/verify.cpp:1018-1048`）。
- 多くの multi-row 分岐は `n > 1` を条件にする。1 行の window ではこの設定による複数行処理は発生しない（例: `engine/src/core/verify.cpp:2059,2636,2956`; SYCL: `engine/sycl/src/core/verify.cpp:1343,1583,1815`）。
- QSA の query/key/value 複数行経路は native QSA と native RoPE が使える場合に限られる。CUDA/HIP ではさらに `STRATA_DF_QB_Q4` が unset または `atoi != 0` であることが必要で、KV が Q4 のとき `STRATA_DF_QB_Q4=0` ならこの経路を使わない。SYCL 側は `st.kv_q4` の場合に無効（`engine/src/core/verify.cpp:2035-2059`; `engine/sycl/src/core/verify.cpp:1338-1347`）。KV/indexer の一括追記は、さらに `STRATA_NO_BATCH_KV_STEP` が無効で、batch-rec window でないことが条件（CUDA/HIP: `engine/src/core/verify.cpp:2105-2112,2352-2355`; SYCL: `engine/sycl/src/core/verify.cpp:1367-1389,1409-1418`）。
- Router の一括経路は backend の native router・expert 数・top-k などの条件にも依存する。CUDA/HIP では native 経路が `NE == 512 && K == 10`、または `route_window_on()` のとき。SYCL native 経路は `NE == 512 || NE == 256` と `K == 10`、HIP gfx906 では別の `moe_route_window` 経路がある（CUDA/HIP: `engine/src/core/verify.cpp:2631-2660`; SYCL: `engine/sycl/src/core/verify.cpp:1578-1605`）。条件が合わない場合は `moe_route` の行ループへ進む。
- multi-row MoE combine には `native_moe_combine_enabled()` も必要。それ以外では `moe_combine_parts` を行ごとに呼ぶ（CUDA/HIP: `engine/src/core/verify.cpp:2944-2964`; SYCL: `engine/sycl/src/core/verify.cpp:1810-1823`）。shared expert の gate を複数行で計算する分岐にはさらに `native_bf16` と `n_tok > 1` が必要。`gate_deferred` の場合はその分岐より前に関数から戻る（CUDA: `engine/src/kernels/cuda/shared_expert.cu:216-220,258-280`; SYCL: `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-320,355-420`）。
- expert source の `gpu_zeroes_hits` は値が有効なだけでは使われず、`d.plan != nullptr`、window entry 数が上限以下、`n <= d.plan->cap`、`STRATA_VERIFY_DEVICE_PLAN` と（CUDA/HIP では）`STRATA_VERIFY_DEVICE_HITS` の両方が有効でないことも条件。SYCL は `STRATA_VERIFY_DEVICE_PLAN` のみを確認する（CUDA/HIP: `engine/src/core/expert_source.cpp:5730-5735`; SYCL: `engine/sycl/src/core/expert_source.cpp:2727-2728`）。この条件を満たすと kind 0/1 の hit 行をホストで再度ゼロ化しない。
- ソース上の読み取りは CUDA/HIP 系と SYCL 系にある。OS による値規則の差は見つからない。適用されない backend/build 経路での動作は、これらの読み取り箇所からは判断しない。

## 実行時の詳細

`Verifier::record_window` 内では最初にその関数が実行されたときに関数ローカル `static const bool dec_batch` が評価され、以後そのプロセス内で同じ関数の値を再利用する（CUDA/HIP: `engine/src/core/verify.cpp:1468-1489`; SYCL: `engine/sycl/src/core/verify.cpp:1018-1048`）。expert source と CUDA/SYCL shared-expert 関数にも別のローカル static があるため、それぞれの関数で初回評価時に独立してキャッシュされる（`engine/src/core/expert_source.cpp:5727`; `engine/sycl/src/core/expert_source.cpp:2724`; `engine/src/kernels/cuda/shared_expert.cu:263`; `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:379`）。したがって初回評価後にプロセス環境を変更しても、すでに評価済みの static には反映されない。読み取り時点はプロセス起動時とは限らず、それぞれの関数の初回到達時である。

有効時、条件を満たす verifier 処理は window の複数行を一括で投影・追記・router・combine 等へ渡し、条件が成立しないか値が false の場合は行ループの経路へ進む。無効時も `STRATA_DEC_BATCH` 自体によるエラーや終了処理はない。CUDA/HIP の verifier には batch-rec window 時、`dec_batch` と `STRATA_BATCH_SLOT_RUNS` の両方が有効なら同じ slot の行をまとめる別分岐もある（`engine/src/core/verify.cpp:1490-1501`）。SYCL にこの `slot_runs` 分岐はない。

expert source では、GPU による mapped-row copy が hit 行をゼロ化する場合に限り、後続の CPU 側 `memset` を省く。`STRATA_VERIFY_DEVICE_PLAN=1`（CUDA/HIP では `STRATA_VERIFY_DEVICE_HITS=1` も）を使う経路では、この GPU-side zeroing 判定から外れる（`engine/src/core/expert_source.cpp:5727-5735,5827-5835`; `engine/sycl/src/core/expert_source.cpp:2724-2728,2762-2769`）。

## ログと測定値

この変数専用の警告・ログ・失敗文言はない。CUDA/HIP verifier は router 分岐後に `router layer: batched native router=...` を `dispatch::notef` で通知し、combine では `combine layer: kind ... (0 per-token, 1 multi, 2 multi+hits, 3 multi+hits gated)` を通知する。ただしこれらは実際の経路状態を示す診断であり、`STRATA_DEC_BATCH` の値そのものの表示ではない（`engine/src/core/verify.cpp:2662-2663,2944`）。SYCL 側に同じ router/combine 文言の `notef` はない。エラー時は router/combine/shared expert の失敗が verifier の `err` に設定される（例: `engine/src/core/verify.cpp:2646,2752-2755,2956-2964`; SYCL router/combine: `engine/sycl/src/core/verify.cpp:1593,1811-1823`）。この変数による起動失敗や終了コードの分岐はない。

`docs/DETAILS.md` の opt-in switches 表にはこの変数の仕様・測定値の記載がない。リポジトリ内の過去ベンチ記録には設定値を使った比較があるが、現行コードの仕様や一般的な性能値の根拠にはしていない。

## 根拠

- `engine/src/core/verify.cpp:1468-1501,2035-2060,2105-2120,2350-2355,2631-2663,2737-2755,2847-2861,2944-2964,2984-2992`
- `engine/sycl/src/core/verify.cpp:1018-1065,1338-1352,1367-1418,1576-1608,1658-1675,1805-1823,1839-1847`
- `engine/src/core/expert_source.cpp:5727-5735,5827-5835`; `engine/sycl/src/core/expert_source.cpp:2724-2728,2762-2769`
- `engine/src/kernels/cuda/shared_expert.cu:216-220,258-283`; `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-320,355-420`
