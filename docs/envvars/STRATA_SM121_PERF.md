# `STRATA_SM121_PERF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae8e9d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソースであり、外部ライブラリや GPU driver の環境変数動作は含めない。

## 役割

NVIDIA compute capability 12.1（sm_121、GB10 / DGX Spark）で、Strata が起動時に設定する4個の性能関連環境変数の既定値セットを有効にするか抑止するスイッチです。sm_121 は Strata の CUDA ビルドで、可視 CUDA device がすべて同じ compute capability 12.1 の場合に限って対象になります。値が有効でも `STRATA_DEFAULTS=026` が有効ならセットは適用されません。

この変数が有効な場合、プロセス環境にまだ設定されていない次の値を設定します: `STRATA_PF_FUSED=1`、`STRATA_PREFILL_NVFP4=w4a4`、`STRATA_HC_UPMIX=1`、`STRATA_SPEC_COST=1`。対象の個別スイッチが環境にすでにあれば、その値が何であっても保持されます。

## 値と判定

| `STRATA_SM121_PERF` | 表の判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効。設定値は存在するが、先頭文字は `\0` であり `'0'` ではない |
| 先頭文字が `0` の値（例: `0`, `0anything`） | 無効 |
| その他の設定値（例: `1`, `false`, `0` 以外で始まる任意文字列） | 有効 |

実装は文字列全体を parse せず、先頭文字が `'0'` かだけを比較します。したがって `false` や `no` も有効、`0anything` も無効です。空白除去、大文字小文字変換、数値変換、範囲検査はありません。根拠: `src/core/nv_defaults.cpp:13-16,53-57`。

## 有効になる条件

- NVIDIA CUDA ビルドであること。呼び出しは `!STRATA_USE_HIP && !STRATA_GPU_METAL` のコンパイル条件内にあります。
- CUDA の可視 device が1台以上あり、全 device から取得した compute capability major/minor が同じであること。異なる capability、device 数が0、または取得失敗の場合、この既定値適用ブロックは実行されません。
- capability が 12.1 であること。sm_120 など他の GPU にはこの表はありません。
- `STRATA_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれでもないこと。これらは完全一致で判定され、該当すれば sm_121 の表は空になります。`STRATA_SM121_PERF` を `1` にしてもこのマスター設定を打ち消しません。

適用対象となる個別スイッチについては、プロセス環境にすでに値があればその値を維持します。たとえば個別スイッチの値が `0` でも既定の `1` や `w4a4` で上書きしません。ここでの優先順位は、表の適用可否では `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` が表全体を止め、表が適用可能な場合の各値では利用者が設定した個別環境変数が既定値より優先、です。該当する CLI 引数による上書き処理はこの表の実装にはありません。

根拠: `src/program/generate.cpp:3445-3462`, `src/core/nv_defaults.cpp:19-24,53-57,82-92`, `include/strata/core/defaults_026.hpp:21-29`。

## 実行時の詳細

Strata の `generate` 起動経路は CUDA device 数と各 device の compute capability を調べ、全 device が同一なら `apply_nv_defaults()` を呼びます。この呼び出しは engine のスイッチ読み取りより前に行われます。`nv_default_env()` は sm_121 の条件と両方の抑止条件を確認して既定値一覧を作り、`apply_nv_defaults()` は未設定の項目だけをプロセス環境へ追加します（Windows は `_putenv_s`、その他は `setenv(..., 0)`）。この関数には `STRATA_SM121_PERF` の独自キャッシュはありませんが、起動経路で表を適用するのはこの初期化時です。`STRATA_DEFAULTS` の判定は `qwen_defaults_026()` 内の `static const bool` に保存され、最初の評価後はプロセス中に環境値を変更しても再評価されません。

1つ以上の値を新たに設定したときだけ stderr に1行出ます。sm_121 の場合の形式は `strata: sm_121 (GB10): N speed switches on by default (STRATA_SM121_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ...` です。すべての個別値がすでに設定済みの場合、抑止条件に該当する場合、または対象外の GPU 条件の場合は、この呼び出しから既定値設定ログは出ません。終了やエラーをこの変数単独で発生させる処理は確認できません。

Strata の `docs/DGX_SPARK_LINUX.md:114-123` は同じ4設定を GB10 上の既定として記載し、`STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` で全体を止められると説明しています。同文書の測定表は release-candidate 0.2.7.1、DGX Spark 1台、2026-10-27 の測定として記載されています（`docs/DGX_SPARK_LINUX.md:90-103`）。この文書ではそこに記載された測定値を一般的な性能保証として扱いません。

## 根拠

- 読み取りと表選択、sm_121 の4既定値: `src/core/nv_defaults.cpp:13-16,19-24,53-79`
- 既定値の注入、個別設定の保持、stderr ログ: `src/core/nv_defaults.cpp:82-106`
- CUDA ビルド条件、可視 device の capability 一致判定、engine の読み取り前に適用: `src/program/generate.cpp:3445-3462`
- `STRATA_DEFAULTS` の受理文字列と初回評価キャッシュ: `include/strata/core/defaults_026.hpp:21-29`
- GB10 のスイッチ説明と測定条件: `docs/DGX_SPARK_LINUX.md:90-103,114-123`
