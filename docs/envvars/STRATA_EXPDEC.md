# `STRATA_EXPDEC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の `native_expert_grouped` における resident expert の gate/up 計算で、既定 kernel ではなく EXPDEC kernel を選べるようにするフラグです。EXPDEC kernel は routed group の q8_1 activation を shared memory に置いて処理します。down projection も `STRATA_EXPDEC_DOWN` 等の条件がそろえば対象になります。EXPDEC が無効、または layout が対象外なら呼び出し元は既定 kernel に進みます（`engine/src/kernels/cuda/iq_kernels.cu:4452-4466,4486-4493,7306,7402-7409`）。

## 値と判定

`env_on` は `std::getenv` の結果が null でなく、先頭文字が NUL でも `'0'` でもないとき true を返します。文字列全体や数値としては parse しません（`engine/src/kernels/cuda/iq_kernels.cu:3689-3692,4360-4362`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常の評価 | `0`（既定 kernel） | 先頭文字が `'0'` 以外の非空文字列。例: `1`, `true`, ` 0`, `0anything` 以外の文字列 | 空文字、`0`, `0anything`, `00`。大文字小文字・後続文字・数値妥当性は判定しない |
| HIP の gfx12 / discrete RDNA3 起動時既定値 | 既定適用が有効なら `1` が設定される | 明示値が上記判定で true | 明示値が上記判定で false。明示設定は自動既定値に置き換わらない |

この変数自体を読むコードに CLI 引数との直接の優先順位はありません。HIP のアーキテクチャ既定値は `getenv(...) != nullptr` なら設定を追加しないため、ユーザー環境の値（空文字や `0` を含む）が優先されます（`engine/src/core/arch_defaults.cpp:307-310,320-324`）。

## 有効になる条件

- `STRATA_EXPDEC` が有効判定になり、旧 IQ kernel を選ぶ `STRATA_OLD_IQ_MMVQ` が有効でないこと。旧 kernel が有効なら gate/up と down の EXPDEC 選択を早期に止めます（`engine/src/kernels/cuda/iq_kernels.cu:3693-3695,4453-4458,4486-4490`）。
- gate/up は `gu_type` が 16, 17, 18, 21, 22 のいずれかで、`had_block == 0`、`tail_off == 0`、`n_embd == 32 * ED_XB`、`n_ff > 0` かつ 64 の倍数であること。条件外では既定 kernel に戻ります（`engine/src/kernels/cuda/iq_kernels.cu:4378-4381,4456-4466`）。
- down はさらに `STRATA_EXPDEC_DOWN` が非ゼロであることが必要です。`d_type == 42` (Q2_0)、または `d_type == 20` かつ `STRATA_EXPDEC_D20` が非ゼロであり、`had_block == 0`、`tail_off == 0`、`n_ff == 32 * ED_HB`、`n_embd > 0` かつ 128 の倍数である必要があります（`engine/src/kernels/cuda/iq_kernels.cu:4366,4371,4382-4384,4486-4493`）。
- HIP の起動時既定値として `STRATA_EXPDEC=1` を補うのは、`gfx12` と discrete RDNA3 (`gfx1100/1101/1102`) のアーキテクチャ表です。`STRATA_GFX12_DEFAULTS=0` または `STRATA_GFX11_DEFAULTS=0` はそれぞれの表を止め、`STRATA_DEFAULTS=026` も旧既定値に戻します。既定値適用自体は HIP build の起動経路で実行されます（`engine/src/program/generate.cpp:4282-4285,4315`; `engine/src/core/arch_defaults.cpp:30-42,50-55,307-310,312-324`; `engine/include/strata/core/gfx11_extra.hpp:27-30,39-45,55-64`; `engine/include/strata/core/defaults_026.hpp:26-30`）。
- down projection の既定有効化は現行コードでは確認できません。`g_expdec_down` の環境読み取り fallback は `0` で、アーキテクチャ表にも `STRATA_EXPDEC_DOWN` はありません（`engine/src/kernels/cuda/iq_kernels.cu:4370-4371`; `engine/src/core/arch_defaults.cpp:43-62`; `engine/include/strata/core/gfx11_extra.hpp:46-75`）。一方、`docs/EXPERTDEC.md:3-5,34-38` は gfx12 の Q2_0 down が既定で有効と説明しており、コードと文書に食い違いがあります。

## 実行時の詳細

`g_expdec` は初期値 `-1` で、`expdec_mode()` の初回呼び出し時に `STRATA_EXPDEC` を読み、その結果を保存します。コードコメントでは、アーキテクチャ既定値設定の後に初回評価する意図が示されています。したがって初回評価後にプロセス環境だけを変更しても反映されませんが、engine API `native_expert_set_expdec(int)` は cache を `0` / `1` に上書きでき、負値なら次の評価で環境を再読します（`engine/src/kernels/cuda/iq_kernels.cu:4360-4362,7055-7056`; 起動順: `engine/src/program/generate.cpp:4282-4285,4315`）。

EXPDEC の gate/up と down はそれぞれ適合条件を確認し、適合すれば専用 kernel を launch して `true` を返し、呼び出し元の既定 kernel を抑止します。適合しない場合は `false` を返し、呼び出し元が通常 kernel を実行します（`engine/src/kernels/cuda/iq_kernels.cu:4452-4466,4486-4493,7306,7402-7409`）。プロセス起動後の環境変更や子プロセスへの `STRATA_EXPDEC` の転送を行う処理は、この変数の参照経路では確認できません。

## ログと測定値

EXPDEC を有効にして対象 layout に到達すると、role と format ごとに初回だけ stderr に実行 kernel、行数、grid 等を出します。適合しない layout では `strata expdec: CUDA%d %s type %d (n_embd %lld, n_ff %lld) not covered: the default kernel runs` を出します。適合する場合は gate/up または down の `strata expdec: ...` 行を出し、stream capture 中なら末尾に `, captured into a graph` が付きます。`STRATA_EXPDEC` が無効、または `STRATA_OLD_IQ_MMVQ` で早期 return する場合はこの記録関数まで到達しません（`engine/src/kernels/cuda/iq_kernels.cu:4421-4449,4453-4458,4486-4490`）。

`docs/EXPERTDEC.md:76-108` は、RTX 2080 Ti / RTX 3060 の `expdec_bench` gate/up 比較、RTX 2080 Ti の 131k decode における gate/up 比較、および同機での end-to-end 測定を記載しています。これらは資料中の測定値であり、この調査では再測定していません。

## 根拠

- 読み取り・値判定・cache: `engine/src/kernels/cuda/iq_kernels.cu:3689-3692,4360-4362`
- 適用条件・kernel 選択・fallback: `engine/src/kernels/cuda/iq_kernels.cu:4378-4384,4452-4493,7306,7402-7409`
- HIP の既定値と明示値の優先: `engine/src/program/generate.cpp:4282-4285,4315`; `engine/src/core/arch_defaults.cpp:28-55,302-324`; `engine/include/strata/core/gfx11_extra.hpp:27-30,39-45,55-64`
- API による cache 上書き: `engine/src/kernels/cuda/iq_kernels.cu:7055-7056`
- ログ: `engine/src/kernels/cuda/iq_kernels.cu:4421-4449`
- 測定資料と down 既定値の記述: `docs/EXPERTDEC.md:3-5,34-42,76-108`
