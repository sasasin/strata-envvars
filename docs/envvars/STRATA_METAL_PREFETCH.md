# `STRATA_METAL_PREFETCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の SSD expert streaming が選ばれた場合に、次の layer で使われると予測した routed expert を先読みする数を制御します。各 token の次 layer router logits から上位 K 個を選び、重複 expert をまとめて I/O queue に積みます。これは予測読み込みの制御であり、layer が実際に必要とする expert は通常の layer 処理で読み込まれます。

## 値と判定

`ExpertStream::open()` は共通 helper `env_int()` で値を読みます。未設定または空文字列なら既定値を使い、それ以外は `std::atoi()` の結果です。したがって文字列全体の厳密な整数 parse ではなく、先頭の空白と符号を許し、数字列の後ろは無視します。数字で始まらない文字列は 0 になります。

| 環境変数値 | `pre_k_` の結果 | 予測読み込み |
|---|---:|---|
| 未設定または空文字列 | expert が大きい場合 6、それ以外 10 | 有効 |
| `0`、負数、数値で始まらない文字列 | 0 以下 | 無効 |
| 正の整数 | parse した値 | 有効。読み込み時の K は最大 32 に制限 |
| 正の整数の後に文字が続く値（例: `4xyz`） | 先頭の整数 | その値で有効 |

「expert が大きい」は各 layer の平均 expert byte 数 `eb / 48` が 1,500,000 を超える場合です。`atoi()` の範囲外値の扱いは C/C++ 実装に依存するため、文書では有効な `int` 範囲外の結果を規定しません。

Window 側にも独立した読み取りがあります。ここでは未設定なら予測 logits 用バッファを確保し、設定時は `atoi(value) > 0` の場合だけ確保します。このため、数値でない文字列は両方の読み取りで 0 となり無効です。一方、明示的な空文字列は不一致があります。`stream.cpp` は helper により既定 K（6 または 10）を採用しますが、`window.cpp` は `atoi("") == 0` として予測バッファを確保しません。その結果、先読みは実行されません。

## 有効になる条件

- Metal engine が使われ、かつ `ExpertStream::wanted()` が expert streaming を選んだ場合だけ参照されます。streaming は `STRATA_METAL_STREAM=1` で強制でき、`=0` で無効化できます。それ以外（未設定を含む）は、モデル expert が GPU working set に余裕を持って収まらない場合に自動選択されます。
- prompt chunk (`T > 8`) の処理では `at_layer()` が prompt 経路を通って戻るため、この変数による予測 read-ahead は行いません。
- 次 layer が存在し、router logits の予測 pointer が渡される必要があります。最後の layer では次 layer がないため実行されません。
- 先読み数は `ahead()` の入口で 32 に上限設定されます。実際の読み込みは空き victim slot がなくなればそこで打ち切られ、すでに arena にある expert の読み直しは行いません。
- `STRATA_METAL_PREFETCH2` は別途 layer + 2 の予測読み込みを制御します。本変数を 0 以下にしても、`STRATA_METAL_PREFETCH2` が正なら layer + 2 の先読みは独立して実行可能です。ただし Window 側の予測バッファ確保は本変数が正（または未設定）であることを条件にするため、本変数が 0 以下なら `pred2` も供給されず、layer + 2 の先読みも実行されません。

## 実行時の詳細

値は Window 初期化中に作られる `ExpertStream` の `open()` 時に読み取られ、`pre_k_` と `prefetch_` に保存されます。Window 初期化は予測 logits 用の `predL_` バッファを必要に応じて確保します。環境変数を変更しても、すでに初期化済みの stream や window の保存値・バッファは再評価されません。

通常の decode layer では、Window が layer `l` の FFN input から layer `l+1` の router logits を計算して保存します。layer の host cut に到達すると `at_layer()` にその logits が渡り、`prefetch_` が有効であれば `ahead(l+1, ..., pre_k_)` が上位候補を選びます。候補 expert の読み込みは I/O queue に追加され、I/O thread が非同期に処理します。後続 layer では resident な expert を使い、未到着の予測読み込みは待機・昇格され、予測に外れた未開始の queue entry は破棄されます。

stream arena の起動時 stderr 統計には `read-ahead top %d` として有効な `pre_k_` が表示され、先読み無効時は 0 と表示されます（`STRATA_METAL_PREFETCH=0` の場合）。このログは arena の fill 統計であり、個別の候補や命中率を表示するものではありません。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: `env_int()` の unset・空文字の fallback と `atoi()` 変換。
- `metal/src/engine/stream.cpp:33-48`: Metal streaming の選択。`STRATA_METAL_STREAM` の完全一致 `1` / `0` と自動判定。
- `metal/src/engine/stream.cpp:154-160`: expert サイズ区分、既定 K、変数読み取り、正値判定。
- `metal/src/engine/stream.cpp:538-541`: arena fill 統計に read-ahead top を出力。
- `metal/src/engine/stream.cpp:571-612`: K の 32 上限、router logits の上位候補抽出、重複排除、先読み queue 登録。
- `metal/src/engine/stream.cpp:614-711`: prompt 経路の除外、実際の layer expert 処理後に行う layer + 1 / layer + 2 の先読み。
- `metal/src/engine/window.cpp:427-432`: streaming の選択と `ExpertStream::open()` 呼び出し。
- `metal/src/engine/window.cpp:538-547`: Window 側の独立した変数読み取りと予測バッファ確保。
- `metal/src/engine/window.cpp:292-295, 768-777`: host cut への logits 渡しと layer + 1 / layer + 2 router logits の生成。
- `metal/src/engine/stream.h:62-66, 119-120`: 予測入力と設定値のメンバー。

`docs/DETAILS.md` には `STRATA_METAL_PREFETCH` の個別説明を確認できませんでした。この調査では性能値や先読みの正答率は主張しません。
