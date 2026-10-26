# `MMVQ_IL_TMAX`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この変数は、CUDA の合成パリティ確認・ベンチマーク実行ファイル `mmvq_il_parity` が試す token 数 `T` の上限を指定します。通常の Strata 実行ファイルが読む環境変数ではありません。`src/kernels/mmvq_il_parity.cpp` の `run_case()` だけが参照し、各ケースについて `T=1` から上限まで順にパリティを確認します。`--bench` を付けた場合は同じ範囲で計時も行います。

## 値と判定

| 設定 | 上限 `t_max` | 実行される `T` |
|---|---:|---|
| 未設定 | 8 | 1〜8 |
| 正の整数文字列 | `std::atoi()` の結果 | 1〜その値（両端を含む） |
| 空文字、数値に変換できない文字列、0 | 0 | なし |
| 負の数 | 負の値 | なし |

`std::atoi()` を使うため、文字列全体の厳密な検証はしません。先頭の空白と符号は整数変換の規則に従い、数値の後ろに文字があっても数値部分が使われます（例: `5xyz` は 5）。数値として読めない先頭なら 0 になります。上限を clamp する処理はありません。表の挙動は `src/kernels/mmvq_il_parity.cpp:108-109` によります。

## 有効になる条件

- `mmvq_il_parity` は CUDA 有効時に作られ、CMake の `STRATA_BUILD_TESTS` ブロック内で実行ファイルと CTest 項目として登録されます。通常の Strata engine の処理には影響しません（`CMakeLists.txt:268,1097-1102`）。
- `MMVQ_IL_ONLY` が設定されていると、`main()` はケース名にその文字列を含むケースだけを `run_case()` に渡します。空文字なら全ケース名に一致します。これは `MMVQ_IL_TMAX` の値判定とは独立したケース絞り込みです（`src/kernels/mmvq_il_parity.cpp:305-307`）。
- `--bench` は各ケースについてパリティ確認に加えて時間を測ります。未指定なら時間測定はしません。`MMVQ_IL_TMAX` 自体に CLI 引数による上書きはありません（同 `:298-300,150-187`）。

## 実行時の詳細

環境変数は `run_case()` の呼び出しごとに読みます。結果を `static` に保存しないため、ケースごとに値を取得する実装です。各ケースでは上限まで入力ベクトルを生成し、通常の `native_mmvq` と interleaved 版 `native_mmvq_il` の結果を比較します。`--bench` 時には同じ `T` ごとに両経路の時間も測定します。計算やパリティ比較自体を省略するのではなく、反復する `T` の範囲を変える診断用設定です。

`MMVQ_IL_TMAX` を設定して上限を既定値の 8 から変えても、成功時に出る最終行は固定文字列 `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)` のままです。そのため、この行の `T 1-8` は設定値を反映しません（同 `:108-109,309-310`）。

## 根拠

- `src/kernels/mmvq_il_parity.cpp:83-109,123-150,168-187` — 上限の取得、inclusive な `T` ループ、比較とベンチマーク。
- `src/kernels/mmvq_il_parity.cpp:298-310` — CLI モード、ケース選択、終了時の表示。
- `CMakeLists.txt:268,1097-1102` — テストビルド内での CUDA 実行ファイル登録。
- `docs/MMVQ_IL_TABLE.md:22-27` — `mmvq_il_parity` をビルド・実行して表を測定する手順。
