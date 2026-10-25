# `--batch-mtp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--batch-mtp` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定は無効 |

## 役割

`--serve --batch` の各有効 slot で、通常の次 token に加えて MTP（multi-token prediction）draft を1 token 提案し、同じ verify window で検証します。提案 token が target 側の出力と一致し、終了条件や出力上限に抵触しなければ採用します。既定では無効です（`src/program/generate.cpp:670`, `910-915`, `11601-11612`）。

## 使い方

```sh
strata --pack ./model --serve --batch 4 --mtp ./draft --spec 4 --batch-mtp
```

`--batch` は2以上、`--mtp` は MTP draft のパス、`--spec` は2以上を指定します。オプション自体は値を受け取りません。エンジンの help も `--serve` の `--batch` に付随する opt-in と説明しています（`src/program/generate.cpp:910-915`）。

## 値と既定値

- parser は `--batch-mtp` を見つけると真偽値を `true` にします。値を消費せず、`Options::batch_mtp` の初期値は `false` です。繰り返し指定しても有効化されるだけで、個別の重複エラーはありません（`src/program/generate.cpp:670`, `2618`）。
- 同じ機能は `STRATA_BATCH_MTP` でも有効化できます。環境変数が存在し、空でなく、先頭文字が `0` でない場合に有効です。CLI flag と環境変数の論理和で判定します。したがって `STRATA_BATCH_MTP=0` と空文字は無効、`00` も先頭が `0` のため無効です（`src/program/generate.cpp:5299-5300`）。関連する環境変数の説明は [`STRATA_BATCH_MTP`](../../../STRATA_BATCH_MTP.md) を参照してください。
- 値なしフラグのため、数値範囲 validation はありません。必要条件を満たさない場合は起動エラーにせず、警告して batch MTP を無効化します（`src/program/generate.cpp:5301-5321`）。

## 実行時の動作

有効時、各 slot 用の `MtpDrafter` を `--batch` 個ロードし、それぞれの draft 数を1にします。draft の重みは solo drafter と共有しますが、slot ごとに private K/V state と buffer を確保します。layer split 時は drafter を最終 stage の GPU に置きます。起動時に slot 数、GPU、slot ごとの private state/buffer の MiB、空き VRAM を stderr に表示します（`src/program/generate.cpp:5520-5543`）。

各 MTP slot は verify window 内で現在 token と提案 token の2 row を使います。window は最大8 row なので、通常の slot を1 rowずつ処理する場合より一度に処理できる slot 数が少なくなり、必要に応じて slot をローテーションします（`src/program/generate.cpp:910-915`, `11525-11549`）。target 出力が提案 token と一致し、EOS・stop 条件がなく、2 token 分の生成上限と context 上限を超えない場合だけ提案を採用します。不一致時は通常 token のみを commit します（`src/program/generate.cpp:11601-11612`）。

## 適用条件と副作用

有効化には以下が必要です。条件を満たさないと stderr に `WARNING: --batch-mtp is off: ...` と理由を出し、通常の batch 処理を続けます（`src/program/generate.cpp:5301-5321`）。

- `--serve` と `--batch 2` 以上。
- `--mtp` の指定と `--spec T`（`T >= 2`）。
- layer split を使う場合、各 stage が別 GPU 上にあること。`--split-device 0` のように同一 GPU 上へ置く構成は対象外。
- layer split で helper expert cache または `--remote-expert-opt` を使わないこと。
- layer split の複数 slot group pipeline と併用しないこと。`--batch-groups G` が1より大きく解決される場合は無効になります。

layer split で `--batch-groups` を省略した場合、自動 group selection が pipeline を選ぶことがあります。その既定は `--batch-mtp` を落とす動作です。明示的な `--batch-groups auto` も pipeline を要求するため、複数 group なら `--batch-mtp` と併用できません。serial window を使うには `--batch-groups 1` を指定できます。また、`STRATA_BATCH_MTP_SERIAL` が有効で、`--batch-groups` を指定していない場合も、自動既定を1 groupにします。詳細は [`STRATA_BATCH_MTP_SERIAL`](../../../STRATA_BATCH_MTP_SERIAL.md) と `include/strata/program/batch_groups.hpp:50-65` を参照してください。

有効時は GPU 上に slot ごとの draft state/buffer が増えるため、VRAM を消費します。verifier は slot rotation による多様な row layout に備え、captured batch graph の保持数を64に制限します（`src/program/generate.cpp:9166-9169`; 上限 API: `include/strata/core/verify.hpp:225-226`）。

## 出力とエラー

- 条件不成立は警告のみで、`--batch-mtp` をオフにして続行します（`src/program/generate.cpp:5318-5321`）。
- slot drafter の load または bind、slot residual buffer の GPU allocation に失敗すると、理由を stderr に出し、engine は終了コード `1` で戻ります（`src/program/generate.cpp:5525-5530`, `9182-9196`）。
- 実行中、生成 token は server の stdout protocol `BT <slot> <token>`、slot 完了は `BDONE ...` で出力されます。window 終了時の verifier/commit 失敗や draft 失敗は `ERR ...` を stdout に出して batch 処理を失敗させます（`src/program/generate.cpp:11610-11612`, `11640-11673`）。
- batch summary が出るとき、受理された MTP proposal 数と総提案数を stderr に表示します（`src/program/generate.cpp:11730-11733`）。
- layer split の pipeline が残った場合は、slot drafter の VRAM は確保されたまま draft が実行されない旨を stderr に警告します（`src/program/generate.cpp:11739-11747`）。通常は事前の group gate で無効化されます。

## 根拠

- parser・既定値・help: `src/program/generate.cpp:670`, `910-915`, `2618`
- `STRATA_BATCH_MTP` の判定、条件 validation と警告: `src/program/generate.cpp:5299-5321`
- slot drafter の生成・配置と起動時表示: `src/program/generate.cpp:5520-5543`
- verifier graph 上限と初期化: `src/program/generate.cpp:9166-9173`; `include/strata/core/verify.hpp:225-226`
- proposal row、採否、commit、server 出力: `src/program/generate.cpp:11525-11549`, `11601-11612`, `11640-11673`
- batch summary と pipeline 警告: `src/program/generate.cpp:11730-11747`
- group の自動解決: `include/strata/program/batch_groups.hpp:50-65`
