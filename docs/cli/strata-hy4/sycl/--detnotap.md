# `--detnotap`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（root） |
| オプション | `--detnotap` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--detcheck` による決定性確認で、各反復時に層ごとの中間値を記録する tap を無効にする。中間値の比較表示を省きつつ、反復間の logits のビット単位比較は残す。単独で指定した場合は通常の推論結果を変える処理はない。

## 使い方

```sh
strata-hy4-sycl --model model.strata --tokens token-ids.txt --detcheck 4 --detnotap
```

モデルと入力 token ID を読み込み、同じ1 token の forward を4回行って比較する例。`--detnotap` は `--detcheck` と組み合わせて使う。

## 値と既定値

値を取りません。パーサーがこの引数を見つけると内部フラグを `true` にし、指定しない場合は `false` のままです。引数値の validation はありません。`--detnotap VALUE` のように値を後置すると、その文字列は別の引数として処理され、認識できなければ `unknown arg` で終了コード 2 になります（`engine/src/hy4flash/sycl/sy_main.cpp:97-99, 107-116, 173, 190-197`）。

## 実行時の動作

`--detcheck N` が正の値で指定されると、入力 token 列から greedy に次 token を選び、同じ token・位置・KV prefix で1 token の forward を N 回実行します（`engine/src/hy4flash/sycl/sy_main.cpp:409-438`）。この反復中、`--detnotap` があると `Runner::tap` を null にし、層ごとの値を `rep` 配列へ記録しません。指定がない場合は各反復の tap を記録して比較します（`engine/src/hy4flash/sycl/sy_main.cpp:429-435`）。

`--detcheck` が2以上の場合、logits はどちらの場合もホストへ読み出して反復間比較され、差分数と `DETCHECK REPEATABLE` / `DETCHECK NONDETERMINISTIC` の結果は出力されます。値が1の場合は比較ループがなくても `DETCHECK REPEATABLE` と表示されます。`--detnotap` 指定時は tap 差分がない場合の `repeat ...` 行を省略し、logits に差がある場合だけその行を表示します（`engine/src/hy4flash/sycl/sy_main.cpp:435-458`）。tap が有効な場合、tap 関数は値を GPU からホストへコピーして保存します（`engine/src/hy4flash/sycl/sy_graph.h:761-779`）。

`--detcheck` が正でなければ、このフラグが使われる分岐に入りません。引数の処理は `--detcheck` の後に独立して行われるため、両方を指定したときは `--detnotap` の有無にかかわらず detcheck 分岐が実行されます。detcheck が有効な通常推論経路では VRAM static 設定も有効になります（`engine/src/hy4flash/sycl/sy_main.cpp:170-174, 298-300, 409-410`）。

## 適用条件と副作用

このフラグの効果は、SYCL runner の `--detcheck` 分岐に限られます。`--wincheck` 分岐は別に層 tap を設定するため、`--detnotap` は同分岐の tap を無効にしません（`engine/src/hy4flash/sycl/sy_main.cpp:409-410, 459-497`）。

tap を無効にすると中間値のホストコピーと保存がなくなります。一方、tap が無効な場合に SYCL graph 実行を許可する条件が runner にあるため、detcheck 反復の実行経路も tap 有効時と異なる可能性があります（`engine/src/hy4flash/sycl/sy_graph.h:1387, 1439`）。性能差や結果への影響量はこのコード調査では測定していません。

## 出力とエラー

`--detnotap` 自体に専用のエラー経路はありません。detcheck が正常に完了すると `detcheck pos=... repeats=...` と最終判定を標準出力へ出します。logits に差があれば反復ごとの差分行も出ます。forward に失敗した場合は `forward: ...` を標準エラーへ出し、終了コード 1 で戻ります（`engine/src/hy4flash/sycl/sy_main.cpp:431-440, 453-458`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:97-99, 107-116, 170-174` — `detnotap` の初期値と値を取らない引数解析。
- `engine/src/hy4flash/sycl/sy_main.cpp:298-300, 409-458` — detcheck の適用条件、反復、tap 記録の切替、logits 比較、表示。
- `engine/src/hy4flash/sycl/sy_main.cpp:459-497` — `--wincheck` 分岐が detcheck と別に tap を設定すること。
- `engine/src/hy4flash/sycl/sy_graph.h:761-779, 1387, 1439` — tap のホストコピーと graph 実行条件。
