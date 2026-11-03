# `STRATA_METAL_LDB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal decode window が dispatch する一部のカーネルを切り替えます。既定では load-batched 版を使い、`STRATA_METAL_LDB=0` のときは元のカーネルを選びます。対象は hyper-connection の正規化 `gr_norm`、MoE の combine `moe_combine_sh`、および Metal MTP drafter の RMS norm です。Strata が Metal 向けにビルドされ、Metal window を使う場合にだけ参照されます。`src/core/verify.cpp:90-105,900-902` が `STRATA_GPU_METAL` ビルドで verifier を Metal window に引き渡し、`metal/CMakeLists.txt:110-130` が Metal engine を `strata` に組み込みます。

## 値と判定

値は文字列全体を `"0"` と比較します。数値変換、空白除去、大文字小文字変換はありません。

| 環境値 | 選択 |
| --- | --- |
| 未設定 | load-batched 版 |
| 空文字 | load-batched 版 |
| 正確に `0` | 元のカーネル |
| その他すべて（例: `1`, `00`, `false`, ` 0`） | load-batched 版 |

`ldb_` は `Window` インスタンスのメンバー初期化時に設定され、そのインスタンスの間保持されます。実行中に環境を変更しても既存インスタンスの選択は変わりません。CLI 引数や他の環境変数による上書きは見つかりませんでした。根拠: `metal/src/engine/window.cpp:441-443`。

## 有効になる条件

- Metal backend であることが必要です。CUDA / HIP の verifier はこの Metal window への引き渡し対象ではありません（`src/core/verify.cpp:90-105,900-902`）。
- `gr_norm` の切り替えは decode window の通常の層処理、および PLE が有効な場合の処理で使われます。`Window::gr_read()` と PLE 経路は同じ `k_norm()` の選択を使います（`metal/src/engine/window.cpp:931-946,1428-1441`）。
- MoE combine の切り替えは window の層で combine dispatch を行う箇所で使われます（`metal/src/engine/window.cpp:1272-1279`）。
- MTP drafter の切り替えは幅が 2560 または 10240 の RMS norm でのみ load-batched 版を選びます。それ以外の幅は `ldb_` が true でも `mtp_rms` のままです（`metal/src/engine/window.cpp:2346-2354`）。

## 実行時の詳細

`STRATA_METAL_LDB` が有効（未設定を含む）なら `k_norm()` は `gr_norm2`、`k_comb()` は `moe_combine_sh2` を返します。`=0` ではそれぞれ `gr_norm`、`moe_combine_sh` を返します。両経路とも同じ引数・dispatch grid を使います（`metal/src/engine/window.cpp:441-443,931-946,1272-1279`）。MTP では有効時かつ幅 2560 / 10240 の場合に `mtp_rms_b10` / `mtp_rms_b40` を選び、それ以外は `mtp_rms` です（`metal/src/engine/window.cpp:2346-2354`）。

カーネルソースの説明では、load-batched 版は読み込みをまとめ、元版と同じ順序の演算を行う実装です。`gr_norm2` と `gr_norm` は同じ `GrArgs` と入出力を扱い、`moe_combine_sh2` と `moe_combine_sh` は同じ combine 結果を計算する構造です（`metal/kernels/gr.metal:25-58`, `metal/kernels/glue.metal:38-68`）。MTP の batched RMS norm は `metal/src/engine/msl/mtp.metal:16-58` にあります。性能差や実機での出力同一性はこの調査では測定していません。

この変数専用のログや警告はありません。Metal window 初期化成功時には一般的な `strata metal: decode window on ... ready in ...` が stderr に出ます（`metal/src/engine/window.cpp:870-873`）。選択された関数名が Metal library にない場合、pipeline 作成時に `mtl: no function <name> ...` を stderr に出して終了コード 3 でプロセスを終了します。pipeline 作成自体が失敗した場合も `mtl: pipeline <name>: ...` を出して終了コード 3 です（`metal/src/mtl_rt.mm:484-521`）。この環境変数の値に対する専用 fallback はありません。

## 根拠

- `metal/src/engine/window.cpp:441-443` — 値判定と正規化・combine カーネル名の選択。
- `metal/src/engine/window.cpp:931-946,1272-1279,1428-1441` — 選択されたカーネルを dispatch する箇所。
- `metal/src/engine/window.cpp:2346-2354` — MTP RMS norm の幅別選択。
- `metal/kernels/gr.metal:25-58`, `metal/kernels/glue.metal:38-68`, `metal/src/engine/msl/mtp.metal:16-58` — 元版と load-batched 版のカーネル実装。
- `src/core/verify.cpp:90-105,900-902`, `metal/CMakeLists.txt:110-130` — Metal backend と window への接続。
- `metal/src/mtl_rt.mm:484-521` — 関数・pipeline 作成失敗時のログと終了。
