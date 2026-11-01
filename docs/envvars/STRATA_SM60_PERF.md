# `STRATA_SM60_PERF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

NVIDIA compute capability 6.0（sm_60、Tesla P100 / Pascal GP100）の CUDA 実行で、Strata が engine 初期化時に設定する 7 個の既定スイッチをまとめて無効化します。変数自体は既定セットを選ぶための off switch であり、個別スイッチの値を一括で `0` にするものではありません。

## 値と判定

`src/core/nv_defaults.cpp` の `off()` は `std::getenv()` の結果が null でなく、先頭文字が `'0'` のときだけ true を返します。文字列全体の parse や数値変換はしません。

| `STRATA_SM60_PERF` | P100 用既定セット |
| --- | --- |
| 未設定 | 有効（既定） |
| 空文字 | 有効。設定済みだが先頭文字は `'0'` ではない |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他の先頭文字（例: `1`, `true`, `false`, 空白） | 有効 |

大文字小文字、後続文字、数値としての妥当性は判定されません。したがって `false` も有効です。無効値に対する警告や fallback はありません。

## 有効になる条件

- `STRATA_USE_HIP` と `STRATA_GPU_METAL` が定義されていない CUDA 経路であること。
- `cudaGetDeviceCount()` が成功し、可視デバイスが 1 台以上あること。
- すべての可視 CUDA デバイスの compute capability が同一で、かつ `6.0` であること。

デバイス列挙または属性取得が失敗する場合、あるいは可視デバイスの世代が混在する場合は `apply_nv_defaults()` が呼ばれず、この既定セットは適用されません。HIP / Metal 経路ではこの CUDA 用適用ブロックに入りません。

## 実行時の詳細

engine 初期化中、デバイス条件の確認後に `apply_nv_defaults()` が呼ばれ、engine のスイッチ読み取りより前に適用されます。sm_60 で off switch が無効なら、次の値を Strata のプロセス環境へ既定値として設定します。

| 環境変数 | 既定値 |
| --- | --- |
| `STRATA_ADAPT_NOWAIT` | `1` |
| `STRATA_ADAPT_LAG` | `2` |
| `STRATA_SIDE_MIXER` | `2` |
| `STRATA_FUSE_WAIT` | `2` |
| `STRATA_B6_MMVQ_ROWS` | `1` |
| `STRATA_FUSE_DECODE` | `1` |
| `STRATA_GR_UP75` | `1` |

この各変数が既に設定されていれば、その値は `0` や空文字を含めて保持され、その変数への既定値設定はスキップされます。つまり `STRATA_SM60_PERF` が有効でも個別設定が優先され、CLI 引数による一括上書き処理はこのコードにはありません。`STRATA_SM60_PERF=0` のときは既定テーブルが空になり、個別スイッチを新たに設定しません（既存の個別設定を消去もしません）。

判定は呼び出し時に `getenv()` で行われ、static cache はありません。通常の engine 初期化経路ではこの関数が起動時に一度呼ばれます。適用関数は off switch 自体を書き換えず、子プロセスへの転送もこの実装にはありません。

既定値を 1 個以上設定した場合だけ stderr に `strata: sm_60 (Pascal): 7 exact speed switches on by default (STRATA_SM60_PERF=0 turns them off; a switch you set is kept): ...` 形式の行を出し、設定したスイッチ名を列挙します。全スイッチが既に設定済み、off switch が有効、または適用条件を満たさない場合、この関数からはログが出ません。異常値専用の終了・失敗経路はありません。

## 根拠

- `src/core/nv_defaults.cpp:13-16` — 環境値の読み取りと先頭文字 `'0'` の判定。
- `src/core/nv_defaults.cpp:41-52` — sm_60 の off switch と 7 個の既定値。
- `src/core/nv_defaults.cpp:82-106` — 既存環境値の優先、環境への設定、stderr ログ。
- `src/program/generate.cpp:3445-3461` — CUDA 限定の適用箇所、全可視 GPU の世代一致確認、および既定値設定の呼び出し。
- `include/strata/core/nv_defaults.hpp:15-16,25-33` — 既定値設定の目的と適用順序。
- `docs/DETAILS.md:1211-1220`, `docs/OLDER_GPUS.md:141-147` — P100 の既定 7 スイッチと off switch の既存資料。実際の条件・値の解釈は上記実装に基づく。
