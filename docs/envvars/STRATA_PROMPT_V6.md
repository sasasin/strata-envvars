# `STRATA_PROMPT_V6`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal の長い prompt 処理に使う MoE expert カーネルを、ragged tile 対応の V6 (`mm_scan6` / `mm_gu6` / `mm_down6`) に切り替え、1 expert の複数の 16 行 subtile で重みの decode を共有します。値は subtile のグループ数 `MS` として使われ、既定は 4、2 以上で有効です。これは Metal prompt chain 内だけの設定で、decode window の通常実行や CUDA/HIP/SYCL の処理には適用されません。V6 が使えない場合、同じ prompt chain 内で V3 または V2 の経路が選ばれます。

この設定を読むのは `metal/src/engine/prompt_chain.inc` の `Window::pc_setup()` です。そこに到達するのは、Metal の `prompt_run_rows()` が window 経由ではない通常の prompt chain を選んだ場合です。Metal エンジンは macOS 向けです (`setup.py:8233-8237`)。

## 値と判定

`pc_setup()` が V3 expert 経路に入った場合に環境変数を読み、`std::atoi` で整数化します。文字列全体の検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | `MS=4`。型条件も満たせば V6 を有効化 |
| 空文字 | `atoi("")` は 0 となり無効 |
| 数値の先頭部分が 0、1、負数 | `MS < 2` なので無効 |
| 数値の先頭部分が 2 または 3 | それぞれ `MS=2` または `MS=3` として有効化 |
| 4 以上 | 有効化し、`MS` は `min(値, 4)` で 4 に制限 |
| 数字で始まらない文字列 | `atoi` の結果 0 となり無効 |
| 数字の後ろに文字がある文字列 | 数字部分だけを使う。例: `2abc` は `MS=2`、`4foo` は `MS=4` |

`atoi` のため、先頭の空白や符号は整数変換の規則に従い、空白除去や文字列比較による検証はありません。整数に変換できない値を警告する処理もありません。値の読み取りと `MS` の判定は `metal/src/engine/prompt_chain.inc:73-89` にあります。

## 有効になる条件

環境変数の判定だけでは V6 は有効になりません。次の条件を満たす必要があります。

- `prompt_run_rows()` が prompt chain を選ぶこと。`STRATA_METAL_PROMPT=window` ならこの経路を使わず、非 streaming でも `Window::run()` の窓ごとの処理に進みます。通常の非 streaming 経路では prompt 長が `STRATA_METAL_PROMPT_MIN` 以上である必要があり、その既定値は 32 行です。streaming 経路は別の prompt GEMM / chunk 経路へ進みます (`metal/src/engine/window.cpp:3593-3625`)。
- `pc_setup()` の V3 expert 条件 `b.v3e` が真であること。これは `COOP_K4` の実行時 layout probe が成功し、block 0 の gate expert tensor type が 144 未満の場合です。満たさないと `STRATA_PROMPT_V6` の値は V6 選択に使われず、V2 expert 経路です (`metal/src/engine/prompt_chain.inc:26-47,53-62,71-84,449-476`)。
- 48 層すべての gate/up expert type が `Q4_K`, `Q5_K`, `Q6_K`, `Q8_0`, `IQ3_XXS`, `IQ2_S`, `IQ4_XS`, `IQ3_S`, `IQ2_XS`, `IQ2_XXS` のいずれかで、down expert type が `Q5_1`, `Q8_0`, `Q5_0`, `IQ4_NL`, `Q2_0` のいずれかであること (`metal/src/engine/prompt_chain.inc:73-84`)。
- 上記の条件下で変換された `MS` が 2 以上であること。そうでなければ V6 は使わず、V3 expert kernel が使われます (`metal/src/engine/prompt_chain.inc:84-89,449-476`)。

`STRATA_PROMPT_GU` と `STRATA_PROMPT_DN` が設定されていると、各値は V6 用 kernel 名の tile 形状にも影響します。V6 有効化時は gate/up と down の tile height を 16 にしますが、それぞれの環境変数が未設定のときに限って残りの tile 形状を V6 用既定値に変更します。設定値が存在する場合（空文字を含む）は `sscanf` の結果が保持され、V6 用既定形状への変更は行われません (`metal/src/engine/prompt_chain.inc:65-70,85-91`)。

`MS=2` または `MS=3` は値として受理されますが、Metal kernel の実体化済み variant は型と tile 形状に限りがあります。既定の V6 tile 形状に対しては、`metal/kernels/moe_mm.metal:1392-1404` の実体化一覧に MS 2/3 の組み合わせがなく、該当 kernel 名の解決に失敗し得ます。tile override を使った場合も、選んだ型・形状・MS の組み合わせが実体化一覧にないと同様です。V6 の条件判定自体は variant の存在までは検査しません。

## 実行時の詳細

`Window::prompt()` から `pc_setup()` が呼ばれ、48 層の expert 型を確認したうえで `STRATA_PROMPT_V6` を読みます。値を `static` 保存する実装ではありません。`PromptBufs` が既に要求サイズ以上なら `pc_setup()` は直ちに戻るため値を再読込しません。より大きな prompt chunk 用に buffer を再確保する場合は設定を再評価します (`metal/src/engine/prompt_chain.inc:49-60,73-89`; 呼び出し元は `:564-570`)。

有効時は V6 の scan と expert gate/up・down kernel 名を選び、plan に `MS` を渡します。kernel 実装では gate/up と down の重みをロード・decode した後、最大 `MS` 個の 16 行 subtile を計算します (`metal/src/engine/prompt_chain.inc:421-432,447-476`; `metal/kernels/moe_mm.metal:1246-1317,1338-1389`)。V6 が無効なら scan は `mm_scan`、expert kernel は V3 の `mm_gu3` / `mm_down3` に戻ります。`b.v3e` 自体が偽なら V2 kernel を使います。

成功時の標準 stderr ログは `strata metal: prompt kernels ... ready ...` ですが、V6 の有効状態や `MS` はこのログに出ません (`metal/src/engine/prompt_chain.inc:136-139`)。要求された kernel function が見つからない場合、Metal runtime は `mtl: no function <名前> ...` を stderr に出して終了コード 3 で終了します。pipeline 作成に失敗した場合も `mtl: pipeline <名前>: ...` を出して終了コード 3 です (`metal/src/mtl_rt.mm:486-521`)。したがって、parse できる `MS=2/3` でも variant が無ければ V3 に自動 fallback する動作ではありません。

## 根拠

- 変数の読み取り、`atoi`、既定値 4、上限 4、`MS >= 2` の分岐、対応型条件、tile override: `metal/src/engine/prompt_chain.inc:49-91`。
- `PromptBufs` の保持状態と `b.v3e` / `b.v6` の定義: `metal/src/engine/window.cpp:169-183`。
- V6 の scan / gate-up / down 選択と plan の `MS`: `metal/src/engine/prompt_chain.inc:421-432,447-476`。
- V6 kernel の subtile 計算と実体化済み variant 一覧: `metal/kernels/moe_mm.metal:1246-1317,1338-1404`。
- prompt chain の経路条件と `Window::prompt()` 呼び出し: `metal/src/engine/window.cpp:3593-3625`; chunk setup 呼び出し: `metal/src/engine/prompt_chain.inc:564-570`。
- 不明 kernel / pipeline のログと終了経路: `metal/src/mtl_rt.mm:486-521`。
- Metal engine の macOS セットアップ経路: `setup.py:8233-8237`。
