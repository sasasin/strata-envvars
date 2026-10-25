# `--allow-not-repeatable`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 Strata checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--allow-not-repeatable` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

自動チューニングで、実行ごとに回答が同一にならない設定候補も試行できるようにします。通常は回答の再現性に関するクラスが `nonrepeatable` の候補を計画から除外します。

## 使い方

```sh
strata tune auto <profile-name> --allow-not-repeatable --no-save
```

`<profile-name>` はチューニング対象の保存済みプロファイル名です。`--no-save` を付けた例では測定結果を報告しますが、新しいプリセットを保存しません。

## 値と既定値

このフラグは `argparse` の `store_true` で定義され、値を受け取りません。省略時は `False`（候補を許可しない）、指定時は `True` です。数値などの引数検証はありません。同じフラグを複数回指定しても真偽値のままです。別の否定形は定義されていません。

## 実行時の動作

CLI は値を `autotune.Options.allow_nonrepeatable` に渡し、設定計画の `Context` に引き継ぎます。候補の許可判定では `exact` は常に許可され、`nonrepeatable` はこのフラグが有効な場合だけ許可されます。`placement` の候補を許可する `--allow-small-differences` とは別の判定です。

この revision で `nonrepeatable` と分類されている自動候補は `adapt_async`（エンジン引数 `--adapt-async 1`）です。フラグはその設定自体を直接適用せず、候補計画での除外を解除します。候補が選ばれても、測定で改善が確認されることが必要です。

## 適用条件と副作用

`adapt_async` は class A、CUDA backend、resident RAM 条件、および GPU 1 枚以下の条件を持ちます。したがって、このフラグを指定しても、それらに合わない環境でその候補が試されるわけではありません。さらに、他の候補と同様に、実行エンジンが必要なフラグを受け付けること、候補値の規則を満たすこと、現在の設定と異なること、過去に起動失敗扱いされていないことが計画条件です。

候補を含めてチューニングを実行すると、ベース設定と候補設定を使ったエンジン測定が行われます。結果が `improved` または `default_confirmed` で `--no-save` がなければプリセットが保存されます。`--no-save` の指定がない場合は、測定結果に応じて既存のプリセットストアへ変更が加わる可能性があります。

## 出力とエラー

フラグ固有のエラー経路やエラーメッセージはありません。候補が `--allow-not-repeatable` なしで除外される場合、計画上の理由は「answers would not repeat run to run」と記録されます。チューニング完了時は通常出力または `--output json` の JSON 結果を出し、結果に応じて終了コード `0`（改善または既定設定確認）、`6`（その他の結果）、`130`（中断）を返します。なお、不正な対象やエンジン未検出時はこのオプションに関係なく失敗し、それぞれ対象解決時の終了コード（既定 `2`）や `5` になります。

## 根拠

- 索引上の配置とコマンド scope: `docs/cli/README.md:804-824`。
- コマンド parser の登録と dispatch: `strata_cli/cli.py:486`, `1652-1653`。
- `strata tune auto` parser とフラグ型・既定値: `strata_cli/tune_commands.py:20-47`。
- CLI から option への受け渡し、対象解決・エンジン確認、計測とプリセット保存、出力・終了コード: `strata_cli/tune_commands.py:174-200`, `217-261`。
- 候補 `adapt_async` の分類・条件: `strata_control/tune_knobs.py:80-90`。
- resident RAM 条件、class A の選択、1 GPU 条件: `strata_control/tune_knobs.py:212-243`。
- answer class と許可条件、候補計画での除外理由および追加チェック: `strata_control/tune_knobs.py:337-356`, `380-446`。
- option を `Context` へ伝える処理: `strata_control/autotune.py:850-880`。
- 候補測定と候補がない場合の処理、結果分類: `strata_control/autotune.py:417-435`, `630-662`。

この調査では parser とソースコードを確認しました。CLI `--help`、別 platform の Release artifact、および実機での tuning 実行は確認していません。
