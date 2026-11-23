# `STRATA_GFX11_WMMA_DEFAULTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、AMD HIP の離散 RDNA3（`gfx1100` / `gfx1101` / `gfx1102`）向けに Strata が自動で有効にする matrix-core・MoE・関連 Q8 の既定値セットを止めるスイッチである。`gfx11_wmma_defaults_disabled()` は、この変数または上位の `STRATA_GFX11_DEFAULTS` が無効指定かを判定し、`gfx11_discrete_wmma_env()` が有効なら `STRATA_HIP_WMMA=1`、`STRATA_PA_FAST=1`、`STRATA_SELECT_WMMA=1`、`STRATA_PF_GEMM=1`、`STRATA_HC_UPMIX=1`、`STRATA_PF_FUSED=1`、`STRATA_PF_F16=2`、`STRATA_PF_DM16=1`、`STRATA_PF_P1A=1`、`STRATA_PF_P1A_L2=1`、`STRATA_DFLASH_WMMA=1`、`STRATA_HIP_FAST_DEC=1` を既定として設定する（`engine/include/strata/core/gfx11_extra.hpp:33-37,87-109`）。

`=0` はこの WMMA 系セットを抑止するが、Strata が個別スイッチに明示値を設定する動作を強制的に禁止するものではない。`STRATA_GFX11_DEFAULTS=0` はこのセットに加え、別枠の bitwise-exact RDNA3 既定セットも止める。WMMA セットが抑止されても、その個別スイッチを利用者が別途設定していれば、その設定は既定適用時に保持される（同 `:8-12,27-37`、`engine/src/core/arch_defaults.cpp:318-344`）。

## 値と判定

| 条件 | unset | 無効になる値 | 無効にならない値 |
|---|---|---|---|
| `gfx11_wmma_defaults_disabled()` の判定 | WMMA 既定値を許可。ただし `STRATA_DEFAULTS=026` または `STRATA_GFX11_DEFAULTS` の無効指定が優先 | 値の先頭文字が `0`（例: `0`, `00`, `0anything`, `0 `） | 空文字、`1`、`true`、`false`、先頭が空白の ` 0` など |

対象変数は `std::getenv` で読み、null でなく、かつ `woff[0] == '0'` のときだけ無効扱いになる。数値変換も文字列全体の比較も行わず、大文字小文字は判定に関係しない。したがって空文字は「設定あり」でも無効化しない。先に `defaults026` が真、または `STRATA_GFX11_DEFAULTS` の先頭文字が `0` なら、対象変数を読む前に無効が決まる（`engine/include/strata/core/gfx11_extra.hpp:27-37`）。

対象変数の先頭が `0` 以外なら、単独ではスイッチ群を強制的に有効化せず、既定値セットを許可するだけである。`STRATA_DEFAULTS=026` は `qwen_defaults_026()` が `STRATA_DEFAULTS` 全体を `026` / `0.2.6` / `v0.2.6` と完全一致で比較した結果であり、その結果は関数内 `static` に一度だけ保存される（`engine/include/strata/core/defaults_026.hpp:21-30`）。

## 有効になる条件

- 既定値を環境へ設定する経路は `STRATA_USE_HIP` のコード内から呼ばれる。起動時に HIP デバイスの情報を取得でき、`apply_arch_defaults()` に渡された GPU が統合 GPU でなく、かつアーキテクチャ名が離散 RDNA3 の `gfx1100` / `gfx1101` / `gfx1102` と一致する必要がある。名前の末尾は終端または `:` が許される。CUDA・SYCL、統合 GPU、他の gfx11（例 `gfx1103` / `gfx1151`）ではこの既定セット適用箇所は対象外（`engine/src/program/generate.cpp:4282-4315`; `engine/src/core/arch_defaults.cpp:312-320`; `engine/include/strata/kernels/gfx_arch.hpp:15-26`）。
- `STRATA_DEFAULTS=026` または `STRATA_GFX11_DEFAULTS` の先頭が `0` なら、対象変数が未設定または `1` でも WMMA セットは作られない。`STRATA_GFX11_DEFAULTS` は bitwise-exact セットと並列リクエスト用セットにも適用される一段上の抑止スイッチである（`engine/include/strata/core/gfx11_extra.hpp:27-37,41-45,90-109,116-133`）。
- 既定セット中の各名前は、既に環境に存在すれば値を変えずスキップされる。空文字を含め「設定済み」なら保持されるため、個別スイッチの明示値がこの変数で上書きされることはない（`engine/src/core/arch_defaults.cpp:334-344`）。
- `STRATA_DFLASH_WMMA` は DFlash attention 経路で別に判定される。空または未設定なら RDNA3 の WMMA 既定判定に進むが、先頭が `0` なら DFlash WMMA を止め、先頭が `0` 以外の非空値なら GPU 世代の確認後に `STRATA_GFX11_WMMA_DEFAULTS` の判定を迂回して有効にする。この明示的な個別設定は、本変数による既定値抑止より優先する（`engine/src/kernels/cuda/dflash2.cu:542-560,1696-1703`）。
- prompt CPU share の RDNA3 既定有効化は、HIP（`STRATA_HIP_GFX906` 以外）で、その経路が適用対象かつ `STRATA_PREFILL_CPU_SHARE` に明示設定がない場合に限る。ここでは対象変数または `STRATA_GFX11_DEFAULTS` が無効なら既定 ON にしない（`engine/src/prefill/prefill.cpp:3842-3864`; `engine/include/strata/core/gfx11_extra.hpp:140-146`）。

## 実行時の詳細

通常のエンジン起動では `generate.cpp` が HIP デバイス属性を読み、`apply_arch_defaults()` を呼ぶ。離散 RDNA3 向けの WMMA 既定テーブルを得た後、まだ環境にない各項目を `setenv(..., 0)`（Windows は `_putenv_s`）で設定する。対象変数はこの既定値適用のたびに直接参照され、Strata 側で値をキャッシュしない。一度既定値群が環境へ設定された後は、環境変数としてそのプロセス内に残り、後続の機能判定で参照される（`engine/src/program/generate.cpp:4282-4315`; `engine/src/core/arch_defaults.cpp:218-224,312-344`）。

別の利用箇所として、native dense の `hc_q8_env()` は関数内 `static` の初回評価時に対象判定を行い、その bool を以後再利用する。ここでは `STRATA_HC_Q8` が `1` で始まればその明示指定が先に有効になり、未設定・空文字・`auto` の場合に RDNA3 の対象判定へ進む（`engine/src/core/native_dense.cpp:47-56,71-83,98-100`）。prefill の CPU share 判定は `gfx11_prefill_share_default()` 経由で呼び出しごとに判定する（`engine/src/prefill/prefill.cpp:3842-3864`; `engine/include/strata/core/gfx11_extra.hpp:140-146`）。

DFlash の WMMA 選択では、`STRATA_DFLASH_WMMA` の判定結果を関数内 `static` に保存し、GPU の WMMA 対象判定も `PerDeviceFlag` でデバイスごとに保持する。一方、個別スイッチが未設定・空文字のときに参照される `STRATA_GFX11_WMMA_DEFAULTS` と `STRATA_GFX11_DEFAULTS` の判定は、その呼び出しで直接行う（`engine/src/kernels/cuda/dflash2.cu:542-560`）。

## ログと測定値

既定セットの項目が一つ以上新たに設定されたとき、stderr に `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default (STRATA_GFX11_WMMA_DEFAULTS=0 or STRATA_GFX11_DEFAULTS=0 turns them off; NAME=0 turns one off): ` に件数と設定名が続く行を出す。対象変数などで既定セットが空になるか、12 項目すべてがすでに環境にある場合はこの行を出さない（`engine/src/core/arch_defaults.cpp:334-344`）。

prefill の CPU share 既定を実際に有効にしたときは別途 `prefill: the CPU share is ON by default for prompt chunks up to ...` の行を出す（`engine/src/prefill/prefill.cpp:3855-3862`）。このコードのコメントには first-token KL の範囲があるが、本書では性能や正確性の実測を独立に確認したものとして扱わない。

対象変数自体について、無効値の警告、エラー、終了処理は見つからない。値によって既定セットが抑止された場合に起動を失敗させる専用経路もない。

## 根拠

- `engine/include/strata/core/gfx11_extra.hpp:27-37,87-109,139-146` — 対象値の判定、WMMA 既定値一覧、CPU share 既定判定。
- `engine/src/core/arch_defaults.cpp:218-224,312-344` — 明示環境値の保持、既定値設定、stderr 行。
- `engine/src/program/generate.cpp:4282-4315` — HIP 起動時の GPU 判定と適用。
- `engine/src/core/native_dense.cpp:47-56,71-100` — HC Q8 経路と cache。
- `engine/src/prefill/prefill.cpp:3842-3864` — CPU share 既定の適用条件。
- `engine/src/kernels/cuda/dflash2.cu:542-560,1696-1703` — DFlash の値優先順位、GPU cache、HIP 経路。
- `engine/include/strata/kernels/gfx_arch.hpp:15-26` — RDNA3 のアーキテクチャ名判定。
- `engine/include/strata/core/defaults_026.hpp:21-30` — `STRATA_DEFAULTS=026` の完全一致判定と cache。
