# `STRATA_DFLASH_WMMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

HIP/AMD の DFlash2 drafter が attention を計算するとき、対象 gfx11 GPU 上で Wave32 FP16 WMMA kernel を選ぶかを制御する。ON なら通常の `attn_part_kernel` の代わりに `attn_part_wmma_gfx11_kernel` を起動する。DFlash2 自体を有効にする変数ではなく、DFlash2 を使う実行の attention 経路だけに作用する。CUDA build ではこの環境変数を読まず、別条件の CUDA Tensor Core kernel 選択を行う（`engine/src/kernels/cuda/dflash2.cu:1696-1722`）。

## 値と判定

`df2_attn_wmma_enabled()` は `std::getenv` の結果を関数内 `static` に一度だけ保存する。未設定または空文字は自動判定値 `-1`、先頭文字が `0` の非空値は OFF、その他の先頭文字は ON として扱う。文字列全体の比較や数値変換はせず、大文字小文字・空白・後続文字も検査しない（`engine/src/kernels/cuda/dflash2.cu:542-548`）。

| 値 | 判定 | 例 |
|---|---|---|
| unset / 空文字 | gfx11 対応 GPU と他の既定値スイッチによる自動判定 | 未設定、`""` |
| 非空で先頭が `0` | OFF | `0`, `00`, `0anything` |
| 非空で先頭が `0` 以外 | 明示 ON | `1`, `true`, `false`, ` 0`, `-1` |

関数内 static のため、環境をプロセス起動後に変更しても、この値を初回評価した後は反映されない。初回評価で未設定・空文字だった場合の自動判定は別途 `STRATA_GFX11_DEFAULTS` と `STRATA_GFX11_WMMA_DEFAULTS` を呼び出すたびに読み直す（同ファイル `:542-560`）。

| 条件 | unset / 空文字 | 設定時 |
|---|---|---|
| HIP/AMD、対応 GPU、`g_attn_variant == 0` | 両 GFX11 既定値スイッチが先頭 `0` でなければ ON。いずれかが先頭 `0` なら OFF | 上記の値判定に従う。先頭 `0` 以外なら GFX11 既定値スイッチより優先して ON |
| CUDA build または対応外 GPU / variant | この変数による WMMA 経路は選択されない | 同左 |

## 有効になる条件

- Strata が HIP/AMD build であること。HIP 分岐内だけでこの判定を呼ぶ（`engine/src/kernels/cuda/dflash2.cu:1696-1703`）。
- DFlash2 attention 呼び出しで `g_attn_variant == 0` であること。この変数は bench 用 variant setter で変更される（同ファイル `:27`, `:1699`, `:1762-1763`）。
- 実行デバイスの `gcnArchName` が `gfx1100`, `gfx1101`, `gfx1102`, `gfx1103`, `gfx1150`, `gfx1151` のいずれかであること。WMMA kernel のコンパイル guard と実行時の `gfx_arch_is_gfx11_wmma` 判定がこの対象を列挙する（同ファイル `:91-96`, `:552-556`; `engine/include/strata/kernels/gfx_arch.hpp:28-32`）。
- `STRATA_DFLASH_WMMA` が未設定・空文字の自動判定では、`STRATA_GFX11_DEFAULTS` または `STRATA_GFX11_WMMA_DEFAULTS` の先頭が `0` なら無効。先頭文字だけを調べる（同ファイル `:558-560`; `engine/include/strata/core/gfx11_extra.hpp:27-37`）。明示的な本変数の値が先頭 `0` 以外ならこの自動判定スイッチに優先する。
- GPU の現在デバイス番号取得に失敗した場合はエラー状態をクリアして無効扱いにする。デバイス属性の確認に失敗した場合も対応 GPU と判定されず、通常 kernel へ進む（`engine/src/kernels/cuda/dflash2.cu:549-556`）。
- `engine/src/program/generate.cpp:4282-4315` の HIP 起動時既定値設定は、Windows gfx1151 の arch default 群と discrete gfx1100–gfx1102 の WMMA default 群として本変数を `1` に設定する。ただし既に環境に値があれば空文字を含めて上書きしない。Windows gfx1151 群は `STRATA_GFX1151_DEFAULTS=0` で除外される。discrete 群は integrated GPU では適用せず、`STRATA_DEFAULTS=026`、`STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0` のいずれかで除外される（`engine/src/core/arch_defaults.cpp:28-29, 64-66, 193-214`; `engine/include/strata/core/gfx11_extra.hpp:33-37, 87-114`）。この既定値設定は環境変数をセットする処理で、変数自体の自動判定とは別段階。なお変数が未設定・空文字のときの WMMA 自動判定に `STRATA_DEFAULTS=026` や `STRATA_GFX1151_DEFAULTS` は直接参照されず、同判定が参照するのは `STRATA_GFX11_DEFAULTS` と `STRATA_GFX11_WMMA_DEFAULTS`。

## 実行時の詳細

`df2_attention()` は HIP build で、variant が 0 かつ `df2_attn_wmma_enabled()` が true の場合に `attn_part_wmma_gfx11_kernel` を起動し、直後に `check("attn_part_wmma_gfx11")` を呼ぶ。それ以外は通常の `attn_part_kernel` と `check("attn_part")` に進み、その後いずれも `attn_merge_kernel` を実行する（`engine/src/kernels/cuda/dflash2.cu:1696-1724`）。WMMA kernel は Q/K を FP16 にし、Wave32 WMMA を用いて attention 部分結果を計算する（同ファイル `:345-359, 372-383, 448-455, 507-533`）。

`STRATA_DFLASH_WMMA=0` は WMMA 選択を止めるだけで、DFlash2 attention を止めず通常 kernel にフォールバックする。対象 GPU 判定に失敗した場合も同じ通常 kernel 経路となる。WMMA kernel 起動後に HIP/CUDA runtime のエラーを検出すると、`check` は stderr に `dflash2 kernel attn_part_wmma_gfx11: <runtime error>` を出し、同じ内容の `std::runtime_error` を投げる。ここでは通常 kernel への再試行はしない（同ファイル `:29-34, 1699-1702`）。

アーキテクチャ既定値が本変数を設定したときは、適用された名前を一覧にする stderr 行が出る。WMMA 群の文言は `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default (STRATA_GFX11_WMMA_DEFAULTS=0 or STRATA_GFX11_DEFAULTS=0 turns them off; NAME=0 turns one off): ...`。対象変数が既に設定済みなら一覧から除かれ、既定値として追加されない。読み取り関数自体は有効・無効状態のログを出さない（`engine/src/core/arch_defaults.cpp:334-344`）。

## ログと測定値

ソースコメントには gfx1151 Windows での DFlash2 WMMA について 2.78x との記載があるが、条件一式や測定手順をこの変数の実装と結び付けて確認できる資料はないため、一般的な性能値としては扱わない（`engine/src/core/arch_defaults.cpp:202-204`）。Strata の `docs/DETAILS.md` に本変数の説明・測定値は見つからなかった。

## 根拠

- 値の読み取り、自動判定、GPU 判定: `engine/src/kernels/cuda/dflash2.cu:542-560`
- WMMA kernel の実行時コンパイル条件と対応 gfx: `engine/src/kernels/cuda/dflash2.cu:91-96`; `engine/include/strata/kernels/gfx_arch.hpp:28-32`
- attention kernel の選択と失敗経路: `engine/src/kernels/cuda/dflash2.cu:29-34, 1696-1724`
- アーキテクチャ別既定値の追加、ユーザー環境値の優先、ログ: `engine/src/core/arch_defaults.cpp:193-214, 218-223, 302-344`; `engine/include/strata/core/gfx11_extra.hpp:27-37, 87-114`
- HIP 起動時に既定値を適用する呼び出し: `engine/src/program/generate.cpp:4282-4315`
