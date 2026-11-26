# `--no-token-graph`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（root のエンジン引数） |
| オプション | `--no-token-graph` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常は条件が整うと全層の処理を一つの CUDA graph に capture して token ごとに起動するところを、このフラグで無効にします。代わりに通常の layer loop が使われ、各層の `pre` graph と `post` graph をホストが順に起動します。help の説明では A/B 比較用です。性能改善を保証する設定ではありません。

## 使い方

```sh
# pack から token 推論し、token graph を使わない経路を選ぶ
strata generate --pack /path/to/pack --tokens "1,2,3" --no-token-graph
```

## 値と既定値

値を取りません。未指定時の `Options::no_token_graph` は `false` で、指定すると parser が `true` にします。同じフラグを複数回指定しても同じ真偽値を設定するだけです。個別の値検証やこのオプション専用のエラー分岐はありません。parser が認識しない引数は stderr に `unknown argument` と usage を出して終了コード `2` で終了します。

## 実行時の動作

`--no-capture` でなく native pack でもない場合、通常の層別 `SessionGraphs`（層ごとの `pre` と `post`）はこのオプションに関係なく capture されます。フラグを指定すると token graph capture 条件から外れ、decode loop は `session_run_token` ではなく `session_loop` を呼びます。`session_loop` は層ごとの `pre` を開始し、router の結果を CPU expert pool に渡し、その結果を転送して同じ層の `post` graph を起動します。

プロファイル済み expert cache の hit 判定を token graph 内で行うための device residency table の構築も、このフラグ指定時には抑止されます。token graph 専用の設定を通らず、`session_loop` 側の host 層別経路が使われます。

## 適用条件と副作用

- token graph 自体が capture されないのは、`--no-capture` が指定されていないこと、`native_pack`（expert layout の native 形式）でないこと、layer dump / half dump を行わないこと、multi-GPU layer split でないことなど、通常の token graph 条件が満たされる場合の比較です。これらの条件により元から token graph を使わない実行では、このフラグによる経路変更はありません。
- `--no-capture` を指定した場合は token graph capture 自体が行われず、token ごとに `session_token` が呼ばれます。この場合も `--no-token-graph` による追加の変更はありません。
- flag 専用のファイル・ネットワーク操作は確認できません。通常 capture と layer loop に必要な GPU graph、CUDA stream、device buffer などの割当・起動・解放は実行されます。
- 根拠にした `generate.cpp` は CUDA/HIP のエンジン実装です。別 backend の同名フラグの動作はこの調査では確認していません。
- root parser とは別に、Qwen3.6 専用 parser にも同じ文字列があります。索引で scope が別文書に分かれているため、この文書は root `strata generate` の実装だけを記述します。

## 出力とエラー

このフラグを指定したこと自体を示す専用ログは確認できません。token graph を利用する経路では `token graph captured ...`、profile cache の token graph hit 経路では `token graph hit path ...` が stderr に出ますが、フラグ指定時は該当する capture / hit-table 準備条件から外れるため、これらのログは出ません。layer loop の graph launch、GPU query、pool 処理などが失敗すれば `session_loop` のエラーが `strata generate:` 付きで stderr に出て、呼び出し側は終了コード `1` を返します。

## 根拠

- `engine/src/program/generate.cpp:954` — `no_token_graph` の既定値 `false` と A/B 用途のコメント。
- `engine/src/program/generate.cpp:1375` — help の説明（層ごとに二つの graph を host 起動する A/B arm）。
- `engine/src/program/generate.cpp:4262` — parser が値なしで bool を `true` にする定義。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数の stderr、usage、終了コード `2`。
- `engine/src/program/generate.cpp:10977-10985` — token graph と層別経路の関係。
- `engine/src/program/generate.cpp:10997-11015` — profile hit 用 residency table の準備が `!o.no_token_graph` 条件下でのみ行われることと割当失敗メッセージ。
- `engine/src/program/generate.cpp:5445` — `native_pack` が expert layout に基づく条件であること。
- `engine/src/program/generate.cpp:11069-11076` — token graph capture 条件、失敗時の stderr と通常終了コード `1`、成功時ログ。
- `engine/src/program/generate.cpp:24296-24313` — decode loop が `session_run_token` と `session_loop` を切り替える箇所、および失敗時の戻り経路。
- `engine/src/core/session.cpp:200-285` — `session_capture` が各層の `pre` / `post` graph を capture する実装。
- `engine/src/core/session.cpp:681-753` — `session_loop` の層別 ring 待ち、pool 呼出し、`post` graph launch。
- `engine/src/core/session.cpp:778-783` — 次層の `pre` graph launch と失敗メッセージ。
- 同じ文字列は `engine/src/qwen35/q36_engine.cu:5357` にも存在し、別 parser では独自に `graph = false` とする。`docs/cli/README.md` の `strata-engine` 節は root と Qwen3.6 専用 parser を分けているため、本書の対象には含めない。
