# `STRATA_METAL_WRAP_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Metal backend がモデルの mmap 領域全体を1個の Metal buffer にできない大きさで包むとき、領域を重複する複数の buffer に分ける処理を使うか制御する。`STRATA_METAL_WRAP_SPLIT=0` の場合は分割せず、1個の buffer として包む。未設定を含むそれ以外の値では分割を許可する。分割許可は、実際に `bytes > maxBufferLength` のときだけ結果を変える（`engine/metal/src/mtl_rt.mm:321-353`）。

通常の `Window::init` では、Metal の resident-model 経路で GGUF 全体を包む際にこの設定が参照される。expert streaming 経路では全モデルを包む呼び出しを通らない（`engine/metal/src/engine/window.cpp:736-744, 765-785`）。

## 値と判定

値は数値や真偽値に parse せず、`getenv` が非 null かつ文字列全体が厳密に `"0"` かを比較する。`bytes <= maxlen` なら環境変数判定に関わらず単一 buffer の経路を使う。ここで `maxlen` は GPU の `maxBufferLength` を 16,384 byte 単位で切り下げた値（`engine/metal/src/mtl_rt.mm:321-324`）。

| 条件 | unset | 有効になる値（分割を許可） | 無効になる値（分割を抑止） |
|---|---|---|---|
| `bytes <= maxlen` | 単一 buffer | どの値でも単一 buffer | どの値でも単一 buffer |
| `bytes > maxlen` | 重複 buffer に分割 | 空文字、`1`、`true`、`false`、`0anything`、その他 `"0"` 以外の文字列 | `0` のみ。単一 buffer として試行 |

大文字小文字や前後の空白は正規化せず、数値としての妥当性も検査しない。したがって `FALSE`、` 0`、`0 ` も分割を許可する。無効文字列用の警告や fallback はない（`engine/metal/src/mtl_rt.mm:323-324`）。

## 有効になる条件

- Metal backend を含む macOS 実行であること。実装は Metal device の `maxBufferLength` と `MTLBuffer` を使う Objective-C++ ランタイム内にある（`engine/metal/src/mtl_rt.mm:321-340`）。
- `Context::wrap(p, bytes, max_span)` が呼ばれること。通常のモデル読込では `Window::init` の resident 経路で、`ExpertStream::wanted` が false の場合に限り呼ばれる。streaming が有効な経路は別の処理へ進む（`engine/metal/src/engine/stream.cpp:34-49`; `engine/metal/src/engine/window.cpp:736-744, 784`）。
- 3引数の `wrap` に渡る `bytes` が `maxlen` より大きいこと。小さい場合は設定値を見ても分岐結果は変わらない（`engine/metal/src/mtl_rt.mm:321-324`）。
- Gyro/PLE を含むモデルでは、`STRATA_METAL_WRAP_PLE` 等によって `Window::init` が `wrap_ranges` を選ぶと、この設定を読む3引数 `wrap` を通らない。PLE を除く範囲が `maxlen` を超えて範囲分割できない場合など、全体を包む分岐へ進んだときには対象設定が適用される（`engine/metal/src/engine/window.cpp:748-785`）。

## 実行時の詳細

モデルの全体 wrap 時、`maxlen` を超え、かつ値が厳密な `"0"` でなければ `max_span` を 16,384 byte 単位に切り上げ、`maxlen - span` ごとに最大 `maxlen` の範囲を作る。これらの範囲は隣同士で重なり、各 chunk に最大の tensor または同時に bind する routed-expert 範囲が収まるように呼び出し元が `span` を計算する。成功後は chunk 数、最大 buffer 長、overlap を stderr に出す（`engine/metal/src/mtl_rt.mm:325-353`; `engine/metal/src/engine/window.cpp:768-784`）。

この環境変数は `Context::wrap` の呼び出しごとにその場で `getenv` され、static cache はない。設定変更が後の呼び出しに反映されるかはプロセス環境の変更方法に依存する。通常の `Window::init` ではモデル読込時に wrap が行われるため、推論の各 token や request ごとの切替ではない（`engine/metal/src/mtl_rt.mm:321-324`; `engine/metal/src/engine/window.cpp:714-785`）。CLI 引数や設定ファイルがこの値を上書きする実装は見つからなかった。

分割経路で `span >= maxlen / 2` なら `mtl_rt.mm:327` のエラーを stderr に出して終了コード 4 で停止する。chunk 作成が失敗した場合も詳細を stderr に出して終了コード 4 で停止する。分割を抑止した単一 wrap が失敗した場合は `mtl: wrap %zu failed` を出し、終了コード 4 となる。これは Metal buffer 作成の成否に対する Strata の処理であり、GPU driver 内部の挙動はここでは規定しない（`engine/metal/src/mtl_rt.mm:327-340, 383-390`）。

## ログと測定値

分割が成功した場合の stderr は `mtl: wrapped %.2f GB as %zu overlapping buffers (maxBufferLength %.2f GB, overlap %.2f GB)`。範囲が大きすぎる場合は `mtl: wrap %zu: a tensor of %zu bytes does not fit the chunks`、chunk 作成失敗時は `mtl: wrap chunk %zu+%zu failed` を出して終了コード 4 で停止する。単一 wrap が失敗すると `mtl: wrap %zu failed` を出して同じ終了コードで停止する。分割されない正常経路や環境変数の無効値に対するログはない（`engine/metal/src/mtl_rt.mm:327-353, 383-390`）。

この変数による性能・正確性の測定値は、対象 commit の実装および関連する `docs/MAC.md` / `docs/DETAILS.md` に見つからなかったため記載しない。

## 根拠

- `engine/metal/src/mtl_rt.mm:321-353, 383-390` — 値判定、分割方式、ログ、失敗時の終了。
- `engine/metal/src/engine/window.cpp:714-785` — モデル読込、resident / streaming / PLE の分岐と `max_span` の計算。
- `engine/metal/src/engine/stream.cpp:34-49` — streaming を選ぶ条件。
- `engine/metal/src/mtl_rt.h:18-27, 105-112` — `Buffer` の chunk 表現と `wrap` の役割。
