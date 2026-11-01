# `STRATA_SM86_PERF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の compute capability が 8.6（sm_86）の GPU 用に、Strata が選んだ性能スイッチを既定で有効にする処理の OFF スイッチです。`STRATA_SM86_PERF` が `0` で始まると、この既定テーブルを空にします。通常の CUDA 起動時に全可視 GPU が同じ compute capability 8.6 の場合にだけ使われます。

既定テーブルは、未設定のとき次の環境変数をプロセス内に設定します。各変数がすでに設定済みなら値を問わず保持します。

| 環境変数 | 自動設定値 |
| --- | --- |
| `STRATA_ADAPT_NOWAIT` | `1` |
| `STRATA_ADAPT_LAG` | `2` |
| `STRATA_CPU_IQ_ALL_EXACT1` | `1` |
| `STRATA_SIDE_MIXER` | `2` |
| `STRATA_ATTN_DAILY` | `1` |
| `STRATA_GR_UP75` | `1` |
| `STRATA_GU_SWIGLU` | `1` |
| `STRATA_QSA_ROWS` | `1` |
| `STRATA_B6_MMVQ_ROWS` | `1` |

## 値と判定

コードは `getenv()` の結果が null でないことと、先頭文字が `'0'` かどうかだけを調べます。文字列全体の parse はしません。

| 値 | 既定テーブルの判定 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 有効（値は設定済みだが、先頭文字は `'0'` ではない） |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、`2`、空白で始まる ` 0` など | 有効 |

大文字小文字、数値としての妥当性、後続文字は判定に影響しません。無効値に対する警告やエラーはありません。

## 有効になる条件

- CUDA ビルドであること（`STRATA_USE_HIP` と `STRATA_GPU_METAL` のどちらも定義されていない経路）。この処理は HIP/Metal ビルドでは呼ばれません。
- `cudaGetDeviceCount()` が成功し、可視 GPU が1台以上あること。
- 可視 GPU 全台の compute capability 取得に成功し、major/minor がすべて一致すること。
- その capability が 8.6 で、`STRATA_SM86_PERF` が `0` で始まらないこと。

いずれかの GPU の capability 取得に失敗するか、世代が混在すると `apply_nv_defaults()` は呼ばれず、sm_86 用テーブルは適用されません。単一 GPU の場合も同じ一致条件を通ります。

この既定処理は CLI 引数より後、engine が各スイッチを読む前に実行されます。ここで `STRATA_SM86_PERF` 自体を設定する CLI 引数はありません。個々のテーブル対象変数を明示設定していれば、その値が自動設定より優先します。`STRATA_DEFAULTS=026` は sm_86 テーブルを無効にしません。

## 実行時の詳細

`src/program/generate.cpp` の CUDA 起動時処理は全可視 GPU の compute capability を調べ、全台が同じなら `apply_nv_defaults()` と `apply_spec_adapt_default()` を呼びます。sm_86 の既定テーブルは `src/core/nv_defaults.cpp` で生成され、上表の値がプロセス環境に追加されます。設定は `setenv(..., 0)`（Windows は `_putenv_s`）で行われるため、既存の各スイッチを上書きしません。後続の engine コードはこれらの環境スイッチを読みます。

読み取りは `nv_default_env()` の呼び出しごとに行われ、`STRATA_SM86_PERF` 自体は static cache されません。一方、この処理が環境変数をセットした後、通常は engine が起動した状態で `STRATA_SM86_PERF` を変更しても、すでに追加された個々のスイッチは取り消されません。

もう一つの `apply_spec_adapt_default()` も `STRATA_SM86_PERF` を同じ `off()` helper で確認します。sm_86 で、`STRATA_SPEC_ADAPT_SM86` が先頭文字 `'1'` である場合に、未設定の `STRATA_SPEC_ADAPT_EVERY=2` と `STRATA_SPEC_ADAPT_WARM=200` を設定します。`STRATA_SM86_PERF` が `0` で始まるとこの追加設定も行いません。これらの値がすでに設定済みなら保持します。

テーブルから一つ以上の変数を設定しようとした場合、stderr に `strata: sm_86 (Ampere): 9 exact speed switches on by default (STRATA_SM86_PERF=0 turns them off; a switch you set is kept): ...` の形式で、対象スイッチ名を列挙します（設定数に応じて `9` は変わります）。`setenv()` / `_putenv_s()` の戻り値は確認していないため、このログは環境設定の成功確認ではありません。全対象スイッチが既に設定済みの場合、または OFF 判定でテーブルが空の場合、この処理からの有効化ログは出ません。GPU 数・capability 検出失敗自体について、この箇所は警告を出しません。

## 根拠

- `src/core/nv_defaults.cpp:13-16` — 名前を受け取る `off()` helper。値の先頭が `'0'` かだけを判定。
- `src/core/nv_defaults.cpp:23-40` — capability 8.6 の OFF 判定と9個の既定スイッチ。
- `src/core/nv_defaults.cpp:82-107` — 未設定変数だけを環境に設定する処理と stderr ログ。
- `src/core/nv_defaults.cpp:109-127` — sm_86 の追加適応既定と `STRATA_SM86_PERF` の OFF 判定。
- `src/program/generate.cpp:3445-3461` — CUDA ビルド条件、可視 GPU 全台の capability 一致判定、および engine の既定スイッチ読込前の呼び出し。
- `include/strata/core/nv_defaults.hpp:15-16,25-33` — 各カードの OFF スイッチ、既存設定の保持、起動時適用の説明。
- `docs/DETAILS.md:1211-1227` — sm_86 テーブルと OFF スイッチの説明。測定値はソースコメントおよびこの資料の記載であり、この調査で再計測していません。
