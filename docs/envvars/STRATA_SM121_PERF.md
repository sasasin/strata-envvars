# `STRATA_SM121_PERF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA compute capability 12.1（GB10 / DGX Spark）向けの起動時既定値セットと、sm_120 系 kernel のうち GB10 でも測定済みの既定を制御する。未設定時は有効で、`STRATA_SM121_PERF=0` はその既定を無効にする。既定値セットは engine 初期化処理で個別スイッチが読まれる前に環境へ設定され、設定された個別スイッチが各処理を選ぶ。個々の既定ルールは CUDA kernel からも GPU ごとに評価される。ソース上の対象は `engine/src/core/nv_defaults.cpp`、`engine/include/strata/core/sm120_series.hpp` と CUDA kernel 群。

既定値表は `STRATA_PF_FUSED=1`、`STRATA_PF_FUSED_KQ=1`、`STRATA_HC_UPMIX=1`、`STRATA_SIDE_MIXER=2`、`STRATA_SPEC_COST=1`、`STRATA_DEQUANT_SIDE=1`、`STRATA_QFUSE=1`、`STRATA_LFUSE=1`、`STRATA_PLE_COMPACT=1`、`STRATA_PLE_COPY_STREAM=1`、`STRATA_PREFILL_NVFP4=w4a4`。主 GPU の報告 VRAM が閾値以下なら `STRATA_ADAPT_FETCH=2`、そうでなく閾値より大きければ `STRATA_VERIFY_DEVICE_HITS=1` も候補に加わる。各個別変数が既に環境にあれば、その値は変更しない。加えて、CUDA kernel の既定値ルールでは GB10 に `STRATA_ATTN_DAILY` と `STRATA_GR_DOWN_TG` の既定も有効になる（後者は 48 SM の GB10 で 2）。さらに CUDA grouped expert mode は `STRATA_EXP_MODE` が未設定なら GB10 で 8 を選ぶ。これらの kernel 既定も対象変数または `STRATA_DEFAULTS=026` により無効になる。`STRATA_SM121_PERF` 自体は、個別スイッチの一般的な実行時効果を一括して書き換えるのではなく、これらの既定選択を止めるスイッチである。`engine/src/core/nv_defaults.cpp:176-217`、`engine/src/core/nv_defaults.cpp:222-255`、`engine/include/strata/core/sm120_series.hpp:63-81`、`engine/src/kernels/cuda/iq_kernels.cu:6792-6802`、`engine/src/kernels/cuda/fused_gr.cu:1582-1607`

## 値と判定

値の規則は読み取り箇所で一致しない。`nv_defaults.cpp` の表は設定値の先頭文字が `0` なら停止し、それ以外なら有効とする。一方、GPU kernel の GB10 既定判定は `atoi(value) != 0` を使う。従って、空文字や `false` などでは表の設定だけ行われて GPU kernel 側の既定は停止する場合がある。`engine/src/core/nv_defaults.cpp:14-18`、`engine/include/strata/core/sm120_series.hpp:66-73`

| 読み取り経路 | 未設定 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| GB10 の起動時既定値表 (`off`) | 有効 | `1`, `true`, 空文字, ` 0`, `abc` | `0`, `0anything`, `01` |
| sm_120 系 CUDA kernel の GB10 既定判定 (`atoi`) | 有効 | `1`, `2`, `1anything` | `0`, `0anything`, 空文字, `false`, ` 0` |

`atoi` は先頭の空白と符号付き整数部分を読み、整数に変換できない文字列は 0 として扱う。変換後の値が非ゼロかだけを判定するため、小数部・末尾文字列は無視される。表側の判定は文字列全体を parse せず `v[0] == '0'` のみを見る。いずれも大文字小文字を変換・比較しない（表側は最初の文字だけなので、`false` は停止条件に当たらない）。`engine/src/core/nv_defaults.cpp:14-18`、`engine/include/strata/core/sm120_series.hpp:67-71`

## 有効になる条件

- 起動時の既定値表を適用する経路は CUDA build であり、`generate.cpp` の呼出しは HIP と Metal を除外する。CUDA device が 1 台以上見つかり、全可視 device の compute capability が同一で、その値が 12.1 のとき `apply_nv_defaults` が呼ばれる。異種 GPU 構成、device 属性取得失敗、CUDA device がない場合、この起動時表は適用されない。`engine/src/program/generate.cpp:4421-4449`
- 表は `STRATA_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致する場合も空になる。`STRATA_DEFAULTS` は初回呼出し時に cache される。`engine/include/strata/core/defaults_026.hpp:21-29`、`engine/src/core/nv_defaults.cpp:176-180`
- 表の各変数が既に設定されていれば、値が `0` や空文字でもユーザー設定として保持され、表から上書きされない。個別変数の最終的な有効・無効規則はその変数の読み取り実装に従う。`engine/src/core/nv_defaults.cpp:222-234`
- `STRATA_ATTN_DAILY` と `STRATA_GR_DOWN_TG` の GPU 既定判定は CUDA kernel の経路で使われ、HIP build ではそれぞれ早期に無効を返す。`sm12x_default` に渡された当該スイッチの GB10 測定定数が true のときだけ `STRATA_SM121_PERF` が判定に参加する。ほかの GB10 定数は false である。`engine/include/strata/core/sm120_series.hpp:93-101`、`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923`、`engine/src/kernels/cuda/fused_gr.cu:1582-1607`
- 対象変数は sm_121 向けで、sm_120 の既定規則は `sm12x_default` の別分岐であるため、この変数では止まらない。`engine/include/strata/core/sm120_series.hpp:60-81`
- `STRATA_EXP_MODE` が未設定のときの CUDA grouped expert mode 8 は、compute capability 12.1、`STRATA_DEFAULTS=026` 以外、そして `STRATA_SM121_PERF` が未設定または `atoi` で非ゼロという条件を使う。HIP ではこの CUDA mode-selection 経路を使わない。`engine/src/kernels/cuda/iq_kernels.cu:6792-6802`
- CLI 引数による `STRATA_SM121_PERF` の上書き読み取りは見つからなかった。モデル内に K-quant experts がある場合だけ、別個に設定される `STRATA_PF_FUSED_KQ` がその prompt 経路に関係するが、対象変数の表適用自体にモデル種別の条件はない。`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:185-192`

## 実行時の詳細

CUDA engine の初期化では、可視 GPU の compute capability がすべて同一の場合に、代表値と `STRATA_PRIMARY_DEVICE`（未設定時は device 0）で選ばれる主 GPU のメモリ量を使い `apply_nv_defaults` を呼ぶ。GB10 かつ `STRATA_SM121_PERF` の表判定が有効で、`STRATA_DEFAULTS=026` でなければ既定値表を作る。未設定のスイッチだけを Windows では `_putenv_s`、それ以外では `setenv(..., 0)` でプロセス環境に追加し、以後の engine/kernel が読む。`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:176-180`、`engine/src/core/nv_defaults.cpp:222-239`

起動時表判定の `off("STRATA_SM121_PERF")` は関数呼出しごとに `getenv` し、static cache は持たない。`sm121_series()` の kernel 既定判定と `iq_kernels.cu` の grouped expert mode 判定は初回呼出し時の `getenv` と `atoi` の結果を関数内 `static` に保存する。関連 kernel もスイッチ判定を static に保存し、GPU ごとの既定を `per_dev[64]` に cache する。従って実行中に環境値を変更しても、既に評価された既定判定や device の選択は更新されない。子プロセスへの転送を行うコードはこの変数について確認できなかった。`engine/src/core/nv_defaults.cpp:14-18`、`engine/include/strata/core/sm120_series.hpp:67-73`、`engine/src/kernels/cuda/iq_kernels.cu:6792-6802`、`engine/src/kernels/cuda/qsa_decode_attn.cu:906-922`、`engine/src/kernels/cuda/fused_gr.cu:1587-1607`

## ログと測定値

既定値表から一つ以上の変数を追加した場合は stderr に次の形式で一行を出す。件数と個別スイッチ名は実行条件と、既にユーザー設定されているスイッチにより変わる。

```text
strata: sm_121 (GB10): %zu speed switches on by default (STRATA_SM121_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ...
```

表が無効、または個別変数がすべて既に設定されていて追加がない場合、このログは出ない。GPU kernel の `sm121_series()` 判定自体はログを出さない。測定値はこの文書では扱わない。`engine/src/core/nv_defaults.cpp:240-255`

## 根拠

- `engine/src/core/nv_defaults.cpp:14-18` — 起動時表の値判定 helper。
- `engine/src/core/nv_defaults.cpp:176-219` — GB10 の表、`STRATA_DEFAULTS=026` 条件、主 GPU メモリ依存の追加。
- `engine/src/core/nv_defaults.cpp:222-255` — 個別設定の保持、プロセス環境への追加、stderr ログ。
- `engine/include/strata/core/sm120_series.hpp:63-81` — GB10 判定、対象変数の `atoi` と static cache、sm_120 系既定規則。
- `engine/src/program/generate.cpp:4421-4449` — CUDA 起動経路、同一 compute capability 条件、主 GPU の選択と表適用。
- `engine/src/kernels/cuda/iq_kernels.cu:6792-6802` — `STRATA_EXP_MODE` の GB10 既定判定にも対象変数を直接使用し、device 別に cache。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:902-923` — `STRATA_ATTN_DAILY` の CUDA / HIP 分岐と device 別既定 cache。
- `engine/src/kernels/cuda/fused_gr.cu:1582-1607` — `STRATA_GR_DOWN_TG` の値解釈と GB10 device 判定。
- `engine/include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS` の許容文字列と static cache。
