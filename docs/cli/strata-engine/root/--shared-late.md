# `strata generate --shared-late`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--shared-late` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

MoE の共有 expert を実行するタイミングを切り替える A/B 用フラグです。既定では GPU が共有 expert を開始してから CPU expert pool が routed expert を処理するため、両者の処理が重なります。指定すると共有 expert を CPU pool の後に実行する経路へ切り替えます。parser では既定値 `false`、指定時に `true` とし、起動時に core layer の共有 expert 実行順へ反映します（`engine/src/program/generate.cpp:952,4260,5111`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --shared-late
```

`--tokens` は usage が要求する入力例です。実際のモデル・トークン列に置き換えてください。`--shared-late` 自体には値を続けません（構文は `engine/src/program/generate.cpp:1208-1214`、parser は同 `:4259-4261`）。

## 値と既定値

- 値・別名はありません。フラグが現れたときだけ `o.shared_late = true` になります。未指定時は `false` です（`engine/src/program/generate.cpp:952,4260`）。
- 同じフラグを複数回指定しても同じ真値を代入します。別値や値付き表記を受理する処理はありません。未知の引数は `unknown argument` を stderr に出し、usage を表示して終了コード `2` で返ります（`engine/src/program/generate.cpp:4260-4273`）。

## 実行時の動作

parser 後、`layer_set_shared_early(!o.shared_late)` により core の共有 expert 実行タイミングを設定します（`engine/src/program/generate.cpp:5111`）。core の既定状態は early です（`engine/src/core/layer.cpp:51,554-555`）。

- **未指定:** `block_layer_pre` の router 実行後に `moe_shared` を呼びます。セッションループはこの pre graph を GPU に投入してから CPU pool を実行するため、共有 expert と CPU 側の routed expert 処理が重なります（`engine/src/core/layer.cpp:1593-1597`、`engine/src/core/session.cpp:226-229,726-733`）。
- **指定時:** pre 段階では共有 expert を呼ばず、CPU pool の後に実行される `block_layer_post` で `moe_finish` を選びます。これは `moe_shared` と routed expert の結合を行う経路です（`engine/src/core/layer.cpp:1593-1597,1631-1637,531-535`）。セッションループは pool の結果を反映してから post graph を投入します（`engine/src/core/session.cpp:731-752`）。

この切替は共有 expert の処理順を変えます。`moe_shared` 自体の重み確認・形式確認・計算失敗は、このフラグで回避されず、呼ばれた段階で失敗として返ります（`engine/src/core/layer.cpp:468-475,503-512`）。`--serve` のセッション設定 fingerprint にも `shared_late` が含まれます（`engine/src/program/generate.cpp:14017-14029`）。

## 適用条件と副作用

効果があるのは共有 expert を実行する MoE 経路です。共有 expert を持たないモデルでの挙動、対応モデルの一覧、性能上どちらが有利かは、このフラグの parser と確認した呼び出し経路だけからは確定できません。フラグ固有のファイル・ネットワーク操作や専用ログ出力は確認できません。

## 出力とエラー

このフラグ専用の成功メッセージや警告はありません。値を取らないため、値付きなど未認識の引数は共通の未知引数経路で stderr に `unknown argument: ...` と usage を出して終了コード `2` になります（`engine/src/program/generate.cpp:4268-4273`）。共有 expert の計算に失敗した場合は `moe_shared` が `false` とエラー文字列を返し、呼び出し元の layer 処理へ伝播します（`engine/src/core/layer.cpp:468-475,503-512,1596,1635-1637`）。

## 根拠

- `engine/src/program/generate.cpp:952,1208-1214,1290,4259-4261` — parser の格納先・usage・フラグ定義・help 表示。
- `engine/src/program/generate.cpp:4268-4273,5111,14017-14029` — 未知引数の失敗経路、core への設定、serve 用 fingerprint への記録。
- `engine/src/core/layer.cpp:51,554-555,1593-1597,1631-1637` — early/late の分岐と pre/post の共有 expert 実行位置。
- `engine/src/core/session.cpp:226-229,726-752` — pre graph、CPU pool、post graph の実行順。
- `engine/src/core/layer.cpp:468-475,503-512,531-535` — 共有 expert の入力検証・実行と late 経路の結合処理。
