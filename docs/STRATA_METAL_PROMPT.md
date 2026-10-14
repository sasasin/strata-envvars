# `STRATA_METAL_PROMPT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal backend の prompt 処理経路を選びます。値が文字列 `window` と完全一致すると、prompt kernels を使う高速経路を選ばず、prompt を decode window で読みます。Strata の `docs/MAC.md` はこれを遅い exact fallback（約 190 tok/s）として説明しています。CUDA/HIP/SYCL の prompt 経路にはこの変数の読み取りはありません。

## 値と判定

| `STRATA_METAL_PROMPT` | `windows` 判定 | 動作 |
|---|---:|---|
| 未設定 | false | 通常の Metal prompt 経路を使う。prompt 長や streaming 状態により prompt kernels、prompt GEMM、または decode window に分岐する。 |
| `window` | true | 長さや streaming 状態によらず decode window 経路を使う。 |
| 空文字、`WINDOW`、`1`、`0`、その他の文字列 | false | 未設定と同じ経路選択。 |

値は数値変換されず、文字列全体を大文字小文字を区別して `window` と比較します。環境変数の判定は `prompt_run_rows()` 内の `static const bool` に保存されるため、プロセス内の初回判定後に環境を書き換えても反映されません。根拠: `metal/src/engine/window.cpp:2555-2559`。

## 有効になる条件

- `Prefill::run()` が `STRATA_GPU_METAL` ビルドで Metal engine の `prompt_run()` を呼ぶ経路に限られます（`src/prefill/prefill.cpp:4338-4348`）。
- `STRATA_METAL_PROMPT=window` なら、resident/streaming の別を問わず decode window fallback に進みます。
- 変数が未設定または `window` 以外でも、resident model では prompt 長が `STRATA_METAL_PROMPT_MIN`（既定 32 rows）以上の場合に prompt kernels を使います。これ未満なら decode window に進みます。`STRATA_METAL_PROMPT_MIN` は初回判定時に `atoll()` で読みます。根拠: `metal/src/engine/window.cpp:2558-2560`。
- streaming model では、`STRATA_METAL_PROMPT` が `window` 以外のとき `STRATA_METAL_PROMPT_GEMM` と `STRATA_METAL_PROMPT_GEMM_MIN` による別判定を行います。既定では prompt GEMM が有効で、長さの既定下限は 64 rows です。GEMM しない場合は decode window に進みます。したがって `STRATA_METAL_PROMPT` はこの streaming 用 GEMM 判定より優先されます。根拠: `metal/src/engine/window.cpp:2560-2579`。

## 実行時の詳細

decode window 経路は最大 `MAXT`（8）rows ずつ token を `int32_t` に変換し、`Window::run()` と `Window::commit()` を呼びます。各 chunk の後に `on_chunk` callback があれば実行します。window がまだ用意されていない場合は `metal prompt: the decode window is not up yet` を返し、run/commit または callback が失敗した場合も prompt 処理は失敗します。根拠: `metal/src/engine/window.cpp:52,2555-2557,2580-2587`。

通常の resident prompt kernel 経路では `Window::prompt()` が呼ばれ、chunk ごとに prompt chain を実行します。streaming の prompt GEMM 経路は `prompt_region(true/false)` で region を囲み、chunk ごとに GEMM prompt を実行します。いずれも `STRATA_METAL_PROMPT=window` では選択されません。根拠: `metal/src/engine/window.cpp:2560-2577`, `metal/src/engine/prompt_chain.inc:394-420`。

この変数専用の有効化ログはありません。decode window 経路でエラーになった場合は上記の prompt error が返ります。prompt kernel 経路では `STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されている場合に prompt tokens、時間、tok/s の診断が stderr に出ます（`metal/src/engine/prompt_chain.inc:416-419`）。

## 文書との照合

`docs/MAC.md:183-194` は `STRATA_METAL_PROMPT=window` を decode window 経由の遅い exact fallback とし、約 190 tok/s と記載しています。同じ文書の `:165` では fast prompt path と decode window の比較として mean KL 0.0004、top-1 agreement 99.4–99.6% を挙げています。ソースは `window` の完全一致で fallback に切り替えることを確認できます。性能・品質値は文書記載の測定値であり、この調査で再測定したものではありません。

## 根拠

- Metal backend の呼び出し条件: `src/prefill/prefill.cpp:103-110,4338-4348`
- 値の判定、static cache、resident/streaming 分岐: `metal/src/engine/window.cpp:2555-2587`
- Decode window の chunk 処理: `metal/src/engine/window.cpp:52,2580-2587`
- Prompt kernel の chunk 処理と診断ログ: `metal/src/engine/prompt_chain.inc:394-420`
- 設定説明と測定値: `docs/MAC.md:165,183-194`
