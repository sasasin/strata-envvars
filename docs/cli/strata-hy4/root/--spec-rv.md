# `strata-hy4 --spec-rv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、トップレベル） |
| オプション | `--spec-rv` |
| 別名 | なし |
| 値 | 整数。候補数として使われ、正の値は最大1024に制限される。0以下は全語彙経路を選ぶ。 |

## 役割

DFly2 speculative decoding のドラフト段階で、各予測位置の語彙候補を何個に絞って補正スコアを評価するかを指定します。正の値なら target の `lm_head` によるベース logits から top-N を選び、その候補だけを hidden correction と組み合わせて評価します。0以下なら候補を絞らず、各位置で全語彙の logits を計算します。これはドラフト候補生成の設定であり、target 側の検証トークン数を指定するものではありません。

## 使い方

```sh
# DFly2 を明示してオフライン生成し、各ドラフト位置の候補数を128にする
strata-hy4 --native model.strata --tokens prompt.txt --gen 64 --draft dfly2 --spec-rv 128

# 候補削減を無効にし、全語彙 logits を使う
strata-hy4 --native model.strata --tokens prompt.txt --gen 64 --draft dfly2 --spec-rv 0
```

オフライン実行の `--draft` は既定値 `auto` で、ソース上の説明では DFly2 は `--serve` 時に自動選択され、CLI の通常実行では無効です。そのため、オフライン生成でこの値を適用するには `--draft dfly2` が必要です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701-714`）。

## 値と既定値

- `--spec-rv` の値は `atoi` で `SpecCfg::rv` に変換されます。既定値は `256` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:412`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-30`）。
- 値の範囲や数値形式を検証する処理は parser にありません。数値でない文字列は `atoi` の変換結果 `0` となり、全語彙経路を選びます。負数も後段の `N > 0` 判定を通らず同経路になります。
- 値を省略すると `nxt()` が `ERR --spec-rv needs a value` を標準出力へ出し、flush 後に終了コード `2` で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383, 412`）。
- 複数回指定時は parser が都度 `scfg.rv` に代入するため、最後に現れた値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383, 412`）。

## 実行時の動作

`Spec` は設定値を `DFly2::rv` に渡します。DFly2 は `N = min(rv, 1024)` とし、`N > 0` の場合はドラフト位置ごとに base logits の top-N 候補を抽出し、候補だけを hidden correction と組み合わせて採点します。したがって指定値が1024を超えても候補数は1024です（`engine/src/hy4flash/run/hy4_spec.hip.h:74-95`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:806-810, 1028-1034`）。

`N <= 0` では候補 top-N の計算を行わず、各ドラフト位置について全語彙サイズの `lm_head` logits を計算してホスト側へコピーします（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1040-1041, 1098-1108`）。値が変えるのはこのドラフト候補評価経路です。通常の DFly2 生成は `--draft dfly2` かつ `--gen` が正の場合に spec モードになります（`engine/src/hy4flash/run/hy4_main.hip.cpp:700-701, 992-1000`）。

`--serve` では `SpecCfg` がサーバー設定へ渡されます。サーバーはドラフトが有効で、chunk が8以上、かつ DFly2 初期化に成功した場合に `Spec` を作ります。chunk が8未満の場合や初期化失敗時はドラフターなしで続行するため、その場合 `--spec-rv` の値は使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-560`、`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。

## 適用条件と副作用

- CUDA/HIP の `strata-hy4` parser に属する設定です。この調査では Metal および SYCL の同名オプションは対象外です。
- DFly2 を使わない実行では値は受理されても効果がありません。通常実行では `--draft dfly2` で DFly2 を選びます。serve では `--draft auto` が drafter を使う場合がありますが、モデルに drafter が含まれることなど初期化条件に依存します（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701-714`、`engine/src/hy4flash/run/hy4_serve.hip.h:321-341`）。
- 正の値は top-N による候補削減を行い、0以下は全語彙 logits を各ドラフト位置で扱うため、計算量と一時データ量に影響します。性能差の大きさはソースだけからは確定できません。
- 特別なファイル出力や `--spec-rv` 固有の警告は確認できません。通常の生成・serve の出力は各実行経路に従います。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-364, 377-383, 408-414` — `draft` と `SpecCfg` の既定値、値取得、parser 定義、値省略時の出力と終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-560, 700-714, 992-1011` — serve への設定引き渡し、オフラインの spec モード条件、生成経路。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30, 74-95` — `rv` の既定値と DFly2 への設定引き渡し。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:806-810, 1028-1034, 1040-1041, 1098-1108` — top-N 候補抽出と全語彙 logits 経路。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` — serve で drafter を使う条件と `Spec` の生成。
