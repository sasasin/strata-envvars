# `--lookup-chain`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数。`generate.cpp` の usage 表記は `strata generate`） |
| オプション | `--lookup-chain` |
| 別名 | なし |
| 値 | 整数 `K`。parser は `0..7` に丸める |

## 役割

MTP が提案したトークン列の続きについて、プロンプトとこれまでに確定した出力内の過去の一致箇所から、最大 `K` 個の追加候補を同じ検証窓へ連結します。候補は通常の verify で検査されるため、候補が受理されるかどうかで生成結果を変える機能ではなく、検証窓の幅を増やし得る投機的ドラフト機能です（`src/program/generate.cpp:780-783`、`include/strata/spec/draft_source.hpp:1-9`）。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --lookup-chain 3
```

これはエンジンの token ID 入力形式を使った例です。通常のモデル利用時は、必要なモデル・pack・入力指定とともに `--lookup-chain K` を渡します。エンジンが受け取るトップレベル引数であり、Terminal CLI の同名なし wrapper オプションではありません（`src/program/generate.cpp:806-812`、[`docs/cli/README.md`](../../README.md) の `strata-engine` 節）。

## 値と既定値

- 省略時は `0`（無効）です（`src/program/generate.cpp:780-784`）。
- `atoi` で整数変換し、その後 `0..7` に clamp します。負数は `0`、`7` を超える値は `7` になります（`src/program/generate.cpp:2672-2675`）。
- 数字として解釈できない文字列は `atoi` の結果 `0` になり、無効値としてはじかれません。値が欠けている場合は parser の共通処理が stderr に `<option> needs a value` を出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2421`）。
- 同じオプションを複数回指定すると parser は各値を順に代入するため、最後の指定が残ります（`src/program/generate.cpp:2416-2421,2674`）。
- 関連する `--lookup-chain-min` は別オプションで、既定 `3`、最小値 `3` です。候補を採用するには一致長がこの値以上である必要があります（`src/program/generate.cpp:784,2675`、`src/spec/draft_source.cpp:20-28`）。

## 実行時の動作

`K > 0` かつ `--spec >= 2` の場合、初期化時に `--spec` の上限を拡張します。`--mtp-max-t` が未指定（`0`）なら現在の `--spec` を MTP 側の基準幅にし、verify 上限を最大 8 まで広げます。`--suffix-draft` の処理が先に `--spec` を変更している場合は、その時点の値が基準です。`--spec < 2` ではこの幅の拡張処理は行われません（`src/program/generate.cpp:3205-3218`）。

各リクエスト／生成履歴について prompt と確定済み出力を lookup history に登録し、MTP の未検証ドラフトを末尾に連結した文脈で過去の継続を検索します。候補数は `min(K, verify 窓に残る幅)` までです。候補の根拠となる一致長が `--lookup-chain-min` 未満なら候補は使われません（`src/program/generate.cpp:14175-14183,14878-14920,16459-16467,16567-16584`、`src/program/generate.cpp:1080-1086`、`src/spec/draft_source.cpp:13-33`）。組み込み source は当該リクエストの prompt と確定済み出力です。API 上は追加の draft source も検索可能ですが、この checkout で追加 source の登録箇所は見つかりませんでした（`include/strata/spec/draft_source.hpp:7-9,36-60`、`src/spec/draft_source.cpp:8-10,29-33`）。

候補が見つかっても、通常は `DraftPolicy::chain` が窓サイズごとの実測コストと過去の受理率、MTP ドラフト確率を使い、期待 tokens/ms が改善する範囲だけを検証窓に追加します（`src/program/generate.cpp:14904-14920,16569-16584`、`include/strata/spec/draft_policy.hpp:40-46`）。環境変数 `STRATA_LOOKUP_CHAIN_FIXED` が存在すると、この policy による候補数の絞り込みをスキップします（値が `0` でも「存在」により有効）。

検証窓へ加えた候補は通常の検証対象となり、受理された候補だけが確定出力になります。提案元は重みを使わず、verify が候補の正否を決める設計です（`include/strata/spec/draft_source.hpp:1-5`）。したがって本オプションによって出力が変わるとはソース上説明されていません。候補が見つからない、最小一致長に届かない、最初の窓である、すでに通常の suffix lookup が選ばれた、または窓に空きがない場合は連結されません（`src/program/generate.cpp:14891-14920,16567-16584`）。

## 適用条件と副作用

- 既定ではオフです。明示的に `K > 0` とした場合だけ lookup history の構築と追加 source の履歴更新を行います（`src/program/generate.cpp:14175-14183,16459-16467`）。
- 通常の `generate` ループでは MTP が有効で、最初の窓ではなく、suffix lookup に切り替わっておらず、verify 窓に余裕がある場合に連結候補を探索します（`src/program/generate.cpp:16569-16581`）。serve ループも最初の窓・別 suffix 窓・上限幅を条件に探索します（`src/program/generate.cpp:14891-14920`）。
- lookup は prompt と生成履歴の token を索引化し、過去一致の候補を確認します。`SuffixDrafter` は三つ組索引を持ち、履歴上限の設計値は約 `20 bytes/token`、一つの三つ組について直近4位置を保持します（`include/strata/spec/suffix_drafter.hpp:7-10,19-24`、`src/spec/suffix_drafter.cpp:18-24,51-61`）。この追加メモリ・CPU処理量は `K > 0` のときに生じます。
- OS、GPU backend、model family による `--lookup-chain` 固有の validation/fallback 分岐は確認できませんでした。配布 Release binary の実動作はこの調査では照合していません。

## 出力とエラー

専用の値 validation error はなく、範囲外値は clamp されます。値欠落は終了コード `2`、未知の引数は `unknown argument: ...` と usage を stderr に出して終了コード `2` です（`src/program/generate.cpp:2416-2421,2787-2792`）。

通常の `generate` は `K > 0` のとき stdout に `lookup chain` の窓数と「受理数 / 提案数」を出します（`src/program/generate.cpp:16739-16744`）。serve は同様の集計を stderr に出し、サーバープロトコルの `DONE` 行にも追加カウンターを付けます（`src/program/generate.cpp:15365-15378,15650-15655`）。具体的な値は実行履歴に依存します。

## 根拠

- parser の option 初期値・help: `src/program/generate.cpp:780-784,942-944`
- parser の変換、欠落値、未知引数: `src/program/generate.cpp:2416-2421,2672-2675,2787-2792`
- verify 上限調整: `src/program/generate.cpp:3205-3218`
- lookup 候補の追加・policy: `src/program/generate.cpp:14891-14920,16567-16584`; `include/strata/spec/draft_policy.hpp:40-46`
- source 検索と一致長 validation: `include/strata/spec/draft_source.hpp:1-9,29-60`; `src/spec/draft_source.cpp:13-33`; `src/program/generate.cpp:1080-1086`
- lookup history の実装: `include/strata/spec/suffix_drafter.hpp:7-10`; `src/spec/suffix_drafter.cpp:18-24,51-95`
- 実行時カウンター: `src/program/generate.cpp:15365-15378,15650-15655,16739-16744`

調査範囲は上記 commit の checkout 内ソースです。同一 revision の CLI `--help` 実行および Release artifact の照合は行っていません。索引上の予定リンクと現行 parser は一致しています。
