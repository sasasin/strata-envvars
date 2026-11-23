# `strata-hy4 --prof`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP の root） |
| オプション | `--prof` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は無効 |

## 役割

CUDA/HIP 版 `strata-hy4` のオフライン推論で、prefill と decode の層処理を Engram、attention、MLP/MoE などの区分に分け、処理時間を標準エラーへ出します。GPU stream の同期を計測区間に挿入するため、計測時は通常実行と処理経路が変わります。また Engram が有効な場合は、推論前にランダムページ読み出しのプローブも行います（`engine/src/hy4flash/run/hy4_main.hip.cpp:731-746`、`engine/src/hy4_graph.hip.h:3429-3452`）。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt.ids --gen 16 --prof
```

`--model` でモデルを指定し、`--tokens` で入力 token ID ファイルを渡すオフライン実行の例です。`--prof` 自体には引数がありません。CLI の使用形式とモデル指定がない場合の usage エラーは `engine/src/hy4flash/run/hy4_main.hip.cpp:613-616`、各引数の解析は同 `:401-405`、`:483-497` にあります。

## 値と既定値

`--prof` は存在すれば `prof = true` にするフラグで、値・範囲・数値 validation はありません。初期値は `false` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:351-352,496`）。繰り返し指定しても同じ真偽値を設定します。別名は定義されていません。

## 実行時の動作

parser が立てた値は `Runner` の `r.prof` に渡されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-699`）。層ごとの Engram、attention、MLP/MoE の実行前後で GPU stream を同期し、その間の wall-clock 時間を累積します。Engram の区分は該当層で Engram が有効な場合に処理され、attention は sliding-window と sparse に分け、MLP は第0層を `mlp0`、他層を `moe` として集計します（`engine/src/hy4_graph.hip.h:3429-3448`）。prefill 後と decode 後に `[prof prefill]` / `[prof decode]` の行を標準エラーへ出し、報告後に累積値をゼロへ戻します（同 `:3449-3452`、`engine/src/hy4flash/run/hy4_main.hip.cpp:783-789,1075-1079`）。

`--prof2` は別の GPU event による区分計測として独立に解析されます。同時指定も可能ですが、`--prof` の wall-clock 区分と `--prof2` の GPU event 集計は異なる計測です（`engine/src/hy4flash/run/hy4_main.hip.cpp:496-497,697-699`、`engine/src/hy4_graph.hip.h:1284-1329`）。

## 適用条件と副作用

- 対象は索引上の CUDA/HIP root parser `engine/src/hy4flash/run/hy4_main.hip.cpp` です。Metal と SYCL には別 parser と別 scope があり、この文書ではそれらの `--prof` の挙動を扱いません（`docs/cli/README.md` の `strata-hy4` 節、`engine/src/hy4flash/run/hy4_main.hip.cpp:496`）。
- 通常の offline 経路では `--prof` が `Runner` に伝わります。一方 `--serve` は `Runner` 作成前に serve 用設定を渡して終了するため、このフラグは serve 側へ渡されず、そこでの効果はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,692-699`）。`--load-only` や `--info` も Runner の実行経路より前に終了します（同 `:389-392,507,658-665`）。
- Engram がロード済みなら、計測出力に先立ち、固定 20,000 件のランダムな 4 KiB ページ読み出しを実施し、16 worker・queue depth 8 で速度と成否を標準エラーへ出します。probe 用バッファを確保して Engram ファイルを読みます。Engram が無効または未ロードならこの probe は行われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:731-746`。`--no-engram` の値は `:493,703-705`）。
- 小さい chunk の CUDA graph 経路は `!prof` を条件に含むため、`--prof` 有効時にはその graph 経路へ入りません（`engine/src/hy4_graph.hip.h:3391-3397`）。また、層処理ごとの stream 同期が追加されるため、計測値はこのオプションを付けない実行と同一条件の処理時間ではありません（同 `:3429-3442`）。

## 出力とエラー

`[prof prefill]` と、decode を実行した場合の `[prof decode]` は標準エラーに出ます。Engram がロード済みなら `[engram-probe]` も標準エラーに出力され、読み出し件数・所要時間・pages/s・MB/s・`ok`・エラー文字列を含みます（`engine/src/hy4_graph.hip.h:3449-3452`、`engine/src/hy4flash/run/hy4_main.hip.cpp:731-746,785-789,1075-1079`）。このフラグ固有の入力 validation エラーや終了コード分岐は parser・計測経路にありません。モデル初期化や forward など他の実行エラーは別経路で返されます（同 `:703-705,759-763`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351-352,496-497` — `prof` の初期値、`--prof` / `--prof2` の parser 定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,692-699` — serve 経路が先に分岐することと、offline Runner への値の受け渡し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:731-746,785-789,1075-1079` — Engram probe および prefill/decode 後の計測レポート。
- `engine/src/hy4_graph.hip.h:3391-3397,3429-3452` — graph 経路の条件、stream 同期による区分計測、出力と累積値の初期化。
- `engine/src/hy4_graph.hip.h:1284-1329` — 別オプション `--prof2` の GPU event 集計。
