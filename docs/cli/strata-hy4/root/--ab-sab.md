# `strata-hy4 --ab-sab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル、CUDA/HIP） |
| オプション | `--ab-sab` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--ab-sab` は、オフラインの `--ab` 比較において、通常の DFly2 推測デコードに加えて、draft token をランダムな ID に置き換えた比較を実行するフラグです。推測デコード制御器が draft の受理率がほぼ 0 の状況でどう動くかを計測するテスト用経路であり、通常の生成動作を選ぶための設定ではありません。ソースの `SpecCfg::sabotage` にも test only と記されています（`engine/src/hy4flash/run/hy4_spec.hip.h:26-28`）。

## 使い方

モデルと prompt token ファイルを用意し、例えば次のように `--ab` と併用します。

```sh
strata-hy4 --model model.strata --tokens prompt-ids.txt --draft dfly2 --gen 128 --ab 3 --ab-sab
```

この例では、3 ラウンドそれぞれで通常の greedy decode と DFly2 decode を比較した後、ランダム draft を使う DFly2 の計測を追加します。実際にモデルをロードして GPU 推論を行うため、help 表示や設定確認だけの例ではありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-621, 632-659, 914-990`）。

## 値と既定値

値は不要です。引数解析時に `ab_sab` は `false` で初期化され、`--ab-sab` を指定すると `true` になります。複数回指定しても同じ真偽値を設定するだけです（`engine/src/hy4flash/run/hy4_main.hip.cpp:373-374, 431-433`）。

このフラグには個別の値検証はありません。効果が現れるのは `ab_rounds > 0 && spec_mode` の分岐内だけで、`spec_mode` は `--draft dfly2`、`--gen` の値が正、かつ `--dfly-alloc-only` なしの場合に成立します（`engine/src/hy4flash/run/hy4_main.hip.cpp:431-433, 701, 914-915`）。したがって `--ab-sab` 単独、`--ab` なし、`--ab` が 0 以下、または上記の推測デコード条件を満たさない実行では、追加の sabotage 計測は行われません。

値を取らないため、直後のトークンを `--ab-sab` の値としては消費しません。後続トークンが別の認識済みオプションでなければ `unknown arg` として stderr に出し、終了コード 2 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 498-505`）。

`--ab` の値は `atoi` で整数化され、正の値がラウンド数として使われます。数値でない値は `atoi` により 0 となるため比較分岐を有効にしません。`--ab` の既定値は 0 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:373, 431, 914, 937`）。

## 実行時の動作

有効な比較分岐では、各ラウンドで同じ prompt 状態を復元し、まず通常 decode、次に `scfg` の設定による DFly2 decode を実行します。`--ab-sab` が有効なら、さらに prompt 状態を復元し、`scfg` を複製して `sabotage = true` にした `Spec` を実行します。その結果として、通常 decode の速度を基準に、ランダム draft を使った DFly2 の速度、speedup、backoff・probe・plain-mode の回数を表示します（`engine/src/hy4flash/run/hy4_main.hip.cpp:937-990`）。

ランダム draft の生成は `Spec::run` 内で行われます。xorshift 状態を更新して各 draft token を `xs % 100000` で作り、confidence を `0.9` に設定します。また sabotage 時は draft tree の分岐探索を無効にします（`engine/src/hy4flash/run/hy4_spec.hip.h:310, 316-333`）。

## 適用条件と副作用

- この計測は `--serve` のサーバーモードでは実行されません。`--serve` はオプション解析後にサーバー経路へ進み、`--ab` 比較を行うオフライン処理へ到達しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:397, 544-611`）。
- `--draft` の既定値は `auto` ですが、オフライン実行で `spec_mode` を成立させるには明示的に `--draft dfly2` が必要です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701`）。
- 有効時は通常の比較に加えて各ラウンドで推測デコードをもう一度実行するため、実行時間と GPU 計算量が増えます。モデルのロードや prompt の prefill も行われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-659, 749-790, 975-989`）。
- 比較結果は stdout の `[ab]` 行と `[ab-sab]` 行に出力され、通常の DFly2 統計は stderr に報告されます。`--ab-sab` の結果をファイルへ保存する処理は、この比較分岐にはありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:970-989`）。

## 出力とエラー

通常 DFly2 比較の `Spec::run` が `finish == "error"` を返した場合、stderr に `spec: <理由>` を出して終了コード 1 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:959-966`）。一方、追加の sabotage 実行では `fin2` と `e3` を受け取りますが、呼び出し側はそれらを検査せず、計測行を出力します（`engine/src/hy4flash/run/hy4_main.hip.cpp:980-989`）。`--ab-sab` 自体に固有の入力エラーや警告経路は確認できませんでした。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373-374, 431-433` — フラグの初期値と parser 定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701, 914-937` — DFly2 比較の適用条件、ラウンド数、比較前の状態復元。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:975-990` — sabotage 用設定を作る呼び出し、計測と出力。
- `engine/src/hy4flash/run/hy4_spec.hip.h:26-28, 310, 316-333` — sabotage の用途、ランダム draft の生成と confidence 設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611` — `--serve` 時の別経路。
