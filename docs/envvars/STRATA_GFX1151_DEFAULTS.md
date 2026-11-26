# `STRATA_GFX1151_DEFAULTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

gfx1151（Strix Halo）向けに Strata が自動設定する最適化スイッチ群を抑止するための環境変数。実装上は値全体を Boolean として解釈せず、「設定されていて先頭文字が `0` か」を各読み取り箇所で調べる。該当すると gfx1151 の既定値表、Windows の一部追加既定値、および Windows gfx1151 の prefill 設定変更を抑止する。ユーザーが個別に設定したスイッチを消したり上書きしたりはしない。`engine/src/core/arch_defaults.cpp:64-106,240-246,293-300`、`engine/src/program/generate.cpp:4374-4405`。

HIP ビルドの `strata-engine` が GPU 0 の情報を取得した後、エンジンが各スイッチを初回参照する前に `apply_arch_defaults` を実行する。そこで gfx1151 用の既定値を設定し、後続の生成処理でも同じ変数を参照する。CUDA 等の非 HIP ビルドからこの初期化経路は呼ばれない（`engine/src/program/generate.cpp:4287-4320`）。

gfx1151 の通常の既定値表は、prompt 系の `STRATA_GDN_HEAD=1`、`STRATA_GDN_PP=2`、`STRATA_GDN_CONVL2=1`、`STRATA_GDN_NOY=1`、`STRATA_CVEC_FUSE=1`、`STRATA_HCD_EXACT=1`、`STRATA_PF_PAD=1`、`STRATA_TOPK_REG_MIN_BLOCKS=4096` と、decode 系の `STRATA_Q8_PACKED=1`、`STRATA_Q6_PACKED=1`、`STRATA_MMVF_ROWS=1`、`STRATA_ATTN_LANECELL=1`、`STRATA_EXPERT_V2=1`、`STRATA_TSUM=1`、`STRATA_LFUSE=1`、`STRATA_GDN_SPLIT=1`、`STRATA_QFUSE=1`、`STRATA_PLE_BATCH=1`、`STRATA_SH_STREAM=1`。Windows では `STRATA_SH_STREAM` を表から外し、代わりに `STRATA_SMALL_UNR=3` と `STRATA_GR_Q8_PFS=1` を加える。これらの個別スイッチが実際にどのカーネル経路で効くかは各スイッチの実装条件による（`engine/src/core/arch_defaults.cpp:67-105`）。

## 値と判定

各箇所とも `std::getenv` の結果を `nullptr` と比較し、非 null の場合は `v[0] == '0'` を確認する。文字列全体の数値変換・真偽値 parse はない。大文字小文字や後続文字は判定に影響しない（`engine/src/core/arch_defaults.cpp:65-66,243-245,296-298`、`engine/src/program/generate.cpp:4374-4405`、`engine/src/prefill/moe_fused_iq.cu:3030-3047,3118-3133,3162-3165`）。

| 条件 | unset | 先頭が `0` の値 | その他の設定値 |
|---|---|---|---|
| gfx1151 の HIP 既定値表 | 表を適用 | 表を空にする | 表を適用 |
| Windows gfx1151、batch slots 2 以上の並列既定値と verify 非同期 launch | 条件を満たせば適用 | 適用しない | 条件を満たせば適用 |
| Windows gfx1151、fused Q50 等の個別経路 | その経路ごとの既定判定 | 既定の有効化を抑止 | その経路ごとの既定判定 |
| Windows gfx1151 の bare `--prefill auto` と prefill borrow 設定 | Strata の gfx1151 用調整を適用 | その調整を抑止 | Strata の gfx1151 用調整を適用 |

例として、unset は既定値を有効にする側、空文字は「設定あり」だが先頭が `0` ではないため同じく有効側、`0` と `0anything` は抑止側、`1`・`true`・`false`・` 0` は先頭文字が `0` でないため有効側である。数値範囲や負値の検査はない。`arch_default_env` が選んだ個別スイッチは `getenv` が null の場合だけ設定されるので、たとえば個別スイッチを空文字や `0` に設定してもその値が保持され、自動設定で上書きされない（`engine/src/core/arch_defaults.cpp:307-310`）。

## 有効になる条件

- 既定値表は HIP の `strata-engine` 初期化経路で GPU 0 が gfx1151 と判定された場合に対象となる。gfx12 は別の `STRATA_GFX12_DEFAULTS` 分岐、その他の GPU アーキテクチャは空の表を使う（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:28-66`）。
- Windows gfx1151 の並列既定値は `batch_slots >= 2` の場合だけ対象で、verify graph の helper-thread launch は Windows gfx1151 の場合だけ対象。どちらも先頭 `0` で止められる（`engine/src/core/arch_defaults.cpp:240-246,293-300`）。
- Windows gfx1151 の prefill 調整は、GPU 0 が integrated で、可視 GPU がすべて integrated かつ同一アーキテクチャであることを前提とする。bare `--prefill auto` の cap/chunk 調整には `o.prefill_auto_bare` と `o.prefill_auto_cap > 0` も必要（`engine/src/program/generate.cpp:4291-4302,4379-4389`）。
- prefill borrow を抑止して own buffers を使う設定は、同じ Windows gfx1151 / 全 GPU integrated 条件で、`STRATA_PREFILL_BORROW` の先頭が `1` でない場合に適用される。`STRATA_GFX1151_DEFAULTS=0` はこの自動変更を抑止する（`engine/src/program/generate.cpp:4392-4405`）。
- `STRATA_PF_FUSED_Q50` が空でなく設定されていれば、その先頭文字の判定が優先され、この変数による既定判定に進まない。未設定または空の場合、Windows HIP gfx1151 では先頭 `0` が既定 ON を抑止し、Linux gfx1151 は既定 OFF。ほかの対象アーキテクチャには `STRATA_GFX11_DEFAULTS` または gfx12 の規則がある（`engine/src/prefill/moe_fused_iq.cu:3118-3133`）。
- K-quant fused prefill の既定有効化は HIP Windows gfx1151 に限られ、`STRATA_PF_FUSED_KQ` が空でなく設定されていればその先頭文字で明示判定される。先頭 `0` は明示 OFF、他の先頭文字は明示 ON であり、この変数の判定は空／未設定の場合だけ行う（`engine/src/prefill/moe_fused_iq.cu:3030-3048`）。
- trellis fused 経路は `STRATA_PF_FUSED_TQ` が `1` であること等が別途必要。gfx1151 では `STRATA_PF_TQ_G1151` が未設定・空なら Windows 既定が使われ、明示値があればそちらが優先するため、明示 `1` はこの既定抑止を上書きする。`STRATA_GFX1151_DEFAULTS` だけで fused trellis 経路自体を有効化はしない（`engine/src/prefill/moe_fused_iq.cu:3151-3187`、`engine/include/strata/prefill/fused_tq_hip.hpp:21-37`）。

この変数は Windows gfx1151 の matrix-core prompt defaults（例: `STRATA_PF_GEMM`、`STRATA_PF_FUSED`）を一括で止める条件には使われていない。これらは `igpu_default_env` 側で別に設定される（`engine/src/core/arch_defaults.cpp:178-215,406-432`）。また、gfx1151 以外の一般的な個別スイッチや、ユーザーが明示した gfx1151 の表内スイッチを強制 OFF にするものではない。

## 実行時の詳細

起動引数を解析した後、HIP 初期化中に GPU 0 のプロパティと可視 GPU 構成を調べ、`apply_arch_defaults` を呼び出す。この段階で標準の gfx1151 表を調べ、環境にまだ存在しない項目だけを `_putenv_s`（Windows）または `setenv(..., 0)`（POSIX）で設定する。したがって既存の個別環境変数が優先される。これはリクエストごとの設定ではなく、エンジン初期化時のプロセス環境への既定値設定である（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:302-310,218-224`）。

並列・非同期 launch 既定値も同じ初期化中に個別に処理される。チャンク、bare `--prefill auto`、borrow の判定は GPU 条件が分かった直後に引数構造体を調整する。これらの分岐に CLI 引数と直接競合する場合、bare `--prefill auto` であることがチャンク変更の条件で、`STRATA_GFX1151_CHUNK` の先頭 `0` は両チャンク調整を抑止する。borrow では `STRATA_PREFILL_BORROW` の先頭 `1` が自動 own-buffer 設定を抑止する（`engine/src/program/generate.cpp:4371-4405`）。

`STRATA_PF_FUSED_KQ`、`STRATA_PF_FUSED_Q50`、trellis 判定はそれぞれ実装関数内で読み取る。`kq_on` の結果、Q50 用 `STRATA_PF_FUSED_Q50` の parse 結果、trellis の defaults-off 判定は function-local `static` に cache され、初回判定後の対応する環境値変更は反映されない。Q50 経路が条件付きで読む `STRATA_GFX1151_DEFAULTS` 自体はその呼出しごとに確認される。対して arch defaults と `generate.cpp` の gfx1151 条件は初期化時に読み、その場で処理する（`engine/src/prefill/moe_fused_iq.cu:3030-3048,3118-3133,3162-3165`）。

## ログと測定値

標準表から少なくとも一つの未設定スイッチを設定した場合、stderr に `strata: gfx1151 (Strix Halo): N exact speed switches on by default (STRATA_GFX1151_DEFAULTS=0 turns them off; a switch you set is kept): ...` の形式で適用数とスイッチ名を出す。Windows gfx1151 の並列スイッチや verify graph launch が追加設定された場合は、それぞれ `strata: gfx1151 (Strix Halo): the exact parallel-request switches are on for N batch slots ...`、`strata: gfx1151 (Strix Halo): the verify window's graph is launched from a helper thread ...` の行も出る。先頭 `0` または全スイッチが個別設定済みで追加がない場合、対応する行は出ない（`engine/src/core/arch_defaults.cpp:397-405,433-452`）。

コードと `docs/STRIX_HALO.md` は、標準表の個別スイッチが測定環境で同一出力だったとの記録を含むが、この文書ではそれを一般的な性能・正確性保証として扱わない。`STRATA_GFX1151_DEFAULTS` 自体について、ここで新たな測定はしていない。

## 根拠

- `engine/src/core/arch_defaults.cpp:28-106` — アーキテクチャ別のgfx1151既定値表と Windows 差分。
- `engine/src/core/arch_defaults.cpp:240-246,293-300,302-310,397-452` — Windows 追加既定値、個別値の保持、設定ログ。
- `engine/src/program/generate.cpp:4287-4320,4371-4405` — HIP 初期化順序、GPU 条件、prefill のチャンク／borrow 処理。
- `engine/src/prefill/moe_fused_iq.cu:3030-3048,3118-3133,3151-3187` — KQ、Q50、trellis 経路の読み取りと優先順位。
- `engine/include/strata/prefill/fused_tq_hip.hpp:21-37` — trellis の明示値と defaults-off の優先関係。
- `docs/STRIX_HALO.md:102-114`、`docs/STRIX_HALO_WINDOWS.md:62-75` — Strix Halo 向け既定値の資料記載。
