# `--prof2`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--prof2` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Hy4-Flash の CUDA/HIP runner で、ラベル付き処理区間ごとの GPU event 時間を集計して表示する診断フラグ。通常の prefill/decode 時間だけでは区別できない処理区間の内訳を調べる用途に使う。計測には GPU event の作成・記録と stream 同期が入り、通常実行に追加の計測コストがある。

## 使い方

```sh
# tokens.txt の入力で生成し、prefill と decode の区間別 GPU 時間を表示する
strata-hy4 --model Model.strata --tokens tokens.txt --gen 16 --prof2
```

`--model` と `--tokens` は通常の推論に必要な入力であり、`--prof2` 自体は引数を受け取らない。

## 値と既定値

`--prof2` が指定されると parser の boolean `prof2` が `true` になり、未指定時は `false`。数値などの値は受け取らない。parser に範囲検証はなく、直後に別の引数があれば次のループで独立した CLI 引数として処理される。未知の引数は `unknown arg <引数>` を stderr に出し、終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 496-505`）。

## 実行時の動作

- parser が立てたフラグを `Runner::prof2` に渡す（`engine/src/hy4flash/run/hy4_main.hip.cpp:496-497, 692-699`）。
- ラベル付き区間ごとに GPU stream 上の hipEvent ペアを記録する。処理区間の終了後、`pflush()` が stream を同期し、event の経過時間をラベル別に累積する（`engine/src/hy4flash/run/hy4_graph.hip.h:1284-1315`）。
- 集計は `[prof2 <区間>] per-step ms by section` の見出し、各ラベルの 1 step あたり ms と calls/step、合計を stderr に出す。prefill はチャンク数で割り、通常 decode は生成 step 数で割る。DFly2 の speculative decode 分岐では `spec total (all steps)` として全体値を出す（`engine/src/hy4flash/run/hy4_graph.hip.h:1317-1331`; `engine/src/hy4flash/run/hy4_main.hip.cpp:785-788, 1000-1011, 1075-1079`）。
- 既定で CUDA Graph が使える構成でも、`T <= 8` の `forward_chunk` は `--prof2` 指定中に graph 経路を通らず通常経路へ進む。計測区間を維持するための分岐で、実行経路・所要時間に影響し得る（`engine/src/hy4flash/run/hy4_graph.hip.h:3390-3398`）。
- `--prof` と同時指定も拒否されない。`--prof` は別の `prof` フラグとして設定され、Engram 読み込み時の probe など独自の処理を行う。`--prof2` 単独ではその probe 条件は有効にならない（`engine/src/hy4flash/run/hy4_main.hip.cpp:351, 496-497, 731-746`）。

## 適用条件と副作用

この文書の対象は索引の `strata-hy4`（CUDA/HIP、`engine/src/hy4flash/run/hy4_main.hip.cpp`）である。同名フラグがある Metal / SYCL runner は別の tool scope で、ここでは扱わない（`docs/cli/README.md:1277-1283, 1358-1363, 1452-1459`）。

フラグを指定すると計測区間ごとの event を作成・記録し、集計のたびに GPU stream を同期するため、診断値は計測を有効にした実行の値である。また、前述のとおり小さい `T` の CUDA Graph 経路が抑止される。`--prof2` 自体がファイルを書き出す処理は確認できない。通常推論の出力ファイルは別の処理条件による。

## 出力とエラー

集計結果は `fprintf(stderr, ...)` による stderr 出力。値の validation error や専用の警告は parser にない。GPU event の API エラー時の具体的な出力・終了動作は共通 `HCK` 実装側に依存するため、この調査では個別のエラー文言を特定していない。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351, 496-497, 692-699` — boolean 既定値、parser 登録、Runner への引き渡し。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1284-1315` — GPU event の記録、同期、ラベル別累積。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1317-1331` — stderr レポートの内容と集計単位。
- `engine/src/hy4flash/run/hy4_graph.hip.h:3390-3398` — CUDA Graph 経路を選ぶ条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:785-788, 1000-1011, 1075-1079` — prefill・speculative decode・通常 decode でのレポート呼び出し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 498-505` — 値なし parser、未知引数の失敗経路。
- `docs/cli/README.md:1277-1283` — `strata-hy4` と root scope の索引上の位置づけ。
