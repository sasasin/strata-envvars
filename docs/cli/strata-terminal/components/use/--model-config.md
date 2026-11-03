# `strata components use --model-config`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`（文字列。parser に型・選択肢・パス検証はない） |

## 役割

このコマンドでは `--model-config` は受理されますが、指定値は使われません。`use` は導入済み engine を選択して今後の起動先を切り替える処理であり、値をモデル設定として読み込んだり、モデル起動テストに渡したりしません。parser の説明文は「テスト起動に使うモデルの run config」ですが、これは共通 parser の説明であり、このコマンドの実装とは一致しません（`strata_cli/update_cmd.py:47-56,84-87,254-256,272-273`）。

## 使い方

```sh
strata components use 0.1.54 --model-config ./run.json
```

この例では engine `0.1.54` の選択だけが行われ、`./run.json` は参照されません。設定ファイルを切替に反映させる目的でこのオプションを付けても効果はありません。engine の選択には版番号、フォルダー名、または `newest` を指定します（`strata_cli/update_cmd.py:84-87`、`strata_control/engine_library.py:198-211`）。

## 値と既定値

`argparse` では値を取る文字列引数として登録され、既定値は `None` です。`type`、`choices`、またはこの parser によるファイル存在確認はありません。値を省略すれば `None`、同じオプションを複数指定した場合は通常の `store` 動作で最後の値が残ります（`strata_cli/update_cmd.py:54-55`）。ただし `components use` の経路では、どの値も後続処理に使われません。

## 実行時の動作

`run()` は引数値を `Context.run_config` に格納します（`strata_cli/update_cmd.py:254-256`）。続いて `components use` は `_engines_command()` に分岐し、導入済み engine の一覧から対象を解決し、`lib.use_engine()` を呼びます（`strata_cli/update_cmd.py:272-273,378-383`）。この経路で `ctx.run_config` を参照する処理はありません。`engine_library.use_engine()` は稼働中モデルの待機・拒否判定を行ってから Qwen または DeepSeek の切替処理に進み、`run_config` を読みません（`strata_control/engine_library.py:225-239`）。

したがって、このオプションに関する validation、ファイル読み込み、起動テストはありません。DeepSeek の切替には engine 実行ファイルの起動確認がありますが、これは `--model-config` を使うモデル設定テストではありません（`strata_control/engine_library.py:265-283`）。

切替が成功すれば、対象 engine が以後の起動先になります。Qwen 系では engine の切替状態を保存し、DeepSeek 系では選択状態・関連プロファイルの参照先を更新します。engine のダウンロードや削除は行いません（`strata_control/engine_library.py:225-239,246-262,265-289`）。

## 適用条件と副作用

オプション値の適用条件はありません。値を指定しても、空文字列を値にしても、その値に由来する副作用はありません。切替そのものは、選択した engine がこのコンピューターに適合しない場合は拒否されます。また、モデル稼働中は `--wait` による待機または拒否となり、`--model-config` はこの判定に影響しません（`strata_cli/update_cmd.py:378-383,403-418`）。

## 出力とエラー

成功時は、人向け出力では切替先や「すでに使用中」を表示し、`--output json` / `jsonl` では成功結果を JSON で出力します（`strata_cli/update_cmd.py:383-394`）。指定した run config の読み込みエラーは発生しません。対象 engine が見つからない・曖昧な場合は終了コード 2、非対応 engine や検証に失敗した engine は終了コード 5、稼働中モデルにより切替できない場合は終了コード 7 です。コマンド側は `UpdateError` を人向けなら stderr、機械出力なら JSON に出します（`strata_control/engine_library.py:198-211,216-239,246-260`、`strata_cli/update_cmd.py:237-242,307-311,378-383`）。

## 根拠

- `strata_cli/update_cmd.py:47-56,84-87` — 共通オプションの parser 定義と `components use` への登録。
- `strata_cli/update_cmd.py:254-256,272-273,378-394` — 値を `Context` に格納する箇所、`use` 分岐、切替呼び出しと出力。
- `strata_control/engine_library.py:198-211,225-239,246-289` — engine の解決、切替・検証・状態更新。`use_engine()` 系は `ctx.run_config` を参照しない。
- `strata_cli/update_cmd.py:403-418` — 稼働中モデルの待機条件。`--wait` が独立して処理される。
- `docs/cli/README.md:291-307` — `components/use` の索引上のスコープと対象リンク。

この文書は指定された source checkout のソースを調査したものです。既存 CLI の `--help` 出力、Release 配布物、実機上の起動結果は確認していません。
