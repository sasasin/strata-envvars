# `STRATA_TOPK_REG_MIN_BLOCKS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP 版の QSA ブロック top-k 選択で、active block 数がこの閾値より小さい場合に register top-k kernel を使わず reference kernel に切り替えるための閾値です。値は block 数で、セル数や token 数ではありません。`qsa_block_topk` 内で使われ、prompt の QSA selection のうち active count を渡す呼び出しで判定されます。active count を渡さない呼び出しでは閾値判定されません。CUDA 版ではこの変数を読みません。`engine/src/kernels/cuda/qsa_select.cu:3060-3076`, `engine/src/prefill/prefill.cpp:5390-5393,9456-9457`, `engine/src/core/layer.cpp:1277-1282`

## 値と判定

HIP コンパイル時に `qsa_block_topk` の初回実行で `std::getenv` を呼び、値が存在すれば `std::atoll` で `int64_t` に変換します。未設定は `7168`。空文字や数値として読めない先頭文字列は `atoll` の結果 `0` になります。数値の後ろに文字があっても数値の先頭部分を読み、空白や符号も `atoll` の規則で扱います。`0anything` は `0`、`-1` は `-1` です。全体の妥当性検査、範囲制限、clamp はありません。`engine/src/kernels/cuda/qsa_select.cu:3060-3067`

| 条件 | 未設定時 | 値の例と結果 |
| --- | --- | --- |
| HIP build | `7168` blocks | `4096`, `0`, `-1`, `12tail` はそれぞれ `4096`, `0`, `-1`, `12`。空文字、`true`、`0anything` は `0`。 |
| CUDA build | この変数は読まれない | 値は top-k dispatch に影響しません。CUDA 側には別の `kWideMinBlocks=4608` の分岐があります。 |

ただし HIP でも、この閾値比較が行われるのは `active_blocks > 0` のときだけです。`reach` は active count が `max_blocks` より小さければ active count、それ以外は `max_blocks` です。`counted && reach < kRegMinBlocks` の場合に reference kernel に進みます。閾値以下と等しい `reach` は `too_small` になりません。`engine/src/kernels/cuda/qsa_select.cu:3042-3069`

## 有効になる条件

- HIP backend の `qsa_block_topk` 経路で有効です。CUDA build は `__HIPCC__` でない側に入り、この変数を参照しません。`engine/src/kernels/cuda/qsa_select.cu:3044-3074`
- `active_blocks > 0` が必要です。active count を渡さない呼び出しでは `counted` が false となり、閾値は無視されて `reach=max_blocks` で dispatch します。`engine/src/kernels/cuda/qsa_select.cu:3044-3059`
- top-k の geometry と capacity がサポート条件を満たす必要があります。`s.idx_block != R` または `cap < qsa_selection_width(...)` の場合は `qsa_block_topk: unsupported geometry or cap` を stderr に出して `exit(1)` します。`engine/src/kernels/cuda/qsa_select.cu:3078-3080`
- Strata は `gfx1151` と discrete RDNA3（gfx1100/1101/1102）の既定値テーブルに `4096` を登録します。既に環境変数が設定済みなら空文字や `0` を含めその値を保持します。gfx1151 は `STRATA_GFX1151_DEFAULTS=0` でテーブルを止められ、discrete RDNA3 は `STRATA_GFX11_DEFAULTS=0` または `STRATA_DEFAULTS=026` で止まります。gfx1151 のテーブルには `STRATA_DEFAULTS=026` による除外条件はありません。`engine/src/core/arch_defaults.cpp:64-77,302-310`, `engine/include/strata/core/gfx11_extra.hpp:27-55`
- 表にない HIP GPU では、Strata の arch default による値の挿入は確認できず、カーネル内の未設定既定値 `7168` を使います。gfx12 の既定表は gfx1151 表から一部を選んでいますが、この変数を含めていません。`engine/src/core/arch_defaults.cpp:30-62,64-77`
- 対象変数に対応する CLI 引数や別環境変数による閾値の上書きは見つかりませんでした。上記 default table の無効化変数は「未設定時の自動挿入」にだけ影響します。

## 実行時の詳細

自動既定値は engine の `apply_arch_defaults` が GPU の arch を調べた後に、対象変数が未設定の場合だけ process environment に設定します。Linux では `setenv(..., overwrite=0)`、Windows では `_putenv_s` を使います。gfx1151 の値は arch default table、discrete RDNA3 の値は gfx11 exact table から設定されます。`engine/src/program/generate.cpp:4290-4320`, `engine/src/core/arch_defaults.cpp:218-224,302-323`, `engine/src/core/arch_defaults.cpp:64-77`, `engine/include/strata/core/gfx11_extra.hpp:41-55`

カーネル内の `static const int64_t kRegMinBlocks` initializer が環境値を一度だけ読み取るため、最初の `qsa_block_topk` 呼び出し後に同一プロセス内で環境値を変えても再評価されません。active count が閾値より小さいと reference kernel に切り替わり、それ以外は geometry に応じて register kernel または wide kernel を選びます。`engine/src/kernels/cuda/qsa_select.cu:3060-3105`

gfx1151 の既定値 `4096` は `reach=4096` から閾値判定を通過します。未設定のカーネル既定 `7168` では、`reach=4096` は reference kernel 側になります。0 以下の値では非負の `reach` が閾値未満にならないため、この閾値条件による reference fallback は発生しません。負値を含む値の clamp はありません。`engine/src/kernels/cuda/qsa_select.cu:3063-3076`

## ログと測定値

`apply_arch_defaults` が gfx1151 用の値を挿入した場合、stderr の `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` に設定したスイッチ名を列挙します。ユーザーが値を指定済みの場合はこの既定値設定リストには入りません。discrete RDNA3 では `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` に列挙されます。カーネルの閾値分岐自体に専用ログはありません。カーネル起動失敗時は `qsa_block_topk: <CUDA/HIP error string>` を stderr に出し `exit(1)` します。`engine/src/core/arch_defaults.cpp:318-332,397-404`, `engine/src/kernels/cuda/qsa_select.cu:3104-3105`

`docs/STRIX_HALO.md:114` は gfx1151 で `4096` により register kernel の開始位置が 16K cells になり、選択 cells は同一と記しています。ソースコード上も gfx1151 default `4096` と reference/register/wide dispatch は確認できますが、この調査では性能測定や parity test を実行していません。測定値を独立に確認したものとしては扱いません。`engine/src/core/arch_defaults.cpp:77`, `engine/src/kernels/cuda/qsa_select.cu:3063-3103`

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3016-3021,3042-3105` — QSA top-k dispatch、HIP/CUDA 条件、値の読み取り、比較、kernel 起動、失敗経路。
- `engine/src/prefill/prefill.cpp:5390-5393` — prompt 側から active block count 付きで呼び出す箇所。
- `engine/src/core/arch_defaults.cpp:28-77,218-224,302-323,397-404` — gfx1151 の既定値、環境値を保持する処理、既定値ログ。
- `engine/include/strata/core/gfx11_extra.hpp:27-55` — discrete RDNA3 の既定値条件と値。
- `engine/src/program/generate.cpp:4290-4320` — GPU arch 判定後の arch defaults 適用。
- `docs/STRIX_HALO.md:114` — gfx1151 の設定・測定資料との照合。
