# `strata-dsv41 --threads`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine の独立 CLI） |
| オプション | `--threads` |
| 別名 | なし |
| 値 | `on` / `off` を想定する文字列。実装は `off` との完全一致だけを判定する |

## 役割

GPU ごとに host thread を使って各 GPU の layer 処理を enqueue する threads mode を選びます。推論 engine の並列経路に関わる設定で、`--cpu-threads` が CPU lane の worker 数を調整するのとは別です（`src/dsv41/ds4_model.hpp:33-35,59-67`）。

## 使い方

```sh
strata-dsv41 --pack ./model/maya-ds4 --serve --threads on
```

`--serve` の代わりに `--ids ...` を使う通常の推論経路でも指定できます。`--pack` と実行モードの引数は engine の usage に示されています（`src/dsv41/ds4_main.cpp:118-123`）。

## 値と既定値

- 既定値は off (`Options::threads = false`) です（`src/dsv41/ds4_model.hpp:62-63`）。
- `--threads` の値が文字列 `off` と一致する場合だけ false、それ以外は true になります。したがって `on` は有効ですが、`false`、`0`、空文字列なども拒否されず true として扱われます。`on` / `off` の列挙検証はありません（`src/dsv41/ds4_main.cpp:2511-2518,2550`）。
- 値を省略して末尾に置くと `<option> needs a value` を標準エラーに出して終了コード 2 で終了します。末尾以外で次の引数がある場合、その引数を値として消費します（`src/dsv41/ds4_main.cpp:2511-2518`）。
- 複数回指定した場合は parser の走査順に上書きされ、最後の値が残ります（`src/dsv41/ds4_main.cpp:2511-2550`）。

## 実行時の動作

parser は値を `o.threads` に保存します。モデル初期化では `par = o.threads || tp > 1` とし、threads mode または `tp > 1` なら decode の並列経路を選びます。`--threads on` は GPU ごとの `Worker` host thread を起動する条件となり、window 処理でも各デバイスに担当 worker を作ります（`src/dsv41/ds4_model.cu:2713-2718,3784-3788`; worker の待機・job 実行は `src/dsv41/ds4_model.cu:963-1005`）。window の plan も `par` を並列 / async 経路の判定に使い、実行時は `forward_par` または `forward_serial` に分岐します（`src/dsv41/ds4_model.cu:13228-13235,14572-14579`）。

`--tp` との相互作用があります。既定の `tp` は 2 なので、既定状態では `--threads off` でも `tp > 1` によって `par` は true です。`--tp 1` のときは `--threads on` が `par` を true にします。GGUF では tensor parallel の幅 `tp` が weight block や head の分割条件に合わない場合に小さく補正されるため、実効 `tp` が指定値より小さくなることがあります（`src/dsv41/ds4_model.hpp:59-63`; `src/dsv41/ds4_model.cu:2693-2718`）。

prompt の chunk 経路は decode の `par` と別の条件も持ちます。`tp > 1` / `par` で有効になるほか、`--prefill-chunk` の指定や既定規則でも選ばれます。Metal build では `DS4_NO_CHUNKS` が無い場合に prompt chunk 経路を強制します（`src/dsv41/ds4_model.cu:2719-2727`）。chunk buffer の確保に失敗した場合、chunk サイズを縮め、さらに確保できなければ prompt を 16-token window 処理へ戻します。この fallback は stderr に警告を出します（`src/dsv41/ds4_model.cu:3550-3566`）。

## 適用条件と副作用

このオプションは `strata-dsv41` の引数 parser で受理され、GPU の group / layer 処理を構築するモデル経路で使われます（`src/dsv41/ds4_main.cpp:2550`; `src/dsv41/ds4_model.cu:2693-2718`）。GPU 数、実効 `tp`、build 条件、prompt buffer の確保可否によって並列経路の範囲が異なります。ソース上、`--threads` 自体にファイル変更や別プロセス起動の副作用は確認できません。

`--cpu-threads` は CPU lane の worker 数を指定する別設定です。`--threads` を CPU thread 数の指定として解釈しないでください（`src/dsv41/ds4_model.hpp:33-35,59-67`）。

## 出力とエラー

- 値の省略は stderr にエラーを出し、終了コード 2 です（`src/dsv41/ds4_main.cpp:2511-2518`）。
- `--threads` の値自体には不正値エラーがありません。未知の option は `unknown option ...` と usage を stderr に出して終了コード 2 ですが、これは parser 全般の経路です（`src/dsv41/ds4_main.cpp:2593-2599`）。
- chunk buffer を確保できない場合は stderr に fallback の警告を出し、prompt を window 処理にします（`src/dsv41/ds4_model.cu:3550-3562`）。

## 根拠

- `src/dsv41/ds4_main.cpp:118-123` — engine の引数形式。
- `src/dsv41/ds4_main.cpp:2511-2518,2548-2550,2593-2599` — 引数値の取得、`--tp` / `--threads` の解析、値省略と未知 option のエラー経路。
- `src/dsv41/ds4_model.hpp:33-35,59-67` — CPU lane thread 設定との違い、`tp` と `threads` の既定値と役割。
- `src/dsv41/ds4_model.cu:2693-2727,2777-2789` — 実効 tensor parallel 幅、decode / prompt の並列条件と chunk 設定。
- `src/dsv41/ds4_model.cu:963-1005,3784-3788,13228-13235,14572-14579` — GPU ごとの host worker と推論経路の選択。
- `src/dsv41/ds4_model.cu:3550-3566` — chunk buffer 確保失敗時の window fallback と警告。
