# `--no-ple`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--no-ple` |
| 別名 | なし |
| 値 | 取らない真偽フラグ |

## 役割

PLE（Per-Layer Embedding）を無効にする診断用の ablation 指定です。ソースは通常推論の設定ではなく「明示的な診断 ablation」と位置付け、PLE を外した実行で得られる token はモデル本来のものではないと警告します。性能・動作の A/B 計測向けで、通常の推論結果を得る用途には適しません（`engine/src/program/generate.cpp:775,1220,6433-6436`）。

## 使い方

エンジンの `--pack` 実行で、既存 tokenizer の token ID を与えて診断実行します。

```sh
strata --pack <pack-dir> --tokens 1,2,3 --max-new 1 --no-ple
```

`--tokens` はこの parser で必須で、カンマ区切りの整数列として読み込まれます（`engine/src/program/generate.cpp:3852-3856,5002-5004`）。

## 値と既定値

オプション自体に値はありません。parser は引数を消費せず `no_ple` を `true` にします。指定しなければ初期値 `false` で、PLE の通常経路に従います。同じ指定を複数回しても真偽値を再設定するだけです（`engine/src/program/generate.cpp:775,3900`）。

## 実行時の動作

`--no-ple` を指定すると `--ple-gguf` が省略されていても PLE table shard の自動検出を行いません。PLE GGUF の読み込み・wire 処理・PLE 用 embedding / scratch buffer の確保は `ple_gguf` が空の場合に実行されず、stderr に PLE を明示的に無効化した旨と、出力 token はモデル本来のものではない旨を出します（`engine/src/program/generate.cpp:5127-5134,6264-6269,6433-6437`）。

実行中は `ss.ple.ready()` が偽になるため、通常層処理や token 処理へ PLE state を渡す箇所、PLE の token 行の issue / finish がスキップされます（`engine/src/core/session.cpp:244-248,818-823`、`engine/src/program/generate.cpp:24255-24262,24268-24276`）。session 全体の確保には別途 PLE history の領域も含まれるため、このフラグだけで session memory の全 PLE 関連領域がなくなるとは限りません（`engine/src/core/session.cpp:47-68,123`）。

## 適用条件と副作用

- `--ple-gguf` と同時に指定できません。同時指定時は stderr に `--no-ple and --ple-gguf are mutually exclusive` を出して終了コード `2` で終了します（`engine/src/program/generate.cpp:5205-5207`）。
- `--native-ple-postops` と併用できません。stderr に PLE が必要とのエラーを出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:5209-5211`）。
- `--native` を使う経路では PLE shard が必須で、`--no-ple` を指定すると validation で拒否されます。stderr は `--native requires --ple-gguf ...` の診断を出し、終了コード `2` です（`engine/src/program/generate.cpp:5155-5158`）。従って、この ablation はこの native GGUF 経路では利用できません。
- `--native-ple-key` も PLE と `--native-dense-gguf` が必要なため、`--no-ple` との組み合わせは拒否されます（`engine/src/program/generate.cpp:5318-5320`）。
- 実行時の PLE 無効化メッセージは stderr です。その他の PLE table 読み込み副作用は、PLE table を開く分岐に入らないため発生しません（`engine/src/program/generate.cpp:6269-6272,6433-6437`）。

## 出力とエラー

成功経路では `strata generate: PLE OFF by explicit --no-ple diagnostic request.` と、出力 token はモデル本来のものではないという警告を stderr に出します。少なくとも上記の競合・native 条件の拒否は終了コード `2` です（`engine/src/program/generate.cpp:6433-6437,5155-5158,5205-5215,5318-5320`）。

## 根拠

- `engine/src/program/generate.cpp:775,1218-1220,3899-3900` — 状態の初期値、help 文言、root parser の `--ple-gguf` / `--no-ple` 登録。
- `engine/src/program/generate.cpp:5127-5158,5205-5215,5318-5320` — native 経路の必須条件、自動 shard 選択、相互排他と validation の失敗経路。
- `engine/src/program/generate.cpp:6264-6272,6410-6437` — PLE table と buffer の初期化条件、ablation 時の stderr 出力。
- `engine/src/core/session.cpp:244-248,818-823`、`engine/src/program/generate.cpp:24255-24276` — ready 判定を使った PLE 処理の適用条件。
- `docs/cli/README.md:1036-1042,1151`（strata-envvars）— `strata-engine` root の scope と当該 option の索引リンク。

調査対象は索引が指定する `engine/src/program/generate.cpp` の root parser です。別 backend 用に複製された parser の挙動はこの文書では一般化していません。
