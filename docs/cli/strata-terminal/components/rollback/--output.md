# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

rollback の結果やエラーを標準出力・標準エラーへどの形式で表示するかを選びます。engine の切り戻し内容や実行条件は変更しません。

## 使い方

```sh
strata components rollback --output json
```

このコマンドは実際に前回の更新で保存された engine へ切り戻します。意図して切り戻す場合に実行してください。出力形式だけを確認する目的なら `strata components rollback --help` を使えます。

## 値と既定値

- 省略時は `human` です。
- `human`、`json`、`jsonl` のいずれかだけを受理します。その他の値は `argparse` の choices 検証で拒否され、コマンド本体に入る前に usage とエラーが表示されます（終了コード 2）。
- 短縮 alias や `--json` alias はこの parser にありません。

## 実行時の動作

- `human` は成功時に切り戻し元・先のバージョン、保存済み tuning preset の扱い、再試行方法を人向けの文で表示します。
- `json` は成功時に `schema_version: 1`、`ok: true` と rollback 結果を含む JSON オブジェクトを標準出力へ1行で出します。
- `jsonl` も成功結果は同じ JSON オブジェクトです。`--wait` により serving 中の engine が止まるのを待つ場合は、待機イベントが先に JSON Lines で出ることがあります。rollback 自体からは進捗イベントを出しません。
- `json` と `jsonl` の失敗は `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON オブジェクトとして出力されます。`human` の失敗は `strata: ...` の形式で標準エラーへ出ます。

## 適用条件と副作用

`--output` 自体の副作用は表示形式の選択です。rollback コマンドは選択した形式にかかわらず、前回の engine が記録されていなければ失敗します。実行できる場合は前回の engine package を検証して pin し、次回の起動でそれが選ばれることを確認します。状態ファイルには pin・active/previous の更新と履歴が保存されます。engine の切り替えで tuning preset の再確認が必要になった場合は印を付けますが、preset は削除しません。

`--wait` で serving 中の engine の停止を待つとき、`--output jsonl` では待機イベントを出力します。待機指定がなくても human 対話端末なら確認を促しますが、machine 出力または非対話実行では待たずに Busy エラーになります。`--components-dir` は rollback state/package を探す場所を指定し、`--backend` はこの PC で復元 engine が利用可能かの判定に使われます。

## 出力とエラー

- `--output` の未対応値は parser 段階で終了コード 2 です。
- 保存された前回 engine がない、またはすでにその engine が有効な場合は終了コード 2 です。
- 前回 engine の package が欠損・破損している場合、または現在の PC に適合しない場合は終了コード 5 です。
- serving 中で待機しない場合や待機時間内に停止しない場合は Busy エラー（終了コード 7）になります。その他の updater エラーもそれぞれの終了コードで返されます。
- JSON/JSONL モードの JSON は `stdout`、human エラーは `stderr` です。`jsonl` の待機イベントは `schema_version: 1` と event 情報を持つ JSON 行です。

## 根拠

- parser と値の choices、既定値、rollback parser への登録: `strata_cli/update_cmd.py:30-40,57-59`
- 実行形式の判定、出力内容、rollback 呼び出しとエラー形式: `strata_cli/update_cmd.py:62-84,163-196,225-234`
- 共通 parser から dispatch まで: `strata_cli/cli.py:139-140,2135-2137`
- updater state の読込・原子的保存・履歴保持: `strata_control/updater.py:165-204`
- rollback の前提確認、待機、package 検証、pin と履歴の更新: `strata_control/updater.py:1033-1078`
- serving 待機イベント: `strata_control/updater.py:300-311`
- `--wait` の既定・human 対話と machine 出力の違い: `strata_cli/update_cmd.py:237-252`
- 起動時に手動 rollback の pin が優先される処理: `strata_control/engine_component.py:937-944`
- オプションの索引上の scope: `docs/cli/README.md` の `strata components rollback` 節

調査範囲は上記 commit の checkout 内の Terminal CLI parser と実装です。別環境の配布バイナリや Release artifact は照合していません。
