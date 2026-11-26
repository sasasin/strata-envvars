# `--graph-only`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数） |
| オプション | `--graph-only` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常の生成ループの代わりに、捕捉済みの各層の `pre` graph だけを GPU で replay し、その時間を測定します。`post` graph と LM head は含まれないため、モデル全体の GPU 処理時間や真の per-token GPU floor を測るものではありません。より全体に近い測定には `--gpu-only-full` が別途あります（ただし両方を指定した場合は `--graph-only` の分岐が先に実行されます）。

## 使い方

```sh
strata --pack /path/to/pack --tokens "1,2,3" --graph-only
```

`--tokens` にはこのビルドが要求する token ID 列を指定します。実際の pack と GPU 環境を用意して実行してください。CLI 使用法は `engine/src/program/generate.cpp:1208-1214`、必須 token 入力の検査は同ファイル `:5002-5007` にあります。

## 値と既定値

値を取りません。指定されると `graph_only` が `true` になり、省略時は `Options` の初期値 `false` のままです。重複指定も同じ bool を `true` にするだけで、別の値規則や重複検査はありません（`engine/src/program/generate.cpp:851-855,3930-3935`）。SYCL 実装も同じ初期値と parser 分岐です（`engine/sycl/src/program/generate.cpp:529-539,1969-1974`）。

## 実行時の動作

通常の非 native pack では、`--no-capture` が指定されていないときに session graph を捕捉します。`--graph-only` の分岐では doorbell を reset し、warm pass を1回実行した後、`session_replay` を20回実行して同期し、経過時間の平均を `ms per token`、`ms per layer`、GPU work 換算の `tok/s` として標準出力に出します。その後 `return 0` で終了するため、通常の生成処理には進みません（`engine/src/program/generate.cpp:10544-10554,10877-10904`）。SYCL 版も同じ warm pass・20 replay・表示形式です（`engine/sycl/src/program/generate.cpp:6318-6359`）。

この測定は `pre` graph のみです。ソースは `gr.execs[l]` の replay が `post` graph（shared expert、combine、2つ目の `gr_write`）と LM head を省くと説明し、これらを含む全体測定として `--gpu-only-full` を案内しています（`engine/src/program/generate.cpp:10907-10917`）。

## 適用条件と副作用

- graph を捕捉しない `--no-capture`、または graph を作らない native pack では、捕捉済み graph を用意する通常経路から外れます。`--graph-only` 専用の事前 validation は見当たらず、その条件での成功動作は保証できません（graph の生成条件: `engine/src/program/generate.cpp:10544-10554`）。
- `--gpu-stages` の処理分岐は `--graph-only` より前にあるため、両方を指定した場合は stage 計測側で終了し、graph-only の測定は行われません（SYCL: `engine/sycl/src/program/generate.cpp:6170-6179,6318`）。
- `--native-flash-attn-short` との併用は通常 decode loop が必要として拒否され、標準エラーに理由を出して終了コード 2 になります（`engine/src/program/generate.cpp:5293-5299`）。
- 本オプション自身によるファイル出力はありません。GPU graph の warm pass と replay を実行します。GPU または replay の失敗時は標準エラーに `session_replay` の失敗を出し、終了コード 1 で終了します（CUDA/HIP: `engine/src/program/generate.cpp:10880-10897`、SYCL: `engine/sycl/src/program/generate.cpp:6321-6353`）。

## 出力とエラー

成功時は標準出力に `pre graphs only` の計測値を表示します。warm replay、通常 replay、同期が失敗すると標準エラーにエラーを表示して終了コード 1 になります。値を取らないため、本フラグ固有の値 validation はありません。未知の引数は一般 parser が usage とともに標準エラーへ出し、終了コード 2 にします（`engine/src/program/generate.cpp:4268-4274`）。

## 根拠

- `engine/src/program/generate.cpp:851-855` — option state と既定値。
- `engine/src/program/generate.cpp:1391-1394,3930-3935` — help 文言と parser 登録。
- `engine/src/program/generate.cpp:5293-5299,10544-10554,10877-10904,10907-10917` — validation、graph 捕捉条件、計測分岐、測定範囲。
- `engine/sycl/src/program/generate.cpp:529-539,948-951,1969-1974,6170-6179,6318-6359,6362-6372` — SYCL 側の parser と同等の処理、先行する stage 分岐。
- `engine/src/program/generate.cpp:4268-4274` — unknown argument の出力と終了経路。
