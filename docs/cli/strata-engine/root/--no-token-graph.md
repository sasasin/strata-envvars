# `--no-token-graph`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査日は 2026-10-25。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（索引上の `strata-engine/root` 引数） |
| オプション | `--no-token-graph` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

通常の capture 経路で、全 layer をひとつにまとめた token graph を作らないようにします。ソース内の説明では A/B 用の切り替えで、token graph の代わりに layer ごとの graph を使います。性能向上を保証する設定ではありません。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-token-graph
```

例では既定の pack directory とトークン列を指定しています。実行環境に合わせて pack と入力 token を用意してください。

## 値と既定値

値は不要です。未指定時は `no_token_graph = false` で、他の条件が許せば token graph capture を試みます。指定時は真になります。同じフラグを複数回指定しても同じ真値を設定するだけです。個別の範囲 validation はありません。`src/program/generate.cpp:603` に既定値、`:2781` に parser の設定があります。

## 実行時の動作

通常の capture 経路では、`--no-token-graph` がない場合に token graph capture 条件を満たすと、`session_capture_token` が各 layer の pre/post 処理を一つの graph に記録します（`src/program/generate.cpp:7471-7478`、`src/core/session.cpp:853-905`）。この option を指定すると、その capture 条件から外れ、token 処理時に `session_loop` を呼ぶ経路になります（`src/program/generate.cpp:15932-15950`）。ソースの説明はこれを「layer ごとの二つの graph」と記載しています（`src/program/generate.cpp:7385-7387`）。

これは `--no-capture` とは異なります。`--no-capture` を指定した場合、token loop は `session_token` に分岐して layer を直接実行するため、`--no-token-graph` が切り替える token graph 対 layer graph の選択は使われません（`src/program/generate.cpp:507`, `:15932-15950`）。

`--no-token-graph` の有無にかかわらず、layer/half dump が有効な場合、native pack または multi-GPU の場合、token graph capture は行われません（`src/program/generate.cpp:7471-7478`）。expert-profile による graph hit 用の residency table 初期化も、`--no-token-graph` 指定時は行われません（同 `:7405-7407`）。これらの条件では、この option が token graph 選択に与える追加の効果はありません。

## 適用条件と副作用

- エンジンの引数 parser が受け付けるフラグです。Qwen3.6 専用 parser に同名 option もありますが、索引では `strata-engine/qwen36/` に分けられています。この文書は通常の `strata-engine/root/` parser の挙動を扱います（`docs/cli/README.md` の strata-engine scope および `src/program/generate.cpp:2781`）。
- graph capture 自体を全て無効にするものではありません。token graph に代わり `session_loop` が使われる通常経路では、layer graph と host loop を実行します（`src/program/generate.cpp:15938-15950`、`src/core/session.cpp:592-620`）。
- option 単独でファイルやネットワークに作用する処理は確認できません。graph 構築・実行経路が変わるほか、token graph 専用の診断出力や統計は token graph が実際に capture された場合に限られます（`src/program/generate.cpp:7478`, `:16986-16990`）。

## 出力とエラー

このフラグを認識するときの専用出力や専用エラーはありません。未知の引数は `unknown argument` を stderr に出し、usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。

token graph を有効にした経路で capture に失敗すると、エラーを `strata generate:` とともに stderr に出して終了コード 1 で戻ります（`src/program/generate.cpp:7473-7476`）。この option で token graph 経路を外した場合は、その capture 失敗経路には入りません。代わりの `session_loop` が失敗すると、`session_loop:` のエラーを stderr に出して終了コード 1 になります（`src/program/generate.cpp:15946-15949`）。

## 根拠

- `src/program/generate.cpp:603` — option の既定値。
- `src/program/generate.cpp:958` — built-in help の説明（A/B、layer ごとの graph と token graph の対比）。
- `src/program/generate.cpp:2781-2792` — parser、未知引数の失敗処理。
- `src/program/generate.cpp:7405-7407`, `:7471-7478` — graph hit 初期化と token graph capture の適用条件、capture 失敗・成功出力。
- `src/program/generate.cpp:15932-15950`, `:16986-16990` — token 実行時の分岐と token graph 統計。
- `src/core/session.cpp:592-620`, `:853-925` — layer loop の validation と token graph の capture 処理。

調査範囲は上記 commit のソースと `docs/cli/README.md` の索引です。Strata の実行バイナリ、Release 配布物、各 GPU/backend での実測挙動は確認していません。索引の `strata-engine/root` scope に合わせ、Qwen3.6 専用 parser の同名 option は調査対象外です。
