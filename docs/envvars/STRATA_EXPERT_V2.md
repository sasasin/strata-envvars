# `STRATA_EXPERT_V2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

CUDA/HIP の grouped expert decode で、条件に合う IQ3_S gate/up と IQ4_NL down の組に S26 カーネルを選びます。S26 は gate/up、SwiGLU と Q8_1 量子化、down を専用カーネル列で処理します。名前に `V2` が含まれますが、この変数は `STRATA_EXPERT_V2K` の Q4_K/Q5_K 系 S27 経路とは別です。

## 値と判定

カーネル側は `getenv()` の値の先頭文字だけを検査し、`'1'` と一致した場合に有効とします。文字列全体や数値としての妥当性は調べず、大文字小文字も関係しません。

| 値 | カーネル側の判定 |
|---|---|
| 未設定 | 無効。ただし gfx1151 向け HIP 起動時の既定値設定が行われる場合を除く |
| 空文字 | 無効（環境変数自体は設定済み） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1`, その他先頭が `1` でない文字列 | 無効 |

gfx1151 の HIP では、起動時に適用されるアーキテクチャ既定値が別途優先順位に影響します。ユーザーがこの変数を何らかの値（空文字を含む）で設定していれば Strata は上書きしません。そのため、たとえば `0` や空文字は既定の有効化を抑止します。

## 有効になる条件

- CUDA/HIP grouped expert の実行で、レイアウトが `gu_type == 21`（IQ3_S）、`d_type == 20`（IQ4_NL）、`n_embd == 2560`、`n_ff == 640` のすべてに一致すること。未一致なら、この変数が有効でも S26 分岐を通らず既存の grouped expert 経路へ進みます。
- S26 分岐のある `src/kernels/cuda/iq_kernels.cu` が使われる実行経路であること。SYCL 版はこの S26/S27 カーネルをビルドせず、この変数を有効値として読んでも無視します。
- gfx1151（Strix Halo）の HIP 起動では、`STRATA_GFX1151_DEFAULTS` が先頭文字 `0` でない場合、Strata はこの変数を未設定時に `1` にします。`STRATA_GFX1151_DEFAULTS=0` はアーキテクチャ既定値テーブル全体を無効にします。gfx1151 以外の HIP と CUDA では、このテーブルによる自動設定はありません。

カーネルのレイアウト条件自体は GPU 世代を分岐条件にしていません。従って CUDA や gfx1151 以外の HIP でも、利用者が先頭文字 `1` の値を明示設定すれば、上記レイアウトに対してコード上は S26 分岐の候補になります。実機での各 GPU の性能・動作はこのコード調査では検証していません。

## 実行時の詳細

CUDA/HIP カーネル側では `native_expert_grouped()` の初回実行時に `static const bool` として値を読み、プロセス内でキャッシュします。最初の評価後に環境を書き換えても、この判定は更新されません。適用対象なら S26 の gate/up カーネル、SwiGLU と Q8_1 変換、down カーネルを同じ stream に順に launch し、CUDA/HIP のエラーチェックを行って戻ります。

gfx1151 HIP では engine の引数処理後、engine が環境スイッチを初回参照する前にデバイス 0 の `gcnArchName` を取得し、アーキテクチャ既定値を適用します。環境変数が既に存在する場合は値を問わず保持し、Strata 自身が値を設定した場合は stderr に既定スイッチ名を列挙する行を出します。CUDA ビルドではこの呼び出しはコンパイル対象外です。

SYCL では grouped expert 経路に入った際、`STRATA_EXPERT_V2` または `STRATA_EXPERT_V2K` のどちらかが先頭文字 `1` なら、初回だけ stderr に次を出します: `note: STRATA_EXPERT_V2 / STRATA_EXPERT_V2K are AMD-only experiments, ignored on SYCL`。SYCL 側でこの変数によるカーネル切り替えはありません。

## 文書との照合

`docs/STRIX_HALO.md` は、この変数を `STRATA_TSUM` と `STRATA_LFUSE` とともに、IQ3_S/IQ4_NL の grouped decode expert 系として説明し、Strix Halo の既定有効スイッチに含めています。同資料は、該当スイッチ群について maintainer 機での同一 token 出力、4K/32K/64K および4モデルでの確認と、カーネル単位の bitwise harness を述べています。これは資料に記載された検証範囲であり、本調査で測定を再実施したものではありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3451-3475` — grouped expert の環境値判定、形式・寸法条件、S26 launch、既存経路への分岐。
- `src/kernels/cuda/iq_kernels.cu:2006-2013,2333-2346` — S26 実装の説明、S26 kernel 列。
- `include/strata/artifact/gguf_reader.hpp:189-196` — GGUF 型 20 と 21 の IQ4_NL / IQ3_S 対応。
- `src/program/generate.cpp:2152-2158` — HIP での起動時アーキテクチャ既定値適用。
- `src/core/arch_defaults.cpp:32-58,61-80` — gfx1151 限定テーブル、`STRATA_GFX1151_DEFAULTS` による停止、利用者設定の保持、stderr 出力。
- `include/strata/core/arch_defaults.hpp:19-26` — 対象アーキテクチャ、呼び出し時期。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5065-5073` — SYCL での無視と一度限りの note。
- `docs/STRIX_HALO.md:86-97` — Strix Halo での既定値と資料記載の検証範囲。
