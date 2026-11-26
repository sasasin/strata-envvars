# `--gpu-only-full`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--gpu-only-full` |
| 別名 | なし |
| 値 | 取らない。指定すると boolean が `true` になる |

## 役割

通常の生成ループの代わりに、モデルの全層について GPU の `pre` と `post` graph を順に再生し、続けて LM head を実行して所要時間を計測する診断・測定モードです。CPU expert pool、token embedding、PLE、logits の readback、sampler を含む通常の token 処理は計測せず、結果を表示して終了します。そのため、通常生成 1 token の実時間ではなく、この経路が実行する GPU work の計測値です。

## 使い方

通常のモデル指定・入力引数に追加します（例は CUDA/HIP 系 `strata` の引数形式です）。

```sh
strata generate --pack /path/to/model-pack --tokens "1,2,3" --gpu-only-full
```

実際のモデルに対応する pack と token ID を指定してください。GPU backend の動作確認や測定の再実行は、この調査では行っていません。

## 値と既定値

- 引数 parser は `--gpu-only-full` を値なし flag として受理し、`o.gpu_only_full = true` にします。未指定時は構造体初期値の `false` で、この測定分岐に入りません。
- この option 自体に数値や文字列の validation はありません。値を後続引数として付ける構文も定義されていません。重複指定も同じ boolean を再度 true にするだけです。

## 実行時の動作

初期化と graph 準備を経てこの分岐に到達すると、doorbell を reset し、warm pass 1 回と計測対象 20 回について `session_replay_full` を呼びます。各 replay は `g.n_layers` 層を順に処理し、各層で `pre` の後に `post` graph を同じ stream に投入します。その後 LM head を実行します。層 replay と head のそれぞれで stream を同期して時間を分け、20 回の平均を計算します。出力は合計 ms/token と GPU-work tok/s、層合計・層あたり・LM head の ms で、正常終了コードは 0 です。

計測値は通常 decode の全処理時間を表しません。通常ループへ進まず早期 return するため、token embedding、PLE、logits 全体の host readback、NaN scan、sampling は含まれません。`--no-pool` を別途指定しなくてもこの測定分岐では pool の token 処理は実行されません。

## 適用条件と相互作用

- whole-model graph replay 用のため、`--layer-split` による multi-GPU 経路とは併用できません。該当条件は graph replay より前に拒否され、stderr に説明を出して終了コード 2 になります。
- `--no-capture` を指定すると全層 graph を capture しないため、この測定に必要な graph がありません。`--no-capture --no-pool --gpu-only-full` のように事前検査を通過する組合せでも、`session_replay_full` は未 capture として失敗し、stderr にエラーを出して終了コード 1 になります。
- `native_pack` のときも全層 graph capture は行われません。したがって、その経路でこの測定分岐を実行すると replay は成立しません。
- `--native-flash-attn-short` との併用は通常 decode loop を必要とするため拒否され、終了コード 2 です。
- `--graph-only` と同時に指定した場合は `graph-only` 分岐が先に実行され、そちらの結果を表示して終了します。`--gpu-only-full` の測定は行われません。
- 有効な測定では GPU graph の再生・同期を warm pass と 20 回行います。追加の測定結果ファイルを作成する処理は確認できません。

## 出力とエラー

- `session_replay_full` が失敗すると `strata generate: session_replay_full: ...` を stderr に出し、終了コード 1 で終了します。
- 層 replay の同期失敗時は `gpu-only-full layers faulted: ...`、LM head の実行失敗時は `gpu-only-full lm_head: ...`、head 同期失敗時は `gpu-only-full head faulted: ...` を stderr に出して終了コード 1 です。
- 条件違反（layer split、native flash-attn-short との併用）はそれぞれ理由を stderr に出し、終了コード 2 です。

## 根拠

- `engine/src/program/generate.cpp:845-855` — option の初期値 `false` と `gpu_only_full` フィールド。
- `engine/src/program/generate.cpp:3930-3936` — parser で値なし flag として受理し、boolean を true にする。
- `engine/src/program/generate.cpp:1389-1395` — help 表示上の測定説明と関連 flag。
- `engine/src/program/generate.cpp:5293-5307` — native flash-attn-short、multi-GPU layer split との拒否条件と終了コード。
- `engine/src/program/generate.cpp:10544-10554` — `--no-capture` 時と native pack の条件では graph capture を行わない経路。
- `engine/src/program/generate.cpp:10917-10956` — warm pass、20 回の replay/head/sync、計時・標準出力・早期終了。
- `engine/src/program/generate.cpp:10877-10905` — `--graph-only` 分岐が先に評価され、先に return すること。
- `engine/src/core/session.cpp:302-324` — CUDA/HIP 側で capture 状態・全層数・post graph を検証し、各層の pre/post を順に投入する実装。
- `engine/sycl/src/program/generate.cpp:1971-1975`, `engine/sycl/src/program/generate.cpp:2711-2721`, `engine/sycl/src/program/generate.cpp:6372-6436`, `engine/sycl/src/core/session.cpp:358-408` — SYCL parser、拒否条件、計測・出力・replay 実装も同じ用途を持つ。

調査範囲は上記 checkout の Strata 所有ソースです。実際の GPU backend ごとの時間・故障内容や、特定のモデルで全層 graph が capture 可能かは実行して確認していません。
