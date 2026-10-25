# `--no-save`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--no-save` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真 |

## 役割

自動チューニングの測定と結果表示を行いながら、結果を保存プリセットとして作成しないためのフラグです。測定自体は通常どおり実行されます。

## 使い方

```sh
strata tune auto my-profile --no-save
```

`my-profile` は保存済みプロファイル名、またはチューニング対象の実行設定 JSON です。

## 値と既定値

`argparse` の `store_true` で定義され、既定値は `False` です。値は不要です。複数回指定しても真のままです。`--no-save=false` のような値付き指定はこの parser の構文ではありません。個別の値検証はありません。

## 実行時の動作

通常の対象解決、エンジン確認、測定、進捗報告はこのオプションの有無にかかわらず行われます。結果が `improved` または `default_confirmed` の場合にプリセットを作成する分岐があり、`--no-save` を指定するとその分岐を通りません。したがって、新しいプリセットファイルや有効プリセット索引はこの実行では作成・更新されず、結果の `preset` と `values.preset_name` は `null` になります。既存のプリセットを無効化・削除する処理もありません。

ただし、測定後には別処理で試行履歴 `history.jsonl` への記録を試みます。書き込み時の `OSError` は無視されます。既定のワークディレクトリは一時フォルダーですが、試行ごとの設定 JSON と engine/worker ログを書き込みます。`--work-dir` を指定した場合はそのディレクトリを使用します。`--no-save` はこれらの副作用を止めません。

## 適用条件と副作用

このフラグは `strata tune auto` のみに適用されます。プリセットを保存しない場合も、チューナーは候補設定で worker とエンジンを起動して計測します。`--name` は保存名を指定するためのオプションなので、`--no-save` と併用してもプリセット名には作用しません。

## 出力とエラー

人間向け出力では通常のチューニング結果が標準出力に表示され、進捗は標準エラーに出ます。改善結果でも保存名の文言は表示されません。`--output json` では結果 JSON の `preset` が `null` になります。

対象設定の解決失敗など、測定開始前のエラーは人間向けなら `strata: ...` として標準エラーに出て、該当コード（例: 対象解決・goal 不正は通常 2、エンジン不在は 5）を返します。JSON 出力では `{ok:false,error:{code,message}}` を標準出力に出します。測定後は `improved` / `default_confirmed` が終了コード 0、キャンセルが 130、それ以外の結果が 6 です。履歴書き込みの `OSError` は無視されます。プリセット作成・有効化の保存処理は実行されません。ただし、別経路の試行履歴書き込みは発生し得ます。

## 根拠

- `strata_cli/tune_commands.py:20-47` — `auto` parser と `--no-save` の `store_true` 宣言、および既定の引数定義。
- `strata_cli/tune_commands.py:174-200` — 対象の解決、RAM 値検査、エンジン存在確認、チューニング設定の構築。
- `strata_cli/tune_commands.py:205-228` — 人間向け進捗の出力先、status 更新、既定一時 workdir と tuner 構築。
- `strata_cli/tune_commands.py:230-261` — 測定実行後の試行履歴記録、`--no-save` によるプリセット作成分岐の抑止、結果出力と終了コード。
- `strata_cli/tune_commands.py:95-108` — 共通の成功・失敗出力形式。
- `strata_control/presets.py:268-307` — プリセット作成時の検査、JSON 保存、および有効化。
- `strata_control/presets.py:485-507` — `history.jsonl` への試行追記。
- `strata_control/tune_session.py:420-431, 461-479` — worker session の workdir と測定設定・ログファイル生成。
- `strata_cli/cli.py:2156-2158, 2174-2183` — `tune` の dispatch と `OSError` の CLI エラー処理。
