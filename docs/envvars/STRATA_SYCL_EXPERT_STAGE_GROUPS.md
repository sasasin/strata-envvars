# `STRATA_SYCL_EXPERT_STAGE_GROUPS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

SYCL verifier の native grouped-expert staged 経路で、一度に処理する expert group の上限を指定する。`verify.cpp` は未設定時に `8`、設定時に `atoi` の結果を渡し、staged 実装は実際の batch 数をこの値と staging workspace に収まる blob 数の小さい方にする。値が 1〜16 の範囲外など staged 実装の前提を満たさない場合は、通常の `native_expert_grouped` を呼ぶ。これは expert staging のまとめ数に関する設定で、token routing や verifier の batch row 数を直接変更するものではない（`sycl/src/core/verify.cpp:1663-1671`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7924-7958`）。

この読み取りは SYCL verifier 専用ソースにあり、通常の CUDA/HIP engine では使われない。トップレベル CMake は `STRATA_ENABLE_SYCL` 時に別の `sycl/` project を構成し、同 project は `verify.cpp` を engine に含める（`CMakeLists.txt:23-33`; `sycl/CMakeLists.txt:257-268`）。

## 値と判定

呼び出し元は `std::getenv` で設定有無を調べる。未設定なら既定値 `8`、設定されていれば文字列全体の検証なしに `std::atoi` の結果を渡す。空文字・数字で始まらない文字列は `atoi` により `0` となる。数値の後ろに文字があっても数値部分を変換する（例: `3tail` → `3`）。先頭の空白や符号は `atoi` の規則で扱われる（`sycl/src/core/verify.cpp:1663-1668`）。

| 条件 | unset | 設定時に staged batch 上限として有効 | staged 実装で無効・fallback |
|---|---:|---|---|
| SYCL staged 経路に到達 | 8 | `1`〜`16`（例: `1`, `8`, `16`, `3tail`） | 空文字、`0`, `0tail`, `junk`, `-1`, `17`。`atoi` の結果が 1 未満または 16 超なら通常 grouped 実装へ fallback |

`atoi` の戻り値以外を検証しないため、`true` は有効な真偽値として認識されず `0` になり、`TRUE` も同様。値の clamp はなく、範囲外値は staged 関数内の前提条件チェックで fallback する（`sycl/src/core/verify.cpp:1667`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849,7931-7940`）。

## 有効になる条件

- SYCL engine の verifier 内で、native expert layout を処理すること。非 native layout は `moe_grouped_s2` に進む（`sycl/src/core/verify.cpp:1645-1652,1673-1676`）。
- `grouped` 呼び出しで `gy == 0` であること。現在の呼び出し箇所は VRAM group の処理で `gy=0` を渡す（`sycl/src/core/verify.cpp:1678-1692`）。
- `device_plan_` が有効で、`STRATA_VERIFY_NO_HOST` と `STRATA_SYCL_EXPERT_STAGE` が `env_on` 判定で有効であること。`device_plan_` は `STRATA_VERIFY_DEVICE_PLAN` の `atoi != 0`、`!all_resident_`、および `!always_publish_` を条件に設定される（`sycl/src/core/verify.cpp:149-152,849-855,1658-1659`）。
- B60 layout が選ばれていないこと（`!b60_layout_requested()`）。B60 の単一 staging 条件が先に処理され、通常 staged path には入らない（`sycl/src/core/verify.cpp:1654-1659`）。
- staged helper が受け付ける layout、queue、workspace 等の前提も満たすこと。対応 layout は `n_embd=2560`, `n_ff=640`, `d_type=42`, `d_row=180` で、`gu_type` ごとの row/off/byte 配置も一致する必要がある。`g_grouped_v1`、cap の範囲外、未整列 scratch/workspace、in-order でない queue、workspace 不足などでも通常 grouped 実装に fallback する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7915-7920,7931-7940`）。

`STRATA_VERIFY_DEVICE_PLAN` など他の設定に CLI 引数の優先順位を与えるコードはこの分岐にはない。対象値そのものは明示された CLI 引数や設定ファイルと比較されず、上記の経路条件を満たしたときにだけ参照される（`sycl/src/core/verify.cpp:1658-1668`）。

## 実行時の詳細

値の `getenv` は `grouped` lambda が staged 条件に入るたびに行われ、関数内 `static` cache はない。従って verifier の staged 呼び出しごとに現在のプロセス環境を読み、`atoi` 結果を helper に渡す（`sycl/src/core/verify.cpp:1648-1668`）。

有効な上限を受け取ると、helper は `batch = min(max_batch_groups, workspace_bytes / layout.bytes)` を求め、expert metadata の準備、blob の staging workspace へのコピー、pointer の再配置、native grouped expert kernel の呼び出しを最大 `batch` groups 単位で繰り返す。workspace 容量が設定値より小さければ実 batch はさらに小さくなる。設定値が無効、または他の helper 前提が不成立なら fallback は無言で `native_expert_grouped` を呼ぶ（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7931-7958`）。

## ログと測定値

この環境変数の値を出力するログ、専用の警告、終了経路は読み取り箇所と staged helper にない。fallback も関数内で通常 grouped 実装を呼ぶだけで、値に関するログは出さない（`sycl/src/core/verify.cpp:1663-1668`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7931-7940`）。

`docs/DETAILS.md`、`docs/INTEL.md`、`docs/INTEL_ARC.md` にこの変数の記載はなく、ソースコメントにも対象値の性能測定値はないため、測定値は記載しない。

## 根拠

- `sycl/src/core/verify.cpp:149-152` — `env_on` の空文字・先頭文字判定。
- `sycl/src/core/verify.cpp:849-855` — device plan の有効条件。
- `sycl/src/core/verify.cpp:1648-1676` — native/non-native 分岐、staged 経路条件、対象値の読み取りと既定値。
- `sycl/src/core/verify.cpp:1678-1692` — `gy=0` の grouped 呼び出し。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849` — batch group 上限 `16`。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7915-7958` — layout 判定、fallback、実 batch、staging 処理。
- `CMakeLists.txt:23-33`; `sycl/CMakeLists.txt:257-268` — SYCL backend の分離と verifier の engine への包含。
