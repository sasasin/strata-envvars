# `STRATA_SM60_PERF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA compute capability 6.0（sm_60、Tesla P100 など）で、Strata が起動時に自動設定する7個の性能スイッチをまとめて抑止します。対象は `STRATA_ADAPT_NOWAIT=1`、`STRATA_ADAPT_LAG=2`、`STRATA_SIDE_MIXER=2`、`STRATA_FUSE_WAIT=2`、`STRATA_B6_MMVQ_ROWS=1`、`STRATA_FUSE_DECODE=1`、`STRATA_GR_UP75=1` です。これらの既定値は、ユーザーが同名変数を設定している場合には上書きしません。

この変数自体は Pascal 専用の Q8_0 decode kernel を有効にしません。そちらは別の `STRATA_Q8_SM60` です。

## 値と判定

`src/core/nv_defaults.cpp` の `off()` は `getenv()` の結果が存在し、かつ先頭文字が `'0'` のときだけ真を返します。文字列全体の比較や数値変換はありません。

| 値 | sm_60 既定スイッチ群 |
|---|---|
| 未設定 | 適用する |
| 空文字 | 適用する（環境変数は設定済みだが先頭文字は `\0`） |
| 先頭文字が `0`（例: `0`, `0abc`） | 適用しない |
| その他（例: `1`, `true`, `false`, `abc`, ` 0`） | 適用する |

大文字小文字、空白、数値としての妥当性は検査しません。環境変数が存在するかどうかだけでなく、文字列の先頭文字を見て判定します。

## 有効になる条件

- CUDA ビルドであること（`STRATA_USE_HIP` と `STRATA_GPU_METAL` が定義される経路ではこの適用処理をコンパイルしません）。
- 起動時に少なくとも1台の CUDA device が見つかり、全可視 device の compute capability が同じであること。
- その共通 compute capability が 6.0 であること。

device 数の取得や capability の取得に失敗した場合、または複数 GPU の capability が一致しない場合、この既定値処理は呼ばれません。別 capability では `STRATA_SM60_PERF` はこのテーブルを変更しません。

## 実行時の詳細

`generate.cpp` は CUDA device capability を調べ、同一 capability のとき `apply_nv_defaults()` を呼びます。この処理は engine 側が各スイッチを読む前に実行されます。`STRATA_SM60_PERF` を判定した時点で先頭文字が `0` なら空のテーブルを返し、環境へ追加設定しません。

適用時は各スイッチを順に確認し、その環境変数が未設定の場合だけ既定値を設定します。ユーザーが値を何か設定していれば、その値が空文字や `0` を含めて保持されます。設定したスイッチが1つ以上ある場合、stderr に `strata: sm_60 (Pascal): 7 exact speed switches on by default (STRATA_SM60_PERF=0 turns them off; a switch you set is kept): ...` 形式の1行を出します。抑止時や既定値を一つも追加しなかった場合、この関数からの当該ログは出ません。

処理は起動経路で実行されます。プロセス環境にスイッチを追加するため、後続の engine コードが参照する値になります。起動後に `STRATA_SM60_PERF` を変更したときの再評価はありません。

## 文書・測定値との照合

`docs/DETAILS.md` は sm_60 の7スイッチと `STRATA_SM60_PERF=0` による一括無効化を説明しており、現行コードのテーブルと一致します。同資料にある Tesla P100 16 GB / IQ3_XXS / 既定引数 / fresh engine の8組 interleaved 測定では、decode が 36.56 から 41.76 tok/s（+14.2%、8/8組で向上）と記載されています。これはその記載条件での結果であり、他の環境の性能を示すものではありません。

## 根拠

- `src/core/nv_defaults.cpp:12-15`: unset と先頭文字 `0` の判定。
- `src/core/nv_defaults.cpp:18-49`: compute capability ごとのテーブル。sm_60 の7スイッチ。
- `src/core/nv_defaults.cpp:52-70`: ユーザー設定の保持、環境への設定、stderr ログ。
- `src/program/generate.cpp:2800-2817`: CUDA ビルド限定、可視 device の capability 一致確認と適用呼び出し。
- `include/strata/core/nv_defaults.hpp:9-13`: sm_60 の対象範囲、起動時適用の意図。
- `docs/DETAILS.md:2425-2453`: スイッチ一覧、適用条件、測定条件と数値。
- `src/kernels/cuda/native_mmvq.cu:1931-1946`: 別変数 `STRATA_Q8_SM60` の定義と用途。
