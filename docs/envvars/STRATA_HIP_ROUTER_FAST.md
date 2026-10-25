# `STRATA_HIP_ROUTER_FAST`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

gfx906 向け HIP 互換ビルドの MoE router で、既定の portable / wave64 kernel に代えて S6 fast kernel を選ぶ opt-in スイッチです。対象の router は logits から expert の top-k ID と重みを計算します。通常の wave32 HIP ビルドでは、この変数ではなく別の `STRATA_HIP_ROUTER_OLD` が fast kernel の切り替えに使われます。

## 値と判定

| gfx906 HIP 互換ビルドでの値 | 判定と動作 |
|---|---|
| 未設定 | `old=true`。fast kernel を選ばず、通常の gfx906 経路へ進む。 |
| 設定あり | 値の内容を読まず `old=false`。fast kernel の入力条件も満たせば S6 kernel を選ぶ。 |

判定は `getenv(...) == nullptr` だけです。したがって `1` に限らず、`0`、空文字、その他どんな文字列でも、設定されていれば同じ扱いです。数値変換や文字列比較はありません。関数内 `static const` の初期化時に一度だけ読み取るため、実行中に環境を書き換えても判定は変わりません。

## 有効になる条件

このスイッチの分岐は HIP コンパイル時（`__HIPCC__`）かつ `STRATA_HIP_GFX906` ビルド時にあります。CMake では `STRATA_HIP_GFX906` が gfx906 向け HIP 互換レイヤーを有効にし、HIP アーキテクチャを別途指定しなければ `gfx906` に設定します。

設定済みであっても fast kernel を起動するのは `n_tokens > 0`、`65 <= n_expert <= 512`、`1 <= k <= 32` の場合だけです。条件外では通常経路へフォールバックします。`n_tokens <= 0`、`n_expert <= 0`、`k <= 0` は通常経路で何もせず戻り、通常経路の上限 `k > 64` または `n_expert > RT_MAX_THREADS * 64` は stderr にエラーを出して終了します。

## 実行時の詳細

`router_top10()` が呼ばれた際、gfx906 HIP 互換ビルドでは環境変数の有無を static cache し、設定されていて上記の入力条件を満たすと `launch_generic(..., mode=1)` で `router_top10_fast_kernel<false>` を起動します。kernel 起動に失敗すると `router_top10 launch: <CUDA/HIP runtime error>` を stderr に出して `exit(1)` します。stream が null の場合は device 同期も行い、失敗時は `router_top10: <runtime error>` を stderr に出して終了します。

fast 条件を満たさない場合、gfx906 の `n_expert <= 64 * RW_PER`（`RW_PER` は 8）かつ `STRATA_ROUTER_BLOCK` が未設定なら、既定の one-wavefront / wave64 kernel が選ばれます。それ以外は portable block kernel です。通常の HIP wave32 ビルドでは `STRATA_HIP_ROUTER_FAST` の参照箇所は gfx906 分岐の外にあるため、この変数は効かず、別変数 `STRATA_HIP_ROUTER_OLD` が unset なら fast kernel が選ばれます。

router API は MoE 層の通常経路および multi-token routing から呼ばれます（例: `src/core/layer.cpp:376,418`、`src/core/mtp.cpp:1112-1113`）。ただし canonical 512-expert / top-10 の一部経路は native router を使うため、generic `router_top10()` を通らず、この変数の影響を受けません。

## 文書との照合

`docs/AMD_HIP.md` は通常の HIP (`gfx1100` / `gfx1201`) では fast router が既定で、`STRATA_HIP_ROUTER_OLD=1` が portable kernel に戻すと説明しています。これは gfx906 互換ビルドの上記 opt-in 分岐とは別の条件です。同資料には gfx906 で `STRATA_HIP_ROUTER_FAST` を使った測定値は見当たらず、gfx906 での性能効果はここでは断定しません。

## 根拠

- `CMakeLists.txt:64-71,128-144` — gfx906 HIP 互換ビルドの選択、compile definition、既定 HIP architecture。
- `src/kernels/cuda/router_top10.cu:266-283` — fast kernel の用途と説明。ソースコメントでは portable kernel と同じ ID / weight になるとし、通常 HIP 用の旧経路切り替えも記載。
- `src/kernels/cuda/router_top10.cu:422-449` — gfx906 における環境変数判定、入力条件、fast kernel 呼び出しとエラー処理。
- `src/kernels/cuda/router_top10.cu:451-495` — 通常経路の入力検査、gfx906 wave64 kernel と portable kernel の選択、同期・エラー処理。
- `sycl/src/kernels/cuda/router_top10.dp.cpp:679-712` — 同名の移植版にも同じ HIP / gfx906 条件付き分岐。
- `src/core/layer.cpp:371-376,393-419`、`src/core/mtp.cpp:1104-1114` — MoE routing から router への呼び出しと native router 経路。
- `docs/AMD_HIP.md:330-336` — 通常 HIP での fast router の説明と `STRATA_HIP_ROUTER_OLD`。
