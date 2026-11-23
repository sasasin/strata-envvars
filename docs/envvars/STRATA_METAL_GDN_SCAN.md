# `STRATA_METAL_GDN_SCAN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal エンジンの prompt GDN scan に使う kernel 名を固定し、機種・prompt 長に応じた自動選択を上書きする診断・比較用の変数です。選択肢は `gdn_scanr_4`、`gdn_scanr_4_8`、`gdn_scanr_4_4`、`gdn_scanr_4_2` です。selector は `engine/metal/src/engine/window.cpp` の `gdn_scan_name` にあり、選んだ名前は prompt 用の GDN scan dispatch の pipeline 名として使われます。通常の decode window が呼ぶ `gdn_step` はこの selector を通らないため、この変数は decode の GDN kernel 選択を変更しません（`engine/metal/src/engine/window.cpp:72-89,1173-1176,3255-3257`、`engine/metal/src/engine/prompt_chain.inc:357-360`）。

## 値と判定

`gdn_scan_name` 内の関数ローカル `static const std::string` 初期化で `std::getenv` を一度呼び、環境値全体を `std::string` の完全一致で比較します。未設定は空文字列に置き換えられ、明示的な空文字も同じく無効です。大文字小文字を区別し、空白除去・数値変換・部分一致はしません。許可名以外はエラーにせず「強制指定なし」として自動選択へ進みます（`engine/metal/src/engine/window.cpp:79-89`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値の例 |
|---|---|---|---|
| Metal prompt GDN scan | 機種・chunk 長による自動選択 | `gdn_scanr_4`、`gdn_scanr_4_8`、`gdn_scanr_4_4`、`gdn_scanr_4_2` | `0`、`1`、`true`、`false`、`gdn_scanr_4_8 `、`GDN_SCANR_4`、任意の別文字列。いずれも自動選択へ戻る |

自動選択は、device 名が正確に `Apple M4` なら `gdn_scanr_4_8`、正確に `Apple M5 Max` かつ scan の `T >= 4096` なら `gdn_scanr_4_4`、それ以外は `gdn_scanr_4` です。`gdn_scanr_4_2` は有効な強制値ですが、自動選択では選ばれません（`engine/metal/src/engine/window.cpp:85-89`）。

## 有効になる条件

- `STRATA_GPU_METAL` を定義して組み立てる Metal エンジン経路に限られます。Metal 以外の backend にはこの Strata 読み取り箇所がありません（`engine/src/prefill/prefill.cpp:9633-9641`、`engine/metal/src/engine/window.cpp:70-81`）。
- prompt が GDN scan を含む行列演算経路に入る必要があります。非 streaming では `STRATA_METAL_PROMPT=window` でなく、入力 token 数が `STRATA_METAL_PROMPT_MIN`（既定 32）以上の場合に `Window::prompt` を呼びます。streaming では `STRATA_METAL_PROMPT=window` でなく、`STRATA_METAL_PROMPT_GEMM` が文字列 `0` でなく、token 数が `STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）以上の場合に prompt chunk 経路を使います。これらの条件を満たさない場合は 8 行 window の経路になり、この selector は使われません（`engine/metal/src/engine/window.cpp:3743-3776`）。
- prompt 経路でも、走査対象の layer が GDN layer である必要があります。prompt chain は `l % G_QI != G_QI - 1` の分岐で GDN 前処理・scan・後処理を dispatch します（`engine/metal/src/engine/window.cpp:3235-3260`、`engine/metal/src/engine/prompt_chain.inc:322-371`）。
- 対象変数を有効値にしても prompt 経路そのものは有効化されません。モデルや request に GDN scan がなければ選択機会もありません。CLI 引数による直接上書きはこの selector にはありません。prompt 経路の選択に関係する上記の環境変数は別途そのゲートとして評価されます。

## 実行時の詳細

環境値は最初の `gdn_scan_name` 呼び出しで読み込まれ、関数ローカル `static` に保持されます。以後の呼び出しでは環境を再読しないため、同一プロセス内での環境変更は反映されません。一方、fallback の機種名と `T` 判定は関数を呼ぶたびに評価されます（`engine/metal/src/engine/window.cpp:79-89`）。

選択名は pipeline 関数名として prompt GDN scan の dispatch に渡されます。通常の window prompt と streaming prompt chunk の両方が同じ selector を呼びます。kernel source は `gdn_scanr_4`、`gdn_scanr_4_8`、`gdn_scanr_4_4`、`gdn_scanr_4_2` を `gdn_scan_r<4, TB>` の別 `TB` として export しています（`engine/metal/src/engine/window.cpp:3255-3257`、`engine/metal/src/engine/prompt_chain.inc:357-360`、`engine/metal/kernels/gdn_prompt.metal:329-334`）。

## ログと測定値

この変数の読み取り、無効値の fallback、選択した kernel 名について専用のログはありません。prompt 全体の既存 trace/profile は `STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されたときに集計時間を stderr に出しますが、選択名は表示しません（`engine/metal/src/engine/prompt_chain.inc:608-611`）。有効名に対応する Metal function が pipeline 作成時に見つからない場合は、共通処理が `mtl: no function %s %s` を stderr に出して exit code 3 で終了します。pipeline 生成失敗時は `mtl: pipeline %s: %s` を出して同じく終了します（`engine/metal/src/mtl_rt.mm:229-265`）。

`window.cpp` の実装コメントは Apple M4 で `gdn_scanr_4_8` が scan 1.16x / GDN prompt stage 1.11x（T 512..32K）、Apple M5 Max で `gdn_scanr_4_4` が T 4096 以上で 1.04x（4K）/ 1.10x（16K）と記載しています。ただしコメントには OS、モデル・量子化、他の設定、測定回数などの条件がなく、この文書では条件付きの再現可能な測定結果として扱いません（`engine/metal/src/engine/window.cpp:72-78`）。

## 根拠

- 実読み取り、受理値、fallback、機種・長さ別の自動選択: `engine/metal/src/engine/window.cpp:72-89`
- prompt GDN scan と decode window の別 kernel: `engine/metal/src/engine/window.cpp:1173-1176,3255-3257`; `engine/metal/src/engine/prompt_chain.inc:357-360`
- prompt 経路ゲートと Metal backend 呼び出し: `engine/metal/src/engine/window.cpp:3743-3776`; `engine/src/prefill/prefill.cpp:9633-9641`
- kernel export と pipeline 作成失敗時の出力: `engine/metal/kernels/gdn_prompt.metal:329-334`; `engine/metal/src/mtl_rt.mm:229-265`
