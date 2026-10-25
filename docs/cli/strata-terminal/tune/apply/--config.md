# `strata tune apply --config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--config` |
| 別名 | なし |
| 値 | run config のファイルパス（`FILE` 相当）。型・選択肢の parser validation なし |

## 役割

完了した tuning job の推奨値を書き込む run config を指定します。適用対象は `strata-<model>.json` 形式の設定ファイルで、保存済み profile を指定するオプションではありません。省略時は job のモデル名を手掛かりに自動選択します。

## 使い方

```sh
strata tune apply <job-id> --config ./strata-model.json
```

`<job-id>` は適用する tuning job の ID です。相対パスは CLI の実行時カレントディレクトリから解決されます（`Path(a.config)` をそのまま使用）。

## 値と既定値

- `--config` は任意の文字列値で、既定値は `None` です。拡張子、ファイル形式、存在確認などを argparse の宣言では検査しません。
- 指定値が truthy ならその値を `Path` にして対象にします。空文字列は未指定と同じ扱いになり、自動選択へ進みます。
- 省略時はカレントディレクトリ以下から `strata-*.json` を再帰検索します。JSON object で `args` が list のファイルだけが候補になり、最大200件までをパス順で調べます。job のモデル名があればファイル名との大文字小文字を無視した部分一致を優先し、一致がなければ候補が1件だけのときに限りそれを選びます。候補がない、または曖昧な場合は設定ファイル未検出として終了します。

## 実行時の動作

指定パスは `strata tune apply` が変更する run config の選択に使われます。指定しても、job の完了状態、推奨の有無、モデル・engine 等の identity 照合は省略されません。job は `--state-dir`、`STRATA_TUNE_DIR`、または既定のユーザー状態ディレクトリ `tuning/` から読み込まれます。

適用処理は完了済みで推奨ありの job、推奨内容、レポートの状態などを確認し、job に記録されたモデル digest がない場合は拒否します。さらに engine、model、backend、workload、context の identity を照合し、測定対象との不一致があれば拒否します。`--model-path` が省略され、job に identity 情報がある場合、現行 CLI は model identity を「ファイルなし」として再構成するため、記録済み digest と照合できず拒否され得ます。`--config` はこの照合条件を変更しません。

許可された推奨 flag は config の `args` に反映され、同じ flag の既存出現はすべて除去して推奨値で置換し、存在しない flag は追加します。その他の config key は保持され、user args は推奨対象 flag を除いて保持されます。書き込み前の元ファイルは job 状態ディレクトリ内の application 記録へコピーされ、候補 config も保存されます。config 本体は一時ファイル経由で atomic replace されます。

## 適用条件と副作用

- 指定した config が存在しない場合、明示指定・自動選択のどちらでも「run configuration がない」として終了します。
- 既定では `<state_base>/tuning` が job 用状態ディレクトリです。`state_base` は POSIX では `$XDG_STATE_HOME/strata`（未設定時 `~/.local/state/strata`）、Windows では `%LOCALAPPDATA%\Strata`（未設定時は home 配下）です。`--state-dir` または `STRATA_TUNE_DIR` による指定は job 検索・application backup の保存先に作用し、`--config` の解決先とは別です。
- **実際の CLI 経路では候補 config を起動して検証しません。** `_tune_apply` は `apply_recommendation(..., verify=None)` を呼びます。したがって適用成功表示の後にも、候補が実モデルで検証されていない旨の注意が出ます。parser の help と apply module の一般的な説明にある「候補を検証してから適用」という記述より、ここでは実際の呼び出しを根拠にしています。
- 適用前の確認中に config の bytes が変わった場合は上書きを拒否します。過去の bytes と application metadata を状態ディレクトリに残しますが、この文書の `--config` 自体には rollback を行う機能はありません。復元コマンドは `strata tune rollback` です。

## 出力とエラー

- 適用成功時、既定の human 出力は対象パス、追加・削除された flag、前後の SHA-256 の先頭16桁、rollback 用 application ID を表示し、実モデル未検証の注意も表示して終了コード `0` を返します。`--output json` では成功 payload を JSON で stdout に出します。
- job が見つからない、config が見つからない、job の model digest がない、identity を再構成できない場合は終了コード `2` です。
- 適用判定で拒否された場合は `ApplyError` の code（既定 `6`）を返します。human 出力では `strata: <理由>` を stderr に、JSON 出力では error object を stdout に出します。
- 不正 JSON など `ApplyError` 以外の config 読み込み例外をこの command handler が個別に整形する処理は確認できませんでした。

## 根拠

- `strata_cli/cli.py:461-470` — `apply` parser と `--config` の値・既定値、および同じ parser scope の関連 option。
- `strata_cli/cli.py:1850-1866` — 指定 config の選択、未指定時の fallback、job/config 不在時の終了。
- `strata_cli/cli.py:1868-1905` — identity 再構成、digest 条件、`--model-path` の使用、適用関数呼び出しと拒否経路。
- `strata_cli/cli.py:1907-1921` — 成功時の出力と未検証の注意。
- `strata_cli/cli.py:1924-1934` — 未指定時の config 候補選択。
- `strata_cli/cli.py:1941-1950` — job ID 形式と job 読み込み。
- `strata_control/tune_apply.py:98-115` — `strata-*.json` の検索、JSON object と `args` list による候補判定、検索上限。
- `strata_control/tune_apply.py:118-166` — 推奨 flag の置換・追加と他設定/user args の保持。
- `strata_control/tune_apply.py:227-289` — job 状態・推奨・drift・config・report・identity の適用判定。
- `strata_control/tune_apply.py:306-370` — 検証 callback の扱い、同時編集検出、backup と candidate 保存、config の atomic write、application 記録。
- `strata_cli/cli.py:1643-1650`、`strata_control/paths.py:13-21` — tuning 状態ディレクトリの優先順位と既定パス。
- `strata_cli/cli.py:527-532`、`strata_cli/cli.py:535-542` — human/JSON の成功・失敗出力形式。
