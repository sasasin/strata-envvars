# `STRATA_IQ4NL_DOWN_SLM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の native expert grouped down projection で、IQ4_NL（down type `20`）用に activation (`hq`) を work-group local memory にステージする `native_down_iq4nl_slm_kernel` を選ぶ実験的な切替です。設定が有効でも、旧 IQ カーネルが選ばれておらず、expert layout が `n_embd == 2560` かつ `n_ff == 640` のときだけ専用カーネルへ分岐します。それ以外は既存の lane / multi down カーネルに進みます（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3051-3109, 6095-6121`）。

専用カーネルは各 group の down 重みと activation を使って出力 `out` を計算し、activation を local memory にコピーしてから IQ4_NL の複数行 dot を行います。生成 token や出力選択を変える設定だとはコードから確認できません。数値の同一性・性能差はこのソースだけでは断定しません（同 `:3051-3109`）。

## 値と判定

`strata::bm_default_on` は `std::getenv` で値を得て、未設定または空文字なら `bm_default` と Battlemage 判定に従います。ここでは `bm_default=false` が渡されるため、どの GPU 世代でも既定は off です。空でない値は先頭 1 文字だけを見て、`'0'` なら off、それ以外なら on とします。数値や真偽語としての全体 parse、空白除去、大文字小文字の比較、後続文字の検査はありません（`engine/sycl/include/strata/sycl_queue.hpp:193-200`; 呼び出しは `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6108-6110`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の `launch_down<20>` | off（Battlemage でも off） | 空でない値で先頭文字が `0` 以外。例: `1`, `true`, `false`, ` 0`, `-0`, `0anything` のうち前の 5 例は on | 空文字は unset と同じ。先頭が `0` の `0`, `0anything`, `00` は off |

表の例はすべて同じ先頭文字判定によります。`false` は `f` で始まるため on、先頭に空白がある ` 0` も on です。明示値は GPU 世代に関係なく helper の判定を上書きします（`engine/sycl/include/strata/sycl_queue.hpp:196-200`）。

## 有効になる条件

- この変数の直接読み取りは `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp` に 1 箇所あります。`STRATA_HIP_GFX906` が定義された build では、後述の AMD 専用分岐が先に実行される場合があり、その経路はこの変数を読みません。
- down projection の呼び出しに到達し、`L.d_type == 20` である必要があります。native grouped 関数は `g_exp_phase == 1` のとき down projection 前に return します（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7946-7949, 7976-7980`）。
- `STRATA_OLD_IQ_MMVQ` で初期化される `g_old_kernels` が false である必要があります。true の場合は専用分岐を飛ばし、後続の通常経路へ進みます。実行時の setter `iq_set_old_kernels` もこの状態を変更します（同 `:3927-3932, 6108-6120, 6126-6128`）。
- `L.n_embd == 2560` と `L.n_ff == 640` の両方が必要です。寸法が異なる場合、変数が on でも専用カーネルは起動しません（同 `:6108-6113`）。
- `STRATA_EXPERT_SPLIT` はこの専用分岐条件に含まれません。専用条件を満たさない場合の通常経路では `g_split_multi` の値が lane / multi カーネル選択に使われます（同 `:3933-3937, 6115-6121`）。
- `STRATA_HIP_GFX906` build では、`em` が `1`, `2`, `4` のいずれか（`STRATA_EXP_MODE >= 5` も `2` に写像）で、`d_type` が `20`, `23`, `42` のとき、AMD 専用 kernel を起動して generic `launch_down` より前に return します。この場合、IQ4_NL down でも本変数は参照されません。`em` は `STRATA_EXP_MODE`（既定 `0`）または `native_expert_set_mode` で決まります（同 `:7748-7758, 7952-7974`）。
- `cap_groups <= 0` または `cap_entries <= 0` では native grouped 処理自体が早期 return します（同 `:7767-7775`）。

## 実行時の詳細

変数名の直接参照は `launch_down<TD>` の `TD == 20` 専用ブロックに 1 箇所あります。`bm_default_on(...)` の結果はそのブロック内の関数ローカル `static const bool` に保存されるため、最初に `launch_down<20>` が実行されてこの宣言へ到達したときに読み取り、そのプロセス内の以降の呼び出しではキャッシュ値を使います。起動後に環境値だけを変更しても再評価されません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6108-6110`）。

down type `20` は `L.d_type` の switch から `launch_down<20>` に dispatch されます。専用条件が成立すれば `launch_down_iq4nl_slm` が local memory を使う専用 kernel を enqueue して return し、不成立なら `g_old_kernels` / `g_split_multi` に応じた既存経路へ進みます。ただし `STRATA_HIP_GFX906` の条件付き経路はこの switch より前にあります（同 `:6083-6093, 6095-6121, 7952-7980`）。この変数を読む CLI 引数や別の設定ファイルからの転送は確認できません。

## ログと測定値

この変数の値や専用経路選択を知らせるログはありません。down dispatch 後には `check("native_expert_grouped/down")` が呼ばれますが、このファイルの `check` は `dpct::err0 e = 0` を置くだけで、エラー処理や出力を実装していません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:72-84, 7982`）。性能値は記載しません。`docs/INTEL.md:591-603, 611-612` もこの制御を既定 off として列挙していますが、個別の測定値は載せていません。

## 根拠

- 値の解釈と Battlemage 既定判定: `engine/sycl/include/strata/sycl_queue.hpp:193-200`
- 変数の読み取り、条件、fallback: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6095-6121`
- 専用 kernel と local memory staging: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3051-3109, 6083-6093`
- type dispatch、早期 return、旧 kernel state: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3937, 6126-6128, 7767-7775, 7946-7949, 7976-7982`
