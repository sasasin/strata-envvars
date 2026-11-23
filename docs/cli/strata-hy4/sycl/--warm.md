# `strata-hy4-sycl --warm`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--warm` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

parser は `--warm` を受理して内部フラグを立てますが、その値は後で破棄され、モデルのロード、serve、生成、CPU expert の warm 処理には使われません。この revision では指定の有無で動作に差はありません。

## 使い方

```sh
# オプションの受理確認用の構文例。実行時に warm-up は行われない。
strata-hy4-sycl --native model.strata --tokens ids.txt --warm
```

## 値と既定値

値は不要です。既定値は `false` で、指定すると `true` になります。複数回指定しても同じ真偽値を設定するだけです。直後に別の値を置く構文ではなく、そのトークンは別の引数として処理されます。

## 実行時の動作

起動時に `warm` は `false` で初期化され、引数走査で `--warm` を見つけると `true` になります（`engine/src/hy4flash/sycl/sy_main.cpp:99,105-106,161`）。その後、serve 設定の組み立てにも通常推論の処理にも渡されず、通常経路では `engine/src/hy4flash/sycl/sy_main.cpp:318` で `(void)warm` として明示的に未使用扱いされています。したがって `--warm` は serve と通常推論のどちらでも処理効果を持ちません。

同じ SYCL ディレクトリには `CpuExperts::warm` の実装がありますが、CLI の `--warm` から呼び出される箇所はありません。確認できる呼び出しはテストコード内です（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:496-550`、`engine/src/hy4flash/sycl/hy4s_cpuexp_test.cpp:343,453`、`engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:75`）。

## 適用条件と副作用

オプション自体に条件分岐や副作用はありません。`--warm` があってもなくても、別の引数が実行経路を決めます。モデル指定がない通常起動は usage を `stderr` に出して終了コード 2 となります。未知の引数は `stderr` に `unknown arg <引数>` を出して終了コード 2 となり、serve モードでは加えて `stdout` に `ERR unknown flag <引数>` を出します（`engine/src/hy4flash/sycl/sy_main.cpp:190-197,215-219,250-254`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,105-106,161` — 内部フラグの初期値と `--warm` の引数処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,318-319` — serve 分岐では設定に含まれず、通常経路でも値を破棄すること。
- `engine/src/hy4flash/sycl/sy_main.cpp:190-197,215-219,250-254` — 未知引数とモデル未指定の場合の出力・失敗経路。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:496-550` と上記テスト呼び出し箇所 — CPU expert warm 実装は存在するが、CLI オプションの使用箇所ではないこと。
- 調査開始時の Strata checkout は `main` の commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`、作業状態は `## main...origin/main`（未コミット変更なし）。CLI help は実行していません。
