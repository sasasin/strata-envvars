# `STRATA_METAL_PREFETCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal エンジンがモデルを SSD から expert arena へストリームする場合に、次層の router 出力から予測した expert を先に読む機能を制御する。正の値は各 token について先読み候補にする上位 expert 数である。実装は `ExpertStream::open` の値設定と、`Window` の予測 router logits の生成に分かれている（`engine/metal/src/engine/stream.cpp:28-31,157-163`、`engine/metal/src/engine/window.cpp:975-983,1290-1303`）。

これは Metal backend 固有の設定で、CUDA/HIP/SYCL や通常の resident model 経路には適用されない。`STRATA_METAL_PREFETCH` を読む CLI／起動ラッパーはなく、Metal engine 内で直接読み取る。

## 値と判定

`stream.cpp` の `env_int` は unset または空文字なら呼び出し側の既定値を返し、それ以外は `std::atoi` を使う。先頭の空白と符号付き数字は `atoi` の規則で変換され、数字以降の文字は変換結果に含まれない。数字を開始できない文字列は `0` になる。数値の範囲・文字列全体・真偽語を検証する処理はない（`engine/metal/src/engine/stream.cpp:28-31`）。

同じ環境変数を `window.cpp` も別に読み、`std::atoi(e) <= 0` なら予測 logits の計算を止める。こちらは unset なら有効だが、空文字は `atoi("") == 0` として無効になる（`engine/metal/src/engine/window.cpp:980-983`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `ExpertStream::open` の先読み数 | expert bytes / layer が 1.5 MB を超える場合 `6`、それ以外 `10` | `1`, `2`, `1abc` → 1, 2, 1 | `0`, `-1`, `true`, 空白だけ → 0 以下 |
| `Window` の予測 logits | 有効 | `1`, `2`, `1abc`（`atoi` が正） | `0`, `-1`, `true`, 空文字、空白だけ（`atoi` が 0 以下） |

空文字は前者で既定値を使い、後者では予測を無効にする。このため空文字を設定すると、`pre_k_` 自体は正の既定値でも予測 logits が渡されず、decode の router 予測先読みは実行されない。非空の非数値文字列や `0anything` はどちらでも `atoi` 結果が 0 となり先読みを止める。`-2tail` などの負値も止める。`atoi` に渡す数値範囲外の文字列の結果は保証できないため、範囲外値の動作は定められない。

## 有効になる条件

- Metal engine の `Window` がモデルをストリーミングする場合に限る。ストリーム化は `STRATA_METAL_STREAM=1` で強制でき、`=0` なら無効。その他の値または unset では、GGUF の重みと余裕分が GPU working set / RAM の resident footprint cap に収まるかで自動判定される（`engine/metal/src/engine/stream.cpp:34-48`、`engine/metal/src/engine/window.cpp:736-744`）。
- 環境変数を読むのは `ExpertStream::open` 時と `Window` の初期化時である。この時点でモデルの stream 経路に入っていなければ値は使われない。起動後の環境変更を再評価するループや static cache はなく、すでに作られた `ExpertStream` / `Window` には反映されない（`engine/metal/src/engine/stream.cpp:61-66,157-165`、`engine/metal/src/engine/window.cpp:975-983`）。
- 値が正でも、次層の予測 logits がない呼び出しでは先読みされない。`Window::at_cut` は `st_pred_` が真で、かつ cut IDs がないときだけ logits を `ExpertStream::at_layer` に渡す（`engine/metal/src/engine/window.cpp:557-560`）。
- プロンプト chunk（`T > 8`）では、現在層処理後に次層の arena 未常駐 experts を読み込む専用経路に入り、予測 logits による top-k 先読みとは別に動く。したがって本変数を 0 にしても、この prompt 向け先読みは止まらない（`engine/metal/src/engine/stream.cpp:620-623,693-712`）。
- この変数が制御するのは次層 router 予測の expert 先読み数である。第 2 層先読み数は別変数 `STRATA_METAL_PREFETCH2` が 0 より大きい場合だけ設定される（`engine/metal/src/engine/stream.cpp:160-163,714-716`）。

## 実行時の詳細

ストリーム経路の初期化時、各層の gate / up / down expert bytes の合計を層数で割り、その平均が `1.5e6` bytes より大きいモデルを `big` と判定する。`STRATA_METAL_PREFETCH` が unset または空なら `big` は既定 top-k `6`、それ以外は `10` を使う。`pre_k_ > 0` が `prefetch_` となる（`engine/metal/src/engine/stream.cpp:157-163`）。

各層の MoE 入力から、その層の通常 router logits に加えて次層の router logits を計算する。`st_pred_` が有効な場合に限って計算される。レイヤー間の host handoff で `ExpertStream::at_layer` に予測 logits が渡ると、各 token の予測順位から最大 `pre_k_` 個を次層の expert として非同期 I/O queue に入れる。先読みが無効なら `prefetch_` が偽、または `pred` が null になり、この経路は呼ばれない（`engine/metal/src/engine/window.cpp:1290-1303`、`engine/metal/src/engine/stream.cpp:620-623,714-717`）。

既に arena にある expert は再読込せず、未開始の不要な先読みはキャンセルされる。先読み済み expert が現在必要になった場合は queue 内の読み込みを優先し、読み込み完了を待つ（`engine/metal/src/engine/stream.cpp:643-680,365-372`）。プロンプト chunk は別途、次層の未常駐 experts を読み込んでから復帰する（`engine/metal/src/engine/stream.cpp:693-712`）。

## ログと測定値

専用の有効・無効警告はない。arena 作成ログの `read-ahead top %d` は有効なら `pre_k_`、無効なら `0` を出すため、設定値そのものではなく `ExpertStream` 側で使う top-k を確認できる。終了時の stream report には `read-aheads` の発行数・window 当たり数・drop 数と、`read-ahead hits` が出る（`engine/metal/src/engine/stream.cpp:544-547,806-824`）。空文字では前述の二つの読み取りの差によりログの `read-ahead top` が正数でも decode の予測 logits がなく、予測先読みが発行されない場合がある。

ストリームの実 I/O 失敗時には `strata metal stream: reading expert %d of layer %d failed` を stderr に出して `exit(6)` する。また、層で利用可能な slot がない場合は `strata metal stream: no free slot (layer %d)` を出して `exit(6)` する。これは環境変数の値検証エラーではなく、streaming 中の I/O / arena 経路の失敗である（`engine/metal/src/engine/stream.cpp:278-308,674-680`）。

## 根拠

- 読み取り helper と unset / empty の既定値処理: `engine/metal/src/engine/stream.cpp:28-31`
- streaming の選択条件と初期化: `engine/metal/src/engine/stream.cpp:34-48,157-165`、`engine/metal/src/engine/window.cpp:736-744`
- 予測 logits の別判定、生成と受け渡し: `engine/metal/src/engine/window.cpp:557-560,975-983,1290-1303`
- top-k 先読みと prompt chunk の別経路: `engine/metal/src/engine/stream.cpp:620-623,693-717`
- queue の発行・待機、ログと失敗経路: `engine/metal/src/engine/stream.cpp:278-308,643-680,544-547,806-824`
