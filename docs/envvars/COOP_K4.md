# `COOP_K4`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンが、GPU の `matmul2d` cooperative tensor の K4 レイアウトを使うかを指定します。対象はデコード時の MoE down tile の選択と、2種類の Metal prompt 経路にある QSA / expert kernel variant です。unset の場合は GPU 上でレイアウトを検査して決めます。

この変数は Metal エンジン内でのみ読み取られます。CUDA、HIP、SYCL、Python サーバーの設定ではありません。

## 値と判定

環境変数が設定されている場合、実装は `std::atoi(e) != 0` で判定します。文字列全体の検証はしません。

| 値 | 判定 |
|---|---|
| unset | GPU の cooperative tensor のレイアウト検査結果を使う |
| `0`、空文字、数値に変換できない文字列（例: `true`） | false |
| 先頭の整数部分が 0 以外（例: `1`, `2`, `-1`, `1tail`, `1e2`） | true |
| 小数表記で `atoi` が先頭から 0 と読む文字列（例: `0.5`） | false |

`atoi` は先頭の空白と符号を受け付け、整数として読める接頭部分の後ろは判定に使いません。範囲外の整数入力に対する挙動はコードで検査・制限されていません。

根拠: `metal/src/engine/prompt_chain.inc:26-47`、`metal/tests/coop_probe.h:10-35`。後者は `metal/src/engine/window.cpp` が include し、Metal prompt GEMM の初期化から呼ぶ helper です（`metal/src/engine/window.cpp:14-20,2147-2173`）。

## 有効になる条件

- Metal エンジンを使う実行経路に限ります。
- prompt chain では、`Window::pc_setup()` が prompt chain のバッファを初めて用意するときに値を読み、`PromptBufs::k4` に保存します。chunk 拡張時も保存済みの値を引き継ぎます。
- 通常のデコードでは `m5_layout()` が最初に呼ばれたときに結果を `m5_layout_` に保存します。
- prompt GEMM 経路では `prompt_gemm_init()` が `coop_k4(cx)` を呼び、`PromptGemm::k4` に保存します。prompt GEMM は初期化済みなら再初期化しません。

したがって実行中に環境変数を変更しても、各経路で一度選択・保存されたレイアウトは切り替わりません。まだ初期化されていない別経路では、その経路が初期化される時点の値を読みます。

## 実行時の詳細

設定値がある場合、実装はその真偽をそのまま採用し、GPU レイアウトの probe は実行しません。unset の場合、prompt chain と通常デコードは `coop_layout_16_64_32` kernel を実行し、各 lane の出力に連続する4つの K 座標が並ぶかを調べます。検査が全 lane で成立すれば true、成立しなければ false です。prompt GEMM は同じ環境値を読む共通 helper を呼び、`coop_layout_16_64_32` と `coop_layout_16_32_32` の両方、および paired-run の配置も検査します。どの経路も初期化時に probe します。

選択結果が true のとき:

- 通常デコードでは `m5_layout()` が false の場合と異なる down tile (`dl`, `dr`) を選びます。条件は量子化 type によって異なり、`Q2_0` はレイアウト値にかかわらず専用 tile 条件を使います。
- prompt chain では QSA の score/attention に K4 用 kernel を選び、function constant 7 を true にします。expert weight type が trellis 系（type 144 以上）でなければ、expert の gate/up と down に v3 kernel も選びます。false なら従来の QSA attention と v2 expert kernel を使います。
- prompt GEMM では、`STRATA_METAL_PROMPT_EXPERTS` と `STRATA_METAL_PROMPT_QSA` が未設定の場合、それぞれ expert v3 と QSA flash を選ぶ既定値になります。いずれも明示値があるとその設定が既定値より優先します。trellis expert type では v3 は無効化されます。

prompt chain は stderr に `strata metal: prompt kernels ...` として選択 variant を出します。prompt GEMM は `strata metal: prompts on the matrix units ... matmul2d layout K4|other` を出します。通常デコード側には、この変数専用のログは確認できません。

この変数は probe を強制上書きします。GPU が示したレイアウトと異なる値を設定した場合に正しい計算になるか、また性能がどう変わるかは、ソース調査だけでは確認していません。`docs/DETAILS.md` と `docs/MAC.md` には、この環境変数の値・判定規則に関する説明を確認できませんでした。性能値や正確性は記載していません。

## 根拠

- `metal/src/engine/prompt_chain.inc:26-47,49-62,94-102`: 環境値の判定、unset 時の layout probe、prompt chain の kernel 選択・ログ。
- `metal/src/engine/prompt_chain.inc:240-262,304-329`: K4 による QSA / expert kernel の分岐。
- `metal/src/engine/window.cpp:380-403,926-937,1914-1923`: 通常デコードの layout cache と down tile 分岐。
- `metal/src/engine/window.cpp:14-20,2147-2173,2230-2234`: prompt GEMM から probe helper を呼ぶ経路、既定 variant、ログ。
- `metal/tests/coop_probe.h:1-35`: `window.cpp` が production build に include する probe helper の値判定と GPU layout 検査。このファイルはテスト用ディレクトリにありますが、実行エンジンから呼ばれるため、その実行経路に限って根拠にしています。
