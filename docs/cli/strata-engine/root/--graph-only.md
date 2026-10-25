# `--graph-only`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--graph-only` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

層ごとの `pre` CUDA graph を連続 replay し、その実行時間を測るための測定モードです。通常の推論結果を生成するモードではありません。`post` graph と LM head を省くため、エンジン全体の GPU 処理時間や GPU 下限値として扱えません。全 GPU 処理を含む測定には、ソースの usage が案内する `--gpu-only-full` を参照してください（`src/program/generate.cpp:974-977,7315-7324`）。

## 使い方

モデルと token 入力など、通常の `strata` 実行に必要な引数と合わせて指定します。

```sh
strata --pack /path/to/model.gguf --tokens 1 --graph-only
```

この例のパスと token ID は形式を示すものです。実際には読み込み可能なモデルと、そのモデルに適した入力を指定してください。parser はこのフラグに値を要求しません（`src/program/generate.cpp:2416-2420,2504-2509`）。

## 値と既定値

`Options::graph_only` は `false` で初期化され、`--graph-only` を指定すると `true` になります。値の変換や個別 validation はなく、同じフラグの複数回指定も同じ真偽値を設定するだけです（`src/program/generate.cpp:516,2508`）。省略時はこの測定分岐に入りません。

## 実行時の動作

測定分岐では doorbell を reset し、最初に `session_replay` を1回実行して warm-up します。その後、同じ replay を20回実行し、経過時間を20で割って token あたりのミリ秒として表示します。さらに層あたりのミリ秒も表示して `0` で終了します。表示する速度は `1000 / ms` による測定値で、性能の保証値ではありません（`src/program/generate.cpp:7285-7312`）。

ここで呼ぶ `session_replay` は `pre` graph のみを再生します。`post` graph 群（共有 expert、combine、2つ目の `gr_write`）と LM head は対象外で、CPU expert pool も走りません（`src/program/generate.cpp:7315-7324`）。モデル・セッション・graph の準備を済ませた後でこの分岐に入るため、GPU メモリーや処理時間を使います（graph capture: `src/program/generate.cpp:6952-6963`、測定: `7285-7308`）。

## 適用条件と副作用

- `--native-flash-attn-short` と同時に指定すると parser 後の validation が拒否し、stderr に通常 decode loop が必要とのエラーを出して終了コード `2` を返します（`src/program/generate.cpp:3378-3385`）。
- `--gpu-stages` も指定した場合、graph-only 分岐より前に stage 測定の分岐が処理され、その測定後に終了します。したがって `--graph-only` の replay は行われません（`src/program/generate.cpp:7137-7148,7277-7282,7285`）。
- `--no-capture` を指定すると graph capture 自体が省略されます。また native pack では per-layer graph を capture しません（`src/program/generate.cpp:6952-6963`）。これらと `--graph-only` の組み合わせを専用に拒否する validation はありませんが、`session_replay` は capture がない場合に `session_replay: not captured` を返します。そのため warm-up でこのエラーを stderr に出して `1` で終了します（`src/core/session.cpp:292-295`、呼び出し元: `src/program/generate.cpp:7285-7291`）。
- `--layer-split` の場合、capture には `split_at[0]` が渡されて CUDA 0 側の層範囲だけを capture します（`src/program/generate.cpp:6954-6959`）。`session_replay` は capture した層数が `g.n_layers` と異なると `session_replay: not captured` を返すため、通常の複数 stage split では warm-up が失敗し、stderr にエラーを出して `1` で終了します（`src/core/session.cpp:292-295`、呼び出し元: `src/program/generate.cpp:7285-7291`）。この組み合わせは専用 validation による事前拒否ではありません（multi-GPU validation の対象: `src/program/generate.cpp:3386-3392`）。

ファイル作成・ネットワークアクセスの副作用はこの分岐では確認できません。GPU の graph replay と同期を実行し、測定値を標準出力へ出します。

## 出力とエラー

成功時は標準出力に `pre graphs only` の token あたり時間、GPU work 換算の tok/s、層あたり時間を表示します（`src/program/generate.cpp:7308-7312`）。

warm-up の `session_replay` が失敗した場合は詳細を stderr に出し、CUDA 同期失敗時は `session_replay warm faulted` を出して、いずれも `1` で終了します。20回の replay が失敗した場合も詳細を stderr に出して `1` で終了します。最後の `cudaDeviceSynchronize` が失敗した場合は CUDA error 文字列を stderr に出して `1` で終了します（`src/program/generate.cpp:7288-7306`）。

## 根拠

- `src/program/generate.cpp:516,2508` — false 既定値と parser action。
- `src/program/generate.cpp:974-977` — usage に記載された測定範囲と `--gpu-only-full` との区別。
- `src/program/generate.cpp:3378-3392` — 相互作用と multi-GPU 測定フラグの validation。
- `src/program/generate.cpp:6952-6963` — graph capture の条件、および native pack / layer split 時の範囲。
- `src/core/session.cpp:205-226,284-289,292-300` — capture 対象層数と replay の事前条件、失敗診断。
- `src/program/generate.cpp:7285-7312` — warm-up、反復回数、同期、出力、終了経路。
- `src/program/generate.cpp:7315-7324` — `pre` のみで `post` と LM head を省略すること。

調査日: 2026-10-25。既存ビルド済み CLI の `--help` は実行していません。記述は同一 revision の parser、usage 文字列、実行経路を根拠にしています。
