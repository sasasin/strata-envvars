# `STRATA_MTP_Q8_SM60`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 共通の MTP drafter が持つ Q8_0 重みの一部を、CUDA の Pascal 向け Q8_0 GEMV が読む packed layout に登録する opt-in です。対象は drafter の 9 個の必須 dense projection と、draft vocabulary subset がある場合の draft head です。通常の GGUF Q8_0 layout で読む経路から、packed layout の `native_mmvq` 経路へ切り替わります。MTP の提案値はカーネルの加算順序の違いで丸めが異なり得ると実装コメントにありますが、target の返信は提案値に依存しないと同コメントは説明しています。`engine/src/core/mtp.cpp:106-115,486-509,996-1004`。

この変数だけでは pack は有効になりません。packer は別の `STRATA_Q8_SM60` も有効と判定した場合にだけ働きます。`STRATA_Q8_SM60` は値が厳密に `1` のとき有効で、CUDA kernel は HIP build では無効です。したがってこの MTP 変数単独、または HIP build では MTP 重みは通常の layout のままです。`engine/src/kernels/cuda/native_mmvq.cu:2623-2637,3044-3051,3111-3117`。

## 値と判定

`MtpDrafter::mtp_q8_sm60()` が `std::getenv` の結果を関数内 `static const bool` に一度だけ保存し、値が存在して先頭文字が `'1'` なら true とします。文字列全体は比較せず、数値変換もありません。unset、空文字、`0`、`true`、` 1` は false、`1`、`10`、`1anything` は true です。最初の呼び出し後に環境を書き換えてもこの判定は変わりません。`engine/src/core/mtp.cpp:109-115`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| MTP 側のフラグ判定 | false | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1` |
| packed layout の実際の作成 | MTP 側フラグが false なら作成しない | 上記に加えて `STRATA_Q8_SM60=1` の CUDA build が必要 | `STRATA_Q8_SM60` unset / 空 / `01` / `1 `、または HIP build では作成しない |

packer 側の `q8_sm60_on()` は `STRATA_Q8_SM60` を文字列全体 `"1"` と比較します。HIP build では常に false です。MTP フラグが true でもこの gate が false なら `pack` は false を返し、通常 layout を維持します。`engine/src/kernels/cuda/native_mmvq.cu:2625-2637,3044-3051,3111-3117`。

## 有効になる条件

- MTP layer を実際にロードすること。`--mtp` が空なら loader に達せず、`--spec` が 2 未満なら `--mtp` は無視されます。`engine/src/program/generate.cpp:8172-8193`。
- backend が CUDA kernel を含む build で、`STRATA_Q8_SM60=1` も設定されていること。HIP build では packer が常に false を返します。コードは GPU 世代を実行時に検査せず、Pascal / GP100 向けとするコメントに基づく opt-in です。`engine/src/kernels/cuda/native_mmvq.cu:2623-2637,3044-3051`。
- projection は `MtpDrafter::load()` が共有 weights を受け取らず (`shared == nullptr`)、`--mtp-q4 proj` または `all` で作る `dense4_` がないときだけ pack を試します。必須 9 tensor のうち `q8_0` で packer の形状条件 `n_in >= 128`、32 の倍数、`n_out > 0` を満たす行列が対象です。batch slot drafter は solo drafter の重みを共有するため、その slot の load では再 pack しません。`engine/src/core/mtp.cpp:345-378,486-509`; `engine/src/kernels/cuda/native_mmvq.cu:2991-2995`。
- draft head は vocabulary subset がロードされ、`STRATA_MTP_FULL_HEAD` が設定されておらず、head が Q8_0 (`type == 8`)、`--mtp-q4 head/all` が適用されていない場合に限り候補です。さらに MTP フラグ、row byte 条件、packer 成功が必要です。subset がなく full head を使う場合、この MTP 変数による draft-head pack はありません。`engine/src/core/mtp.cpp:939-1004`。
- `STRATA_Q8_SM60` は main output head の pack も制御しますが、それはこの変数の効果とは別です。NativeHead 側は Q8_0 head に対して独立に packer を呼びます。`engine/src/core/native_head.cpp:262-265`。
- `generate.cpp` の DFlash2 head 共有見積もりは `STRATA_MTP_Q8_SM60` の値ではなく設定有無を見ます。空文字や無効な値でも存在すれば `df2_expect_share` が false となり、head byte 見積もり上の共有を見込みません。これは MTP pack 判定とは別の相互作用です。`engine/src/program/generate.cpp:8337-8353`。

## 実行時の詳細

solo MTP load の `bind()` で、必須 projection の確認後に pack を試し、成功数と追加 VRAM byte 数を集計します。packer は Q8_0 の packed eligibility（SM60 有効時は `n_in >= 128`、`n_in % 32 == 0`、`n_out > 0`）を検査してから、別の packed buffer を作って registry に登録します。成功した projection が 1 個以上あれば `strata mtp: %d of %zu projections on the Pascal Q8_0 GEMV (STRATA_MTP_Q8_SM60=1, %.1f MiB more VRAM)` を stderr に出します。失敗または対象なしならこの MTP 集計行は出ません。pack 自体の失敗時には VRAM 不足や packing failure の警告が出て、GGUF layout を保ちます。`engine/src/core/mtp.cpp:486-509`; `engine/src/kernels/cuda/native_mmvq.cu:2991-2995,3044-3075`。

draft head subset は同じ bind 中に別途処理されます。形状・alignment に応じて同じ大きさの allocation 内へ in-place pack するか、通常 packer の別 buffer に fallback します。成功時は `dhead_plain_` を false にし、stderr に `strata mtp: the draft head on the Pascal Q8_0 GEMV (STRATA_MTP_Q8_SM60=1)` を出します。失敗時は通常 layout のままです。`engine/src/core/mtp.cpp:996-1004`; `engine/src/kernels/cuda/native_mmvq.cu:3111-3141`。

判定値は最初の `mtp_q8_sm60()` 呼び出し時に static cache されます。projection pack は `load()` 中、draft-head subset pack は `bind()` 中に実行され、その後の `record_rest()` が Q/O projection と shared-expert projection を `native_mmvq` へ渡し、draft-head row も `native_mmvq` から読みます。registry に packed 重みとして登録済みで、kernel 条件を満たす場合は packed path が使われ、decline した形状は通常の経路に fallback します。`engine/src/core/mtp.cpp:109-115,486-509,996-1004,1309-1354`; `engine/src/kernels/cuda/native_mmvq.cu:2767-2801,3699-3704`。

## ログと測定値

この変数に関して MTP 側が出す成功ログは、projection pack が 1 個以上成功したときの集計行と、draft head subset pack 成功時の行です（上記参照）。packer は作成失敗時に `strata q8 sm60: no VRAM for the packed %s (%.0f MiB); it keeps the GGUF layout`、`strata q8 sm60: packing the %s failed; it keeps the GGUF layout` などを stderr に出します。`STRATA_Q8_SM60=1` が kernel 側で初めて評価された際には `strata q8 sm60: Q8_0 decode GEMVs on the Pascal kernel (STRATA_Q8_SM60=1)` も出ます。`engine/src/kernels/cuda/native_mmvq.cu:2629-2634,3055-3068`。

設定一覧は `STRATA_MTP_Q8_SM60` を「NVIDIA and AMD」と記載していますが、当該 MTP packing 関数が呼ぶ packer は `__HIPCC__` build で false を返すため、この機能の実装条件とは一致しません。release notes は GP100 向け opt-in と記載します。Strata の資料には本変数の性能測定値はありません。`docs/SETTINGS.md:180`; `docs/release-notes-0.2.7.md:53`; `engine/src/kernels/cuda/native_mmvq.cu:3044-3051,3111-3117`。

## 根拠

- `engine/src/core/mtp.cpp:106-115` — MTP フラグの読取・先頭文字判定・static cache。
- `engine/src/core/mtp.cpp:345-378,486-509` — load 経路、共有重み・Q4 優先、projection pack とログ。
- `engine/src/core/mtp.cpp:908-1004,1309-1354` — subset head 条件・pack と packed projection の利用箇所。
- `engine/src/kernels/cuda/native_mmvq.cu:2623-2637,2991-2995,3044-3075,3111-3141,3699-3704` — backend gate、形状、pack / fallback / GEMV。
- `engine/src/core/native_head.cpp:262-265` — main head の別個の `STRATA_Q8_SM60` 処理。
- `engine/src/program/generate.cpp:8172-8193,8337-8353` — MTP 起動条件と DFlash2 共有見積もり。
- `docs/SETTINGS.md:180`; `docs/release-notes-0.2.7.md:53` — 文書記載との照合。
