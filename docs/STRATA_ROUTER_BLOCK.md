# `STRATA_ROUTER_BLOCK`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

gfx906 向け HIP 互換ビルドの MoE router (`router_top10`) で、expert 数が 512 以下のときに既定で使う wavefront kernel を迂回させ、汎用の block kernel を選びます。名前に `BLOCK` を含みますが、値の内容を解釈する設定ではなく、環境変数が存在するかどうかで切り替えます。

## 値と判定

| 状態 | gfx906 ビルドでの結果 |
|---|---|
| 未設定 | `n_expert <= 512` なら wavefront kernel を選択 |
| 設定あり | wavefront kernel の条件を満たしても選ばず、汎用 block kernel へ進む |

`std::getenv("STRATA_ROUTER_BLOCK")` の null 判定だけを使います。空文字、`0`、`false` を含む、どの文字列でも設定されていれば同じ結果です。数値変換、文字列比較、値域チェックはありません。判定は `router_top10()` を呼ぶたびに行われ、static cache されません。

## 有効になる条件

- `STRATA_HIP_GFX906` を有効にした gfx906 HIP 互換ビルドでのみ、この環境変数を読む分岐がコンパイルされます。CUDA の通常ビルドと wave32 HIP ビルドでは、この分岐による効果はありません。
- 通常の `router_top10()` 経路であることが必要です。`n_tokens <= 0` や `n_expert <= 0` などで関数が早期 return する場合、また別実装の router が呼ばれる場合は切り替えません。
- `STRATA_HIP_ROUTER_FAST` が設定され、`n_tokens > 0`、`64 < n_expert <= 512`、`0 < k <= 32` を満たす場合は、先に fast kernel が起動して return するため、この変数の分岐には到達しません。gfx906 では `STRATA_HIP_ROUTER_FAST` の有無を初回に static cache します。
- `n_expert > 512` では wavefront kernel の上限を超えるため、`STRATA_ROUTER_BLOCK` の有無に関係なく汎用 kernel になります。
- 呼び出し元には別 router を使う場合があります。たとえば `src/core/layer.cpp` は native router が有効で 512 experts・top-10 の場合に native router を使い、`src/prefill/kernels.cu` の `route()` は 512 または 256 experts を専用 kernel に直接送ります。その呼び出しでは本変数は router 選択に関与しません。

## 実行時の詳細

通常の gfx906 経路では、`n_expert <= 64 * RW_PER`（`RW_PER` は 8）かつ変数が未設定の場合に、1 token あたり64 threadの `router_top10_wave_kernel` を起動して関数を終了します。この kernel は wave64 内の argmax と register 上の確率値を使います。変数が設定されている場合、その早期分岐を通らず、`router_top10_kernel` を起動します。汎用側は `min(n_expert, RT_MAX_THREADS)` を32の倍数に切り上げた thread 数と、selection mask・double 配列・float 配列用の shared memory を指定します。

この環境変数を選ぶこと自体によるログ出力はありません。kernel 起動に失敗した場合は既存の `router_top10 launch: ...` エラー経路、stream が null の場合の同期失敗は `router_top10: ...` 経路に進みます。ソースコメントは wavefront kernel の routing 結果が汎用 kernel と bit-identical であるとしていますが、`STRATA_ROUTER_BLOCK` 自体の性能値は確認できる資料に記載されていません。

## 根拠

- `CMakeLists.txt:64-71,125-141` — gfx906 HIP 互換ビルドのオプションと compile definition。
- `src/kernels/cuda/router_top10.cu:190-264` — gfx906 wavefront kernel、`RW_PER=8`、汎用 kernel と同一結果である旨の実装コメント。
- `src/kernels/cuda/router_top10.cu:422-495` — router 選択、`STRATA_HIP_ROUTER_FAST` との優先関係、`STRATA_ROUTER_BLOCK` の存在判定、汎用 kernel の起動・エラー処理。
- `src/core/layer.cpp:370-375` — native router を選ぶ呼び出し条件。
- `src/prefill/kernels.cu:2005-2012` — 512/256 experts の専用 route kernel と汎用 `router_top10` の振り分け。
- `docs/AMD_HIP.md:496-507` — gfx906 ビルドと router の wavefront 既定動作の説明。`STRATA_ROUTER_BLOCK` の値別の説明や個別測定値はありません。
