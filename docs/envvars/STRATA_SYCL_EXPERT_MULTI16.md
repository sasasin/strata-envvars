# `STRATA_SYCL_EXPERT_MULTI16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。調査対象リポジトリは `main` で、調査開始時の作業ツリーに未コミット変更はなかった。

## 役割

SYCL の grouped-expert 計算で、IQ2_XXS の gate/up 行について複数の routed entry をまとめて計算するカーネル経路を選ぶスイッチ。通常の IQ2_XXS 経路では entry を一つずつ処理するが、このスイッチが有効な場合は最大 4 entry をまとめる multi-entry dot（残り 2 entry もまとめる）を使い、同じ重み部分を複数 entry の計算に使う。対象は gate/up の IQ2_XXS（型番号 16）であり、down projection や他の形式はこの分岐の対象ではない。読み取りは `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `g_iq2xxs_reuse`、切替は `launch_gu_port` にある。`row_entries` が IQ2_XXS でこの multi-entry 処理を行う条件を `ReuseIQ2XXS` template 引数で制御している（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:2424-2459, 2464-2503, 4250-4263, 5654-5655`）。

このコードだけから、速度向上や出力の bitwise 同一性は断定できない。`docs/DETAILS.md` と `docs/EXPERTDEC.md` にこの環境変数の説明・測定値は見当たらない。

## 値と判定

翻訳単位の初期化時に `std::getenv` で読み、値が設定されていれば `std::atoi(value) != 0` を真とする。`atoi` は文字列全体の厳密な検証ではなく、先頭の空白と符号の後にある十進数字列を変換し、後続の非数字は無視する。数字で始まらない場合（空文字を含む）は 0 になる。範囲検査や `errno` によるエラー処理はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL grouped-expert 実装 | `false` | `1`, `2`, `-1`, `1abc`, ` 1`（変換結果が非 0） | `0`, `0abc`, `true`, `false`, 空文字（変換結果が 0） |

小数や `true` / `false` の文字列としては解釈しない。`atoi` の `int` 範囲を超える入力に対する結果はコードで規定・検査していない。判定箇所は `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4250-4253`。

## 有効になる条件

- Strata の SYCL 実行経路で grouped expert の gate/up が呼ばれ、gate/up 型が IQ2_XXS（`L.gu_type == 16`）であること（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7413-7417`）。
- lane 分割の選択結果が 8 であること。`STRATA_GU_LANES` は `atoi` で読み、結果が 4/8/16/32 ならその値、それ以外または未設定ならビルド時 `STRATA_EXPERT_LANES` 由来の `kExpertLanes` になる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:1127-1128, 4240-4249, 5701-5711`）。
- `STRATA_EXPERT_SPLIT` が無効であること。これは `env_on` で判定し、未設定・空文字・`0...` は無効、先頭文字が `0` 以外の非空値は有効となる。有効だと split multi kernel の経路になり、`launch_gu_port` の lane 経路を通らない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3699, 5815-5829`）。
- IQ2_XXS 専用の packed ESIMD Battlemage 経路が先に選ばれないこと。その経路は `STRATA_PRIVATE_GU_XXS_PACKED` の先頭文字が `1`、`STRATA_PRIVATE_B60_NEXT_POOL` の先頭文字が `1`、Battlemage、`b60_main_actor()` と `b60_weights_packed()` が真で、さらに IQ2_XXS、`n_embd == 2560`、`n_ff == 640`、lane 8、`!v1`、`!g_old_kernels`、`!g_split_multi`、`grid_groups == 0`、容量・device 条件などが合うと `launch_gu_xxs_s4` を選び、この環境変数の分岐を迂回する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4625, 5191-5192, 7388-7392`）。
- `STRATA_SYCL_PACKED_SIGNS` が設定されても、この変数が有効なら packed-signs 経路の条件 `!g_iq2xxs_reuse` が偽になり、その経路には入らず後続の IQ2_XXS reuse 分岐が候補になる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5640-5655`）。

このスイッチ自体に GPU 世代や shape の条件はない。ただし上記の SYCL 経路・型・lane と先行する専用経路の選択条件に従う。CLI 引数、設定ファイル、別の環境変数がこの値を上書きする実装は確認できない。`STRATA_GU_LANES` と `STRATA_EXPERT_SPLIT` は lane / split 経路選択に関与し、`STRATA_PRIVATE_GU_XXS_PACKED=1` と `STRATA_PRIVATE_B60_NEXT_POOL=1` などの条件がそろうと別の IQ2_XXS 専用経路が先に使われる。

## 実行時の詳細

値は `g_iq2xxs_reuse` のグローバル初期化ラムダで読み取られ、その結果を保持する。したがってプロセス起動後に環境を変更しても再評価されない。リクエストごとに読み直す処理や子プロセスへの転送は、この変数について確認できない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4250-4253`）。

lane 8 の `launch_gu_port<16, 8>` でスイッチが真なら `launch_gu_iq2xxs_reuse` を呼び、256 work-item の SYCL kernel として `native_gu_kernel<16, 8, true>` を起動する。行ごとの `row_entries` は group 内の entry を 4 個ずつ、続いて 2 個ずつ multi-entry dot に渡し、残りは一つずつ計算する。スイッチが偽なら `ReuseIQ2XXS` は既定値 `false` のままで、IQ2_XXS はこの multi-entry 条件に入らず逐次処理される（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:2424-2459, 2464-2503, 4255-4263, 5654-5655`）。

値の不正を理由に警告・エラーへ進む分岐はない。変数専用のログもないため、有効化を示すログ出力は確認できない。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2424-2459` — entry を 4/2 個ずつまとめる条件と、残りを一つずつ計算する処理。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2464-2503` — `ReuseIQ2XXS` を `row_entries` に渡す grouped gate/up kernel。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3693-3699, 4240-4263` — 関連 lane/split 設定と対象変数の読み取り・起動設定。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5711, 5815-5829` — launcher の選択、lane 分岐、split multi 経路。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5640-5655, 7388-7392, 7413-7417` — packed-signs との優先関係、Battlemage 専用経路、型別 dispatch。
