# `STRATA_METAL_MTP_CHAIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend の MTP draft で、複数 draft step の pick・確率計算・次 step の embedding を GPU 上の一つの command buffer にまとめる経路を選ぶ。無効にすると step ごとに command buffer を実行し、各 step の token 選択と embedding の dequantize をホスト側で行う。対象は `engine/metal/src/engine/window.cpp` の `Window::mtp_load` と `Window::mtp_draft` である（`engine/metal/src/engine/window.cpp:2595-2605,2926-2938,2957-2981`）。

## 値と判定

`Window::mtp_load` が `std::getenv` で一度読み、値全体を文字列 `"0"` と比較する。それと完全一致した場合だけ明示的に OFF。それ以外は ON 判定の候補になるが、embedding tensor の型が許可リストに含まれることも必要である（`engine/metal/src/engine/window.cpp:2598-2602`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Metal MTP のロード時、embedding tensor type が `{30, 8, 2, 6, 20, 23, 42, 21, 11, 12, 13, 14, 18}` のいずれか | チェーン経路を選択 | `1`、`true`、空文字、`0anything`、` 0`、`00`、その他 `"0"` 以外の文字列 | `0`（完全一致のみ） |
| Metal MTP のロード時、embedding tensor type が上記以外 | チェーン経路を選ばない | なし | 設定値にかかわらずチェーン経路を選ばない |

大文字小文字、空白、数値としての妥当性は検査しない。`"0"` 以外はすべて同じ ON 判定で、空文字も設定ありの OFF ではない。CLI 引数や別の環境変数によるこの判定の上書きはない（`engine/metal/src/engine/window.cpp:2598-2602`）。

## 有効になる条件

- Metal backend を含むビルドであること。Metal CMake 設定は macOS 専用で、`STRATA_GPU_METAL=1` を定義する。CUDA/HIP/SYCL ビルドではこの Metal 実装を使わない（`engine/metal/CMakeLists.txt:1-2,89-94`）。
- MTP drafter がロードされること。共有 MTP ローダーは Metal build で `metal_engine::mtp_load` を呼び、Metal window の初期化時に保存済み MTP パスが空でなければ `Window::mtp_load` が実行される。MTP がロードされない場合、この変数は読まれない（`engine/src/core/mtp.cpp:345-354`; `engine/metal/src/engine/window.cpp:3627-3635,3705-3729`）。
- embedding tensor type が許可リストにあること。外れた場合は環境変数が未設定または `"0"` 以外でも従来経路になる（`engine/metal/src/engine/window.cpp:2598-2602`）。
- チェーン経路を選んだ場合でも、初期の GPU embedding とホスト dequantize の比較で最大差が `1e-6` を超えると、stderr に警告してチェーン経路を無効化する（`engine/metal/src/engine/window.cpp:2611-2636`）。
- 実際の一括 draft 経路は `chain_` が真かつ `max_steps > 0` のときに限る。Metal MTP 呼び出し元は `max_steps` を `max_t_ - 1` と `max_drafts_` の小さい方として求める。0 以下ならこの変数が ON 判定でもチェーン経路に入らず、step ごとのループは 0 回で draft 数 0 を返す（`engine/src/core/mtp.cpp:1869-1878`; `engine/metal/src/engine/window.cpp:2930-2958,2958-2984`）。

## 実行時の詳細

環境値は `Window::mtp_load` で chain flag を決める時に読み取られ、ロード後に同じプロセスで環境値を変更しても現在の `Window` の `chain_` には反映されない。`window_init` は window が未初期化の場合だけ MTP をロードするため、既存 window を使う後続処理でこの値を読み直す経路はない（`engine/metal/src/engine/window.cpp:2595-2602,3627-3638`）。

チェーン経路では round の dispatch を組み立て、一度 `cx_->run_graph(ds)` を呼ぶ。その後ホスト側で GPU が書いた draft token と確率を読み、`min_p > 0` かつ確率が閾値未満なら後続 draft を打ち切る。従来経路では各 step ごとに `run_graph` し、GPU の token pick の結果をホストで読み、必要なら draft vocabulary の token ID に戻し、logits から softmax 確率を計算して次 step に渡す（`engine/metal/src/engine/window.cpp:2937-2956,2958-2984`）。

## ログと測定値

チェーン経路を選ぶと初期 parity 検査後に stderr へ `strata metal: MTP draft round in one command buffer (embedding type %d on the GPU: max |GPU - host| %.3g over %d rows)` を出す。最大差が `1e-6` を超える場合は `strata metal: the GPU embedding differs from the host's: a command buffer per step` を出して従来経路に切り替える。チェーン経路を選ばない場合、この parity 検査ログと警告は出ない（`engine/metal/src/engine/window.cpp:2611-2636`）。

この変数に関する測定値は、調査対象の Strata ソースと参照した `docs/MAC.md` に条件付きで示されていないため記載しない。`docs/MAC.md` の Switches 表には「一 draft step ごとではなく一 round ごとの GPU submission」とあるが、数値測定結果ではない（`docs/MAC.md:261-272`）。

## 根拠

- `engine/metal/src/engine/window.cpp:2595-2605` — MTP ロード後の型判定、環境値読み取り、チェーン用ライブラリのコンパイル。
- `engine/metal/src/engine/window.cpp:2611-2636` — GPU/host parity 検査、ログ、fallback。
- `engine/metal/src/engine/window.cpp:2930-2984` — 一 round 経路と step ごとの経路、および確率閾値による打ち切り。
- `engine/src/core/mtp.cpp:345-354,1869-1879` — Metal MTP のロードと draft 呼び出し側の step 上限。
- `engine/metal/src/engine/window.cpp:3627-3635,3705-3729` — MTP ロード保留と window 初期化時の適用。
- `engine/metal/CMakeLists.txt:1-2,89-94` — Metal backend の build 条件。
