# `strata tune rollback`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune rollback` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/tune_apply.py` |
| 引数 | `application_id`（必須の位置引数） |

## 役割

`strata tune apply` が run config に適用した変更を戻し、適用直前に保存されたファイル内容を復元します。rollback は tuning の測定ジョブ ID ではなく、apply が発行した application ID を指定します。apply 成功時の表示には、対応する `strata tune rollback <application_id>` の例が含まれます。

## 使い方

```sh
strata tune rollback 20261025T120000Z-0123456789ab
```

application ID は実際の `strata tune apply` の結果に表示された値に置き換えてください。状態ディレクトリを明示する場合は `--state-dir DIR`、JSON で結果を受け取る場合は `--output json` を追加できます。

## 実行時の動作

1. application ID に対応する `application.json` を状態ディレクトリ内の `applications/<application_id>/` から読みます。
2. `rolled_back` が未設定または false で、保存済みの `before.json` と記録された run config が存在することを確認します。
3. 現在の run config の SHA-256 が application record の `after_sha256` と一致する場合に限り、保存していた `before.json` のバイト列を run config に原子的に書き戻します。
4. application record に `rolled_back: true` と `rolled_back_at` を記録します。

そのため、apply 後に run config が編集されていれば rollback は拒否され、後から行った変更を上書きしません。すでに rollback 済みの application も再実行できません。

## 適用条件と副作用

- `--state-dir` を指定した場合はそのパスを使います。省略時は環境変数 `STRATA_TUNE_DIR`、それも未設定なら `strata_control.paths.state_base() / "tuning"` を状態ルートとして使います。
- rollback 対象の run config は application record に保存された `config_path` から決まります。このコマンドに config パスを別途指定する option はありません。
- application 記録を探す前に `applications/` ディレクトリを `mkdir(parents=True, exist_ok=True)` で作成します。記録が見つからず失敗する場合も、このディレクトリ作成は行われます。
- 成功時は対象 run config を上書き復元し、application record も更新します。書き込みは `tune_apply._atomic_write` を通じて一時ファイルの fsync 後に置換します。
- このコマンドの rollback 処理は config ファイルと application record を変更します。実行中のエンジンを停止・再起動する処理は確認できません。

## 出力とエラー

- 既定の human 出力は復元先と application ID を表示します。`--output json` は成功時に `restored` と `application` を含む成功 JSON を出力します。
- application record がない場合はエラーコード `404`、apply 後に config が変わっている場合は `409` で拒否します。後者は「nothing was written」として記録されています。
- すでに rollback 済み、保存された旧 config がない、または対象 config がなくなった場合も拒否します。これらの `ApplyError` は既定コード `6` です。
- エラーは human 出力では stderr に `strata: ...`、JSON 出力では `{"ok": false, "error": ...}` の形式で出力され、返されたエラーコードがコマンドの終了コードになります。

## 関連文書

- [tune コマンド概要](../README.md)
- [tune apply コマンド概要](../apply/README.md)
- [CLI オプション索引](../../../README.md)（`strata tune rollback` の option scope）

## 根拠

- Strata `strata_cli/cli.py:472-475` — `rollback` の登録、必須位置引数 `application_id`、`--state-dir`、`--output` の parser 定義。
- Strata `strata_cli/cli.py:1643-1650,1712-1713` — 状態ルートの優先順位と rollback へのディスパッチ。
- Strata `strata_cli/cli.py:1953-1963,527-543` — rollback 呼び出し、human/JSON の成功・失敗出力と終了コード。
- Strata `strata_control/tune_apply.py:50-55,300-303,373-401` — rollback の拒否条件、SHA-256 照合、復元、record 更新、application directory の作成。
- Strata `strata_control/tune_apply.py:61-73` — 一時ファイルへの書き込み、fsync、原子的置換。
- Strata `strata_control/tune_apply.py:343-369` — apply が application ID、対象 config path、前後の digest、rollback 状態を記録する処理。

## 調査範囲

`strata tune --help` は実行せず、調査対象 commit の parser 定義と呼び出し先を根拠にしました。アプリケーション記録や利用環境の実データは調査していません。ファイルの OS レベルの権限・ディスク障害などに対する挙動は、このコマンド専用のエラー処理としては確認していません。
