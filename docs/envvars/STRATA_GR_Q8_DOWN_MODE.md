# `STRATA_GR_Q8_DOWN_MODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Q8_0 hyper-connection read の down projection に使う CUDA/HIP カーネルを選ぶ。選択が効くのは、`fused_gr_read_multi_slice` が down/up の Q8 重みを持つ経路から `launch_q8` を呼び、さらに `launch_q8_t` の Tensor Core 早期 return 経路を通らず、`STRATA_TSUM` 相当の `ts` が有効で、`STRATA_GR_Q8_PFS` 相当の `pfs` が無効な場合だけ。mode 1 は `gr_down_q8_sm70_kernel<T, 4, true>`、mode 2 は CUDA で `gr_down_q8_sm70_v2_kernel<T, 4>` を選ぶ。その他の値は down projection の通常分岐を使う。up projection の選択や hyper-connection の有効化そのものはこの変数では制御しない（`engine/src/kernels/cuda/fused_gr.cu:3991-4020`, `4283-4289`）。

Strata の `STRATA_HC_Q8` 経路で down/up 行列が Q8_0 として供給されることが前提になる。ソースは `fused_gr_read_multi_slice` で両方の Q8 重みポインターが非 null のときに Q8 launch を行う。`STRATA_HC_Q8` は別途 Q8 重みの使用を決め、HIP では一部 GPU で既定有効、CUDA では原則 opt-in だが GGUF の Q8_0 重みを検出したとき既定設定する経路がある（`engine/src/core/native_dense.cpp:47-99, 683-690`; `engine/src/kernels/cuda/fused_gr.cu:4261-4289`）。

## 値と判定

初回の該当 launch 時に `std::getenv` で値を取得し、設定されていれば `std::atoi` で整数化する。整数値が厳密に 1 または 2 のときだけその mode を採用し、それ以外は 0 にする。文字列全体の妥当性検査はなく、`atoi` が読む先頭の数値部分で判定する。したがって空文字・数値で始まらない文字列は 0、`1xyz` は 1、`2.5` は 2、`01` は 1、`-1` や `3` は 0 になる。先頭空白の後の数値も `atoi` により変換される。大文字小文字の概念はない。無効値への警告やエラーはない（`engine/src/kernels/cuda/fused_gr.cu:3993-3997, 4012-4019`）。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA、通常 down 分岐に到達 | 0（通常 down kernel） | `1` / `2`。例: `1`, `01`, `1xyz`, `2`, `2.5` | 例: 空文字、`0`, `0anything`, `true`, `x1`, `-1`, `3`。mode 0 の down kernel に戻る |
| HIP、通常 down 分岐に到達 | 0（通常 down kernel） | `1`（例: `1xyz`） | `2` を含むその他は mode 0。HIP 用の分岐には mode 2 の選択肢がない |

mode 値の未設定時の 0 は、`STRATA_GR_Q8_DOWN_MODE` の読み取り箇所自体の既定値。CUDA の sm_70 用アーキテクチャ既定設定では別途 `2` がプロセス環境へ追加される（次節）。

## 有効になる条件

- down/up の Q8 重みが存在し、`fused_gr_read_multi_slice` が Q8 経路に入ること。Q8 重みがなければこの変数の読み取り・適用に至らない（`engine/src/kernels/cuda/fused_gr.cu:4261-4289`）。
- `launch_q8_t` で `STRATA_HC_Q8_TC` の CUDA Tensor Core 経路と `STRATA_HC_Q8_BF16TC` の BF16 Tensor Core 経路が先に成立しないこと。これらの既定経路は mode を参照せず return する。両経路とも launch 形状の条件 `(LR % 32 == 0) && ((Q8_KC / 32) % 2 == 0) && ((LR / 32) % 2 == 0)` も検査する（`engine/src/kernels/cuda/fused_gr.cu:3902-3923, 3943-3956, 3962-3988`）。
- 通常分岐で `ts` が true であること。`STRATA_TSUM` が設定されていれば `atoi` の結果が 0 以外で true、0 なら false。未設定時は CUDA sm_80 以上で true、その他と HIP では false（`engine/src/kernels/cuda/fused_gr.cu:3926-3941, 3991-3992, 4007`）。
- `pfs` が false であること。`STRATA_GR_Q8_PFS` が設定されていれば `atoi` の結果が 0 以外で true、0 なら false。未設定時は CUDA sm_80 以上で true、その他と HIP では false。`ts && pfs` のときは mode を使わず `gr_down_q8_fast_kernel<T, 4, true>` が選ばれる（`engine/src/kernels/cuda/fused_gr.cu:3992, 4008-4015`）。
- CUDA の sm_70 で、可視 CUDA device がすべて同じ compute capability の場合、Strata は起動時の `apply_nv_defaults` でこの変数を未設定時に `2` として設定する。`STRATA_SM70_PERF` が先頭文字 `0`、または `STRATA_DEFAULTS=026` の既定表停止条件ならこの自動追加はない。明示設定は空文字を含めて保持され、自動値に上書きされない。したがって明示した空文字は自動 mode 2 を抑止し、読み取り側では mode 0 になる（`engine/src/program/generate.cpp:4416-4444`; `engine/src/core/nv_defaults.cpp:136-163, 222-234`）。
- 自動 mode 2 は CUDA の既定表によるもの。HIP ではこの CUDA 既定表を適用せず、mode 2 の分岐もない。索引 `docs/SETTINGS.md` は NVIDIA and AMD と記載するが、対象 commit のコード上、mode 2 は HIP で選択されない（`engine/src/core/nv_defaults.cpp:136-163`; `engine/src/kernels/cuda/fused_gr.cu:4012-4019`）。

## 実行時の詳細

`launch_q8` は実際の token 数 `T` に応じて `launch_q8_t<T>` を呼ぶ。Q8 down/up を含む hyper-connection read では、CUDA/HIP の Q8 dispatcher が最初に Tensor Core 経路を調べ、その後に通常分岐で `STRATA_TSUM`、`STRATA_GR_Q8_PFS`、`STRATA_GR_Q8_DOWN_MODE` と up 側の環境変数を関数内 static 値として読む（`engine/src/kernels/cuda/fused_gr.cu:3958-3966, 3974-4008, 4054-4066, 4283-4289`）。各値は最初の該当呼び出しで一度だけ取得・保持されるため、プロセス実行中に環境を変更しても再評価されない。

通常分岐では down projection の kernel launch だけが変わる。CUDA mode 1 は `gr_down_q8_sm70_kernel<T, 4, true>`、mode 2 は `gr_down_q8_sm70_v2_kernel<T, 4>` を実行する。HIP では mode 1 のみ選択可能で、mode 2 は `gr_down_q8_fast_kernel<T, 4>` に fallback する。`ts` が false なら mode 値に関係なく `gr_down_q8_kernel<T>` を実行する。`ts && pfs` なら mode 値に関係なく `gr_down_q8_fast_kernel<T, 4, true>` を実行する。その後の up projection は別の分岐で、`STRATA_GR_Q8_UP_COLS` / `STRATA_GR_Q8_UP_MODE` に応じて実行される（`engine/src/kernels/cuda/fused_gr.cu:4009-4052`）。

CUDA sm_70 の既定追加は startup 時に一度行われる。全 visible device が同じ capability である場合に限り `apply_nv_defaults` が呼ばれ、環境に既存値がないスイッチだけを設定する。少なくとも一つ設定した場合は stderr に一覧行を出す。値の CLI 引数による上書き経路はこの変数について見つからなかった（`engine/src/program/generate.cpp:4416-4444`; `engine/src/core/nv_defaults.cpp:222-253`）。

## ログと測定値

この変数単独の有効・無効ログや不正値警告はない。sm_70 既定表が適用され、未設定のスイッチに既定値を追加した場合は、stderr に `strata: sm_70 (Volta): <N> exact speed switches on by default (STRATA_SM70_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): <names>` の形式で、追加数と名前一覧を出力する。すべての対象スイッチが未設定なら一覧に `GR_Q8_DOWN_MODE` が含まれる（`engine/src/core/nv_defaults.cpp:238-253`）。

Q8 kernel launch 後に CUDA error が検出された場合は stderr に `fused_gr_read_multi q8: <CUDA error string>` を出し、プロセスを終了コード 1 で終了する。これは mode 専用のエラーではない（`engine/src/kernels/cuda/fused_gr.cu:4284-4291`）。Strata の `docs/NVIDIA_V100.md` と `docs/DETAILS.md` は sm_70 で mode 2 を既定に含め、Q8_0 hyper-connection down projection を bit-exact と説明するが、この調査では性能測定を行っていない（`docs/NVIDIA_V100.md:47-57`; `docs/DETAILS.md:1456-1466`）。

## 根拠

- 読み取り、値判定、分岐、cache: `engine/src/kernels/cuda/fused_gr.cu:3991-4020`
- Q8 重みの存在確認と `launch_q8` への経路: `engine/src/kernels/cuda/fused_gr.cu:4261-4291`
- CUDA sm_70 既定値と既定設定のログ: `engine/src/core/nv_defaults.cpp:136-163, 222-253`
- 起動時に既定値表を呼ぶ条件: `engine/src/program/generate.cpp:4416-4444`
- `STRATA_HC_Q8` による Q8 重み有効条件: `engine/src/core/native_dense.cpp:47-99, 683-690`
