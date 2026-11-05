# `STRATA_NV_KQ_DEFAULT`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

CUDA ビルドで、K-quant expert の prompt 計算を MMQ にする `STRATA_MMQ_KQ=1` を Strata が既定設定するか制御します。対象は、見えている NVIDIA GPU の最小 compute capability major が 8 以上の実行です。既定で有効なため、この変数は通常その既定を止めるためのスイッチです。`STRATA_NV_KQ_DEFAULT=1` は既定動作を変えません。

## 値と判定

`nv_kq_default_env()` は値全体を parse せず、`STRATA_NV_KQ_DEFAULT` の先頭文字だけを見ます。`STRATA_DEFAULTS=026` が有効な場合、または最小 major が 8 未満の場合は、この変数の値にかかわらず設定候補を返しません。

| 条件 | `STRATA_MMQ_KQ` の既定候補 |
| --- | --- |
| `STRATA_DEFAULTS=026` | なし |
| 最小 compute capability major が 8 未満 | なし |
| 上記以外で `STRATA_NV_KQ_DEFAULT` の先頭文字が `0` | なし（`0`, `0abc` など） |
| 上記以外で unset、空文字、または先頭文字が `0` 以外 | `1`（unset が通常の既定動作。`1`, `false`, `2`, 空文字も同じ扱い） |

大小文字、空白、文字列の数値としての妥当性は調べません。たとえば `false` は無効化値ではなく、先頭が `f` のため既定を有効にします。

## 有効になる条件

- 呼び出し箇所は `src/program/generate.cpp` の `#if !defined(STRATA_USE_HIP) && !defined(STRATA_GPU_METAL)` 内です。したがって、この変数による既定設定は CUDA 経路で行われ、HIP / Metal の既定設定には使われません。
- `cudaGetDeviceCount()` が成功し、1台以上の GPU が見える場合に適用判定へ進みます。複数 GPU では最小の compute capability が使われ、major が 8 未満なら適用されません。`STRATA_EMULATE_CC` が有効なら、major の比較にはエミュレート値が反映されます。
- `STRATA_DEFAULTS=026`（同義値 `0.2.6` / `v0.2.6` を含む）が有効なら無効です。この値は `qwen_defaults_026()` が初回呼び出し時に static cache します。
- `STRATA_MMQ_KQ` が既に設定されている場合、空文字や `0` を含め、ユーザーの値をそのまま優先して Strata は上書きしません。カーネル側の通常ビルドでは `STRATA_MMQ_KQ` の先頭文字が `1` の場合だけ K-quant を MMQ 対象として扱います。
- K-quant の MMQ 対応は `STRATA_MMQ_KQUANTS` が定義されたビルドに限られます。対象のモデルに `Q4_K` / `Q5_K` / `Q5_1` / `Q6_K` の expert がなければ、その K-quant 経路は使われません。

## 実行時の詳細

`generate` は GPU を確認した後、最小 compute capability を求めて `apply_nv_kq_default()` を呼びます。この関数は `nv_kq_default_env()` の結果にある変数だけを、プロセス環境で未設定の場合に `setenv(..., 0)` または `_putenv_s()` で設定します。対象スイッチを新たに設定したときだけ stderr に、K-quant experts があれば prompt を MMQ kernel で処理する旨と、`STRATA_MMQ_KQ=0` または `STRATA_NV_KQ_DEFAULT=0` で止められる旨を出します。`STRATA_MMQ_KQ` が事前設定済み、対象変数で無効、対応 GPU がない、または master switch が有効な場合、この設定ログは出ません。

`STRATA_NV_KQ_DEFAULT` 自体は helper の呼び出しごとに読みますが、通常の `generate` 実行では GPU 初期化時に一度呼ばれるため、その後の環境変更で既定設定は再計算されません。下流の K-quant 判定は `STRATA_MMQ_KQ` を初回使用時に static cache します（DSO ビルドでは loader の `wanted()` が同様に初回使用時に cache します）。

K-quant MMQ が有効な DSO ビルドでは、Strata は engine の隣にある K-quant library をロードします。見つからない場合、engine と ABI が一致しない場合、または GPU 初期化に失敗した場合は stderr に理由を出し、その experts を FP16 prompt 経路へ fallback します。正常にロードすると library のパスを stderr に表示します。DSO 内部の計算動作はこの文書の対象外です。

## 根拠

- 対象変数の唯一の本番読み取り、世代 / master-switch 判定、先頭文字判定、`STRATA_MMQ_KQ=1` の候補: `src/core/nv_defaults.cpp:113-127`。
- 未設定時のみ環境に設定し、設定値を保持する処理と設定ログ: `src/core/nv_defaults.cpp:129-143`。
- 起動時の呼び出し、CUDA 限定、見えている GPU の最小 compute capability の決定: `src/program/generate.cpp:3846-3871`。
- `STRATA_DEFAULTS=026` の値比較と初回読み取り cache: `include/strata/core/defaults_026.hpp:21-29`。
- compute capability の emulation: `include/strata/core/emulate.hpp:14-24`。
- K-quant 型の MMQ 対象判定と compile macro 条件: `src/prefill/moe_mmq.cu:41-54,319-345`。
- DSO のロード失敗、ABI / GPU 初期化失敗時の FP16 fallback と成功ログ: `src/prefill/mmq_kq_loader.cpp:58-98`。
- 索引 `docs/envvars/000_envvers.md` は候補名として `STRATA_NV_KQ_DEFAULT` を列挙しており、上記の本番読み取り箇所を確認しました。
