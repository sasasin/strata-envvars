# `--no-ple`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata` |
| オプション | `--no-ple` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

PLE（Per-Layer Embedding）層を明示的に無効にする診断用の ablation フラグです。ソースは通常推論の既定動作ではないと位置付け、無効化時のトークンはモデル本来のものではなく、A/B 測定に限って有用だと stderr に表示します（`src/program/generate.cpp:437`, `4177-4180`）。

## 使い方

通常 parser 経路で PLE 無効化を診断する例です。`--tokens` は tokenizer を介さない、カンマ区切りの事前 token ID 列です。

```sh
strata --pack /models/pack --tokens 1,2,3 --no-ple
```

エンジンの usage は `--pack DIR`、`--tokens LIST` と `--no-ple` を案内しています（`src/program/generate.cpp:806-818`）。

## 値と既定値

- 値や引数は不要です。parser がこの文字列を見つけると `no_ple` を `true` にします。既定値は `false` で、同じ指定を複数回しても真のままです（`src/program/generate.cpp:436-437`, `2413-2425`, `2473-2475`）。
- PLE を有効にする通常経路では `--ple-gguf PATH` が必須です。`--no-ple` を指定するとこの必須条件が免除され、`--ple-gguf` を省略できます（`src/program/generate.cpp:3290-3300`）。

## 実行時の動作

- `--no-ple` を指定し `--ple-gguf` を指定しないと、PLE 表の open、PLE 重みの接続、PLE 用 GPU buffer の確保を行うブロックを通らず、PLE を未初期化のままにします（`src/program/generate.cpp:4023-4033`, `4161-4180`）。通常の token 処理は `ss.ple.ready()` の場合にだけ PLE token の発行・完了処理を呼ぶため、この状態ではその処理もスキップされます（`src/program/generate.cpp:15891-15910`）。
- これは出力品質を保つ通常推論向けの選択肢ではありません。エンジン自身が「以下の tokens はこのモデルのものではない」「A/B measurement のみ」と警告しています（`src/program/generate.cpp:4177-4180`）。性能向上や同等品質を保証する根拠はこのソース範囲から確認できません。
- `--ple-gguf` と同時に指定すると、相互排他として拒否されます。PLE を使わない指定では PLE 表パスを渡さないでください（`src/program/generate.cpp:3290-3293`）。
- `--native` は PLE を必須とする別条件があり、指定時は `--no-ple` または PLE shard を特定できない状態を stderr に出して拒否します。そのため `--no-ple` と `--native` は併用できません（`src/program/generate.cpp:3247-3261`）。
- `--native-ple-postops` と `--native-ple-key` も PLE を必要とし、併用時は拒否されます（`src/program/generate.cpp:3294-3297`, `3403-3405`）。

## 適用条件と副作用

- 対象は CMake の `strata` 実行ファイルが使う `src/program/generate.cpp` の通常引数 parser です（`CMakeLists.txt:759-762`, `src/program/generate.cpp:2413-2425`, `2473-2475`）。
- `--native` / `--model` で Qwen3.6-35B-A3B が選ばれる build では、通常 parser に入る前に `src/qwen35` 実装へ引数全体を転送します（`src/program/generate.cpp:2393-2407`）。この調査では `src/qwen35` に `--no-ple` の parser または使用箇所を確認できなかったため、その別実装での受理や効果は断定しません。
- PLE 表の読込みと PLE 用 GPU buffer の確保を避けます。起動時に `PLE OFF by explicit --no-ple diagnostic request` と、モデル本来の token ではない旨を stderr に出します（`src/program/generate.cpp:4033-4054`, `4177-4180`）。

## 出力とエラー

- `--no-ple --ple-gguf PATH`: `strata generate: --no-ple and --ple-gguf are mutually exclusive` を stderr に出し、終了コード `2`（`src/program/generate.cpp:3290-3293`）。
- `--native --no-ple`: `strata generate: --native requires --ple-gguf ...` を stderr に出し、終了コード `2`（`src/program/generate.cpp:3258-3262`）。
- `--native-ple-postops --no-ple`: PLE 有効化が必要とのエラーを stderr に出し、終了コード `2`（`src/program/generate.cpp:3294-3297`）。
- `--native-ple-key --no-ple`: PLE と `--native-dense-gguf` が必要とのエラーを stderr に出し、終了コード `2`（`src/program/generate.cpp:3403-3405`）。
- 有効な通常 parser 経路では、PLE を外した診断モードである旨を stderr に出します（`src/program/generate.cpp:4177-4180`）。

## 根拠

- オプションの既定値と診断用途: `src/program/generate.cpp:436-437`
- usage と parser: `src/program/generate.cpp:806-818`, `2413-2425`, `2473-2475`
- PLE 必須条件、相互排他、native 関連の拒否: `src/program/generate.cpp:3247-3261`, `3290-3300`, `3403-3405`
- PLE 初期化の分岐と無効化メッセージ: `src/program/generate.cpp:4023-4033`, `4161-4180`
- PLE token 処理の適用条件: `src/program/generate.cpp:15891-15910`
- engine target と Qwen3.6-35B-A3B の別 parser への転送: `CMakeLists.txt:759-762`, `src/program/generate.cpp:2393-2407`
