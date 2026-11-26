# `STRATA_MMVQ_WIDE_MAXC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 実装の Q6_K MMVQ で、wide kernel へ振り分ける `ncols` の上限を指定する。`native_q6_k_mmvq` が wide 経路を選ぶ条件の一つであり、出力行数や入力幅の上限ではない。値を設定しても、wide 経路全体が無効な場合や、先行する packed / planar 経路が処理した場合には、この上限で dispatch は変わらない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3955`）。

ソース全体の完全一致検索では、実行時読み取りはこの関数内の 1 箇所だけだった。`terminal/data/settings-register.json:25576-25590` にも SYCL backend と読み取り位置の登録情報があるが、これは実行時の値読み取りではない。CUDA 実装 `engine/src/kernels/cuda/native_mmvq.cu` にはこの名前の読み取りがない。

## 値と判定

`std::getenv` が `nullptr` かどうかで未設定を判定し、設定されていればもう一度 `std::getenv` を呼んで `std::atoi` の結果を上限にする。空文字も「設定あり」なので `atoi("") == 0` となる。文字列全体の妥当性確認、範囲検査、clamp はない。`atoi` は先頭の空白と符号を含む整数部分を読み、数字以降の文字は無視するため、`" 5tail"` は 5、`"5.5"` は 5、`"true"` や `"x5"` は 0 になる。文字列の大文字小文字は数値変換に影響しない。負数も整数値として保持されるが、`ncols >= 1` との比較を満たせないため wide dispatch の上限としては全列数を除外する（同 `3944-3945`）。

| 条件 | unset | 設定時に wide 上限となる例 | 上限値としての効果がない例 |
|---|---:|---|---|
| SYCL の Q6_K 経路 | `STRATA_MMVQ_A2` が unset または `atoi != 0` なら 8。`STRATA_MMVQ_A2=0` なら 4 | `4` なら `ncols <= 4`、`8` なら `ncols <= 8` | 空文字、`0`、`-1`、`true`、`x5` は 0 以下となり、通常の正の `ncols` では wide 条件を満たさない。`5tail` は 5 として扱う |

この既定値は `q6k_a2()` の結果に依存する。`STRATA_MMVQ_A2` 自体は未設定なら有効（true）、設定時は `atoi(...) != 0` が有効で、`0` や数値に変換できない文字列は無効になる（同 `1545-1548`）。`STRATA_MMVQ_WIDE_MAXC` を明示すると、その整数値が A2 による既定値を置き換える。`atoi` で表現できない範囲の入力について、ソースは規則を追加していない。

## 有効になる条件

- Strata の SYCL backend で、この `native_mmvq.dp.cpp` の Q6_K 実装が使われること。CUDA backend の `.cu` 実装にはこの変数の読み取りがない。
- `native_q6_k_mmvq` の先頭にある `q6_packed_mmvq` と `q6_planar_mmvq` のいずれも処理を完了せず、通常の Q6_K dispatch まで進むこと。packed registry に該当する重みがあり、列数などの条件を満たすと packed 側が先に返る（同 `2876-2895`）。planar registry に登録された重みは列数ごとに処理され、先に返る（同 `3005-3024`, `3935-3938`）。
- wide kernel の全体ゲート `STRATA_MMVQ_WIDE` が有効であること。これは unset なら有効、設定時は `atoi(...) != 0` で判定される（同 `2185`）。
- `1 <= ncols <= STRATA_MMVQ_WIDE_MAXC`、`n_in` が 256 の倍数、かつ `n_out >= wide_min` であること（同 `3943-3945`）。`wide_min` は `STRATA_MMVQ_WIDE_MIN` が設定されていれば `atoi` 値、未設定なら A2 有効時 0、無効時 4096（同 `3943`）。
- 明示値は 8 に clamp されない。通常の MMVQ 形状検査は `1 <= ncols <= 8` だが（同 `2297-2302`）、wide 条件はその検査より先に評価される。したがって上限を 8 より大きく設定して `ncols > 8` で呼ぶと、wide 条件を通り、switch の default が 8 列 kernel を起動して戻るため、後続の形状検査には到達しない（同 `3945-3955`, `3968-3977`）。

## 実行時の詳細

`wide_maxc` は `native_q6_k_mmvq` 内の関数ローカル `static const` で、最初に通常 Q6_K dispatch まで到達した呼び出しで初期化され、その値を以後の呼び出しでも使う。後から環境を変更しても反映されない。初期化時に環境変数が未設定なら `q6k_a2()` の結果を使い、同 helper も `STRATA_MMVQ_A2` を関数ローカル static に保存する（同 `1545-1548`, `3937-3945`）。

上限以下で wide 条件を満たすと、`ncols` に応じて `launch_q6k_wide<1>` から `<7>`、または `<8>` を選び、その場で戻る。条件を満たさない場合は独立した rowwarp 経路（`ncols <= 4` など）を試し、その後 shape / pointer / stream を検証して通常の MMVQ kernel に進む。つまり上限を下げても Q6_K 計算自体を止めるのではなく、wide kernel の選択条件だけを狭める（同 `3945-3977`）。

## ログと測定値

この環境変数の読み取り値、既定値、wide dispatch の選択を知らせる専用ログはない。通常経路で形状が不正なら `native MMVQ requires 1 <= ncols <= 8` などの `std::invalid_argument` が投げられるが、wide 条件を先に通る `ncols > 8` のケースではその検査に到達しない（同 `2297-2302`, `3945-3977`）。本変数について条件を特定できる性能測定値は `docs/DETAILS.md` に見当たらず、ここでは記載しない。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548` — `STRATA_MMVQ_A2` の読み取りと cache。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185` — `STRATA_MMVQ_WIDE` の全体 gate。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2895` — packed Q6_K の先行経路。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3005-3024` — planar Q6_K の先行経路。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3977` — 対象変数の読み取り、wide 条件、kernel 選択、後続経路。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2297-2302` — 通常形状の列数範囲とエラー。
- `terminal/data/settings-register.json:25576-25590` — SYCL 読み取り位置の登録情報（実行時読み取りではない）。
