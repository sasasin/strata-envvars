# `--no-prefill-borrow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--no-prefill-borrow` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

prompt の batched prefill 用 buffer を expert cache の slot から借りず、実行中に必要な VRAM を専用 buffer 用に確保するよう指定します。既定では、prefill 中に cache の一部を buffer として借り、終了後に slot を expert cache に戻します（`src/program/generate.cpp:640-642`）。

## 使い方

```sh
strata --pack PACK --native SHARD1 --spec 4 --prefill 8192 --no-prefill-borrow
```

`PACK` と `SHARD1` は利用するモデルの実ファイルに置き換えます。オプション自体には値を付けません。

## 値と既定値

- parser は引数文字列が `--no-prefill-borrow` と一致したとき boolean を `true` にします。値は消費しません（`src/program/generate.cpp:2601-2605`）。
- 省略時は `false` です（`src/program/generate.cpp:641-642`）。
- このフラグ自体に数値や文字列の validation はありません。prefill の有効・無効は別途 `--prefill` の chunk 値で決まり、既定値は 0（chunk 処理なし）です（`src/program/generate.cpp:620-621`）。

## 実行時の動作

- `--prefill auto` と併用すると、borrow を使わないため auto の選択を解除し、chunk を 2048 に設定します。expert profile がない場合も同じ補正が行われます（`src/program/generate.cpp:3164-3166`）。
- 専用 buffer が必要な VRAM は cache の中に配置されず、cache と別に確保する前提で扱われます。layer split の VRAM 見積もりでは chunk が有効な場合、専用 buffer の概算を各 stage の reserve に含めます。1024 token 以上の split prefill では ring buffer の見積もりも追加されます（`src/program/generate.cpp:4483-4500`）。
- borrow を使う経路では prompt 中に cache slot を一時的に貸し出し、prompt 後に expert を戻します。フラグ指定時はその borrow 分岐を通りません（`src/program/generate.cpp:15711-15718, 15762-15782`）。layer split の server 経路も `pf_borrow` が false となり、各 stage の cache からの貸し出し領域を構成しません（`src/program/generate.cpp:4489, 8475-8483`）。
- この設定の効果が現れるのは、chunk が正（`--prefill` が有効）で prompt が複数 token のときです。通常の生成経路ではこの条件下で prefill 初期化・実行を行います（`src/program/generate.cpp:15711-15716, 15783-15788, 15815-15818`）。

## 適用条件と副作用

- `--prefill` を指定しない場合は chunk が 0 のため、batched prefill 用 buffer の確保や cache slot の borrow は行われず、このフラグによる実質的な差はありません（`src/program/generate.cpp:620-621, 15711-15712`）。
- `--prefill auto` との組み合わせでは chunk が 2048 に補正されます。固定 chunk を指定した場合はその値の専用 buffer を使います。layer split ではその分の VRAM reserve が必要となり、cache に使える容量が減ります（`src/program/generate.cpp:3164-3166, 4499-4500`）。
- layer split の自動 buffer 選択環境変数 `STRATA_SPLIT_OWN` は、明示的にこのフラグが有効な場合には自動選択処理に入りません（`src/program/generate.cpp:3093-3096`）。同処理が自動的に own buffer を選ぶ場合も、内部状態を `no_prefill_borrow = true` にします（`src/program/generate.cpp:3117-3122`）。
- 借用を使わない設定では prompt 中に cache slot の一時退避・返却が発生せず、その代わり buffer 用 VRAM が専用に確保されます。どちらが速いかはソースから一律には言えません。

## 出力とエラー

- 借用経路では stderr に借りた slot 数と容量を出し、prompt 後の refill 完了も記録します。このフラグにより借用しない場合は、`prompt path allocates its own buffers (no cache slots to borrow)` と stderr に出ます（`src/program/generate.cpp:15777-15782`）。
- 専用 buffer の初期化が失敗した場合はエラー文字列を stderr に出して終了コード 1 で戻ります。prefill 実行失敗も同様です（`src/program/generate.cpp:15783-15788, 15815-15818`）。borrow 経路でのみ行う lent slot の refill に失敗した場合も stderr に理由を出し、終了コード 1 で戻ります（`src/program/generate.cpp:15820-15836`）。
- このフラグに固有の値 validation や専用エラー分岐は確認できませんでした。

## 根拠

- parser と既定値: `src/program/generate.cpp:641-642, 2601-2605`
- auto chunk の補正と split buffer reserve: `src/program/generate.cpp:3164-3166, 4483-4500`
- split/server borrow 条件: `src/program/generate.cpp:8475-8483`
- 通常 prefill の borrow 条件・出力・失敗経路: `src/program/generate.cpp:15711-15718, 15762-15788, 15815-15836`

調査範囲はこの checkout の `src/program/generate.cpp` にある parser と使用箇所です。CLI help の実行、build、GPU 実行、テストは行っていません。
