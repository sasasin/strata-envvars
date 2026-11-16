# `STRATA_SYCL_GR_NORM_BOUNDS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 版 fused GR 読み取りの正規化段階で、各 work-group が担当ストリームの範囲だけを走査する `gr_norm_bounds_port_kernel` を選ぶための opt-in です。未設定または値が条件に合わない場合は通常の正規化 kernel を選びます。設定値が出力結果に与える数値上の差は、ソースだけからは確認できません。読み取りは `fused_gr.dp.cpp` の翻訳単位初期化時に一度行われます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:569-572`）。

## 値と判定

`std::getenv` で取得し、値が存在して先頭文字が ASCII の `1` の場合だけ有効です。文字列全体の比較や数値変換はしません。空文字は設定済みでも無効です。先頭以降は無視されるため `1`, `10`, `1anything` は有効、`0`, `true`, ` 1`, `01` は無効です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:569-572`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| SYCL `fused_gr.dp.cpp` を含む実行ファイル | 無効（通常 kernel） | `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1`, `01` |

この変数自体に CLI 引数や別設定による値の上書きはありません。プロセス起動後に環境を書き換えても、翻訳単位の `const` 初期化値は変わりません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:569-572`）。

## 有効になる条件

- SYCL ビルドがこの実装ファイルをコンパイルしていること。SYCL CMake の kernel source 一覧に含まれます（`sycl/CMakeLists.txt:39-43`）。
- 実行経路が fused GR kernel に到達すること。CLI 側では `gr_native_mmvf` が有効で、`--no-fused-gr`、GPU stage、layer/half dump、stage timing のいずれも fused GR を止めていない必要があります（`sycl/src/program/generate.cpp:3140-3150`）。layer 経路でも `g_fused_gr`、stage/half 条件、および geometry 対応が必要です（`sycl/src/core/layer.cpp:1558-1559,1620-1630`）。
- 正規化の分割経路が有効であること。`STRATA_GR_NORM_SPLIT` が未設定なら有効、設定時は `atoi(value) != 0` で判定されます。`0` や数値に変換できない文字列ではこの変数の bounds kernel は選択されません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:574-577,3324-3333`）。
- `STRATA_SYCL_GR_CACHED_NORM` の `atoi` 結果が `3` で安全性条件を満たす場合は、bounds kernel の代わりに cached norm kernel が選ばれます（例: `3`, `3tail`）。cached 経路にはさらに fused GR cache が無効、分割正規化・sliced down が有効、入力/出力バッファが alias 条件を満たすことが必要です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79,85-105,3298-3300,3320-3327`）。

## 実行時の詳細

`fused_gr_read_multi` は引数を検証した後、cached norm 条件を先に評価します。cached 経路に入らず、この変数が真で `gr_norm_split()` も真なら、`n_tok * HC` 個の work-group を起動して `gr_norm_bounds_port_kernel` を実行します。そうでなければ分割 norm kernel、または非分割 norm kernelを選びます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159,3298-3300,3320-3340`）。

bounds kernel は group ごとに token と stream `c` を割り当て、担当範囲 `c*N` から `(c+1)*N` の要素を処理します。必要なら前段の値を残差へ適用し、二乗和から逆 RMS を求め、正規化した重み積を `xn` に書き込みます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:473-518`）。この kernel の後も fused GR の down/up 段階が続きます。`fused_gr_read` は条件により単一 token を `fused_gr_read_multi` に委譲します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3520-3533`）。

対象変数の値は翻訳単位初期化時の一度だけ読みます。`STRATA_GR_NORM_SPLIT` はその関数内の static 初回評価で値を保持します。いずれも実行中の環境変更は既に決まった値を更新しません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:569-577`）。

## ログと測定値

この変数の有効・無効や kernel 選択を知らせる専用ログはありません。fused read の引数不正時には環境変数の値に関係なく `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を stderr に出し、`exit(1)` します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3142-3155`）。この変数による性能や正確性の測定値は、調査対象コードおよび関連資料では確認できません。

## 根拠

- `sycl/CMakeLists.txt:39-43` — SYCL kernel source としての登録。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:473-518,569-577,3139-3159,3298-3340,3520-3533` — bounds kernel、値の読み取り、選択と呼び出し経路。
- `sycl/src/program/generate.cpp:3140-3150`、`sycl/src/core/layer.cpp:1558-1559,1620-1630` — fused GR の有効条件と呼び出し。
