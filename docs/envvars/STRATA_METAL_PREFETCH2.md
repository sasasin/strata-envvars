# `STRATA_METAL_PREFETCH2`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の SSD expert streaming 経路で、decode 中に 2 層先の expert を先読みする数（top-k）を指定します。`STRATA_METAL_PREFETCH` が有効で、ストリーミング経路が選ばれたときだけ使われます。値が正なら、現在の層の FFN 入力から計算した 2 層先 router logits の上位 expert を I/O queue に先読みとして登録します。これは読み込みの先行であり、router の選択やモデル出力をこの値で変更する処理ではありません。

## 値と判定

Metal stream の `env_int()` は、未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を使います。`STRATA_METAL_PREFETCH2` の既定値は `0` です。値は `ExpertStream::open()` 時に読み、`ExpertStream` のメンバーに保持します。

| 環境値 | 読み取った値 | 効果 |
|---|---:|---|
| 未設定、空文字 | 0 | 無効 |
| 数値変換結果が 0 以下 | その値 | 無効 |
| 数値変換結果が 1 以上 | その整数 | 2 層先の先読みを有効化。実際の top-k は最大 32 |

`atoi()` によるため、文字列全体の妥当性検査はありません。先頭の空白と符号は数値変換時に扱われ、数値の後ろに続く文字列は判定に使われません。先頭から数値を変換できない文字列は 0 となり無効です。正値に上限チェックを行うのではなく、`ahead()` が呼ばれた後に K を 32 へ丸めます。整数範囲を超える文字列の扱いはこのコードで保証されません。

## 有効になる条件

- Metal `Window::init()` が `ExpertStream::wanted()` により expert streaming を選び、`ExpertStream::open()` まで成功する必要があります。streaming は `STRATA_METAL_STREAM=1` で強制でき、`=0` で無効化できます。それ以外（未設定を含む）ではモデル・デバイスの footprint 判定で選ばれます。非 streaming のモデルでは本変数は読み取られません。該当経路は Metal backend のみです。
- `STRATA_METAL_PREFETCH` が未設定または `atoi()` の結果が正である必要があります。`Window::init()` は同変数の結果が 0 以下なら `st_pred_` を無効にし、1 層先・2 層先の予測 logits を確保しません。この場合、`STRATA_METAL_PREFETCH2` が正でも 2 層先先読みは行われません。
- 2 層先 logits が渡され、現在層 `l` に対して `l + 2 < 48` である必要があります。prompt chunk の layer cut では `cut_ids_` が使われ、`at_cut()` はその場合 `pred2` を null として渡します。また `at_layer()` は `T > 8` を prompt と判定すると通常の予測先読みより先に戻ります。このため追加先読みが実行されるのは `pred2` がある decode 経路です。
- 正値の K は `min(K, 32)` で上限 32 になります。さらに、先読み対象が既に arena にある場合や空き victim slot がなくなった場合は追加の読み込みを登録しません。

## 実行時の詳細

`ExpertStream::open()` が `STRATA_METAL_PREFETCH2` を一度読み、`pre_k2_` に保存します。続いて `Window::init()` は `STRATA_METAL_PREFETCH` が有効で `ahead2() > 0` のときだけ 2 層先 logits 用バッファを確保します。各 decode 層の処理では、現在層の FFN 入力 `XF_` を使って `l + 2` の router logits を計算します。layer cut の host 側処理で、その logits と `pre_k2_` を `ExpertStream::at_layer()` に渡します。

`at_layer()` は通常の層の expert 読み込み・待機の後、`l + 2 < 48` かつ `pred2 != nullptr` かつ `pre_k2_ > 0` の場合に `ahead(l + 2, ..., pre_k2_)` を呼びます。`ahead()` は各 token の logits から最大 K 個を取り、window 内で expert ID を重複排除してから、まだ arena にないものを非 urgent の read-ahead queue に積みます。後続でその先読み expert が実際に必要になれば通常の layer processing が読み込み完了を待ちます。まだ開始していない不要な read-ahead は後の層でキャンセルされ得ます。

本変数自体に専用ログはありません。stream の統計出力には read-ahead hit 数、発行数、drop 数などが含まれますが、`STRATA_METAL_PREFETCH2` 固有の値や 2 層先分だけは区別されません。expert のファイル読み込みが失敗した場合は `strata metal stream: reading expert ... failed` を stderr に出して終了コード 6 で終了します。環境値の不正を示す警告やエラーはありません。環境変数は stream open 時の設定値として保持されるため、実行中の環境変更はこのインスタンスには反映されません。

## 根拠

- `metal/src/engine/stream.cpp:27-30,157-160`: `env_int()` の未設定・空文字・`atoi()` 処理、既定値 0 の読み取り。
- `metal/src/engine/stream.cpp:575-615,617-620,690-714`: top-k 上限 32、先読み候補の作成、decode 時の条件、prompt path の return。
- `metal/src/engine/stream.cpp:335-346,640-648,803-821`: read-ahead queue への登録、不要な未開始 job のキャンセル、観測可能な統計。
- `metal/src/engine/stream.cpp:275-304`: expert 読み込み失敗時の stderr と終了コード 6。
- `metal/src/engine/window.cpp:393-395,524-548,723-732,1014-1031`: stream 初期化、streaming 条件、`STRATA_METAL_PREFETCH` による予測無効化、予測 logits と 2 層先 buffer の確保・計算・引き渡し。
- `metal/src/engine/stream.h:62-66,120`: `pred2` の意味と保持する設定値。
