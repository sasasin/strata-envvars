# `STRATA_Q6P_GRID`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリや GPU ドライバーが読む環境変数の動作は含めない。

## 役割

Q6_K packed MMVQ カーネルの GPU workgroup 数を指定します。CUDA と SYCL の実装に読み取り箇所があり、読み取った数は出力行数以下に制限され、各 workgroup がその間隔で行を処理します。通常の Q6_K カーネルには影響しません。

## 値と判定

`std::atoi()` で整数へ変換し、正の値だけを採用します。unset、空文字、0、負数、数値変換できない文字列は既定値 `640` になります。`atoi` のため、先頭の空白と符号は許容され、数値の後の文字は変換結果に影響しません（例: `  +256junk` は 256、`junk256` は 0）。文字列全体の妥当性は検査しません。

採用した workgroup 数は `min(n_out, 設定値)` です。したがって `n_out` より大きい値を指定しても実際の grid は `n_out` になります。

## 有効になる条件

この値は、Q6_K 行列が packed registry に登録され、その行列を使う MMVQ 呼び出しで packed 経路が選ばれたときだけ参照されます。packed copy の作成は `STRATA_Q6_PACKED` によって制御されます。対応するエンジン経路で `STRATA_Q6_PACKED` が有効でない場合や、対象行列が packed 登録されていない場合は、通常の Q6_K MMVQ へ進み、この変数は使われません。

CUDA 実装では native output head と MTP draft head の Q6_K 重みが packed 対象です。gfx1151 向け architecture defaults は `STRATA_Q6_PACKED=1` を既定で設定しますが、利用者が `STRATA_Q6_PACKED` を何らかの値で設定していれば、その値を保持します。SYCL 実装にも packed Q6_K 経路と同じ grid 計算があります。

## 実行時の詳細

設定値は `q6p_grid()` の初回呼び出し時に読み、`static const int` に保存されます。そのため、そのプロセスで初回呼び出し後に環境を書き換えても grid は再評価されません。self-test の grid sweep 中は一時的な内部 override が環境設定より優先され、テスト後に解除されます。

packed kernel の起動 grid と行の stride にこの値を使います。各 workgroup は `blockIdx.x` から始め、`row_step` ずつ増やして出力行を処理します。これは実行構成の指定であり、この変数による速度向上の測定値は調査対象の資料には見つかりませんでした。

## 根拠

- CUDA で `atoi`, 既定値 640 を適用: `src/kernels/cuda/native_mmvq.cu:1818-1826`。
- CUDA で `min(n_out, q6p_grid())` を grid と row stride に使用: `src/kernels/cuda/native_mmvq.cu:1907-1915`。
- packed registry に登録された重みに限って packed 経路を選択: `src/kernels/cuda/native_mmvq.cu:1918-1941,2345-2355`。
- Q6_K packed copy の opt-in 判定と形状条件: `src/kernels/cuda/native_mmvq.cu:1980-1990`。
- Native output head と MTP draft head の packed copy 作成: `src/core/native_head.cpp:67-68`, `src/core/mtp.cpp:677-679`。
- gfx1151 defaults と既定値適用時に利用者設定を保持する処理: `src/core/arch_defaults.cpp:32-35,45-50,61-69`。
- SYCL の同じ `atoi` / 640 fallback と grid clamp: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2531-2539,2653-2657`。SYCL 側の packed 判定・dispatch: 同ファイル `2763-2769,3426-3429`。
- docs では packed Q6_K を gfx1151 の decode defaults の一つとして記載: `docs/STRIX_HALO.md:95`。
