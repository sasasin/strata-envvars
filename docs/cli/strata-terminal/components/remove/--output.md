# `strata components remove --output`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--output` |
| 別名 | なし（`--json` は別の alias option） |
| 値 | `human`、`json`、`jsonl` |

## 役割

削除結果とエラーを人向けテキストまたは機械処理向け JSON で出力します。エンジンを削除するかどうか、削除対象、削除処理そのものは変えません。`remove` は `strata components remove <engine>` として登録され、`engine` には版番号またはインストール先 folder 名を指定します。

## 使い方

```sh
strata components remove 0.1.54 --output json
```

## 値と既定値

- 省略時は `human` です。
- `human`、`json`、`jsonl` 以外は parser の `choices` 検証で拒否されます。値を省略した場合も parser error になります。
- `json` と `jsonl` はどちらもこの一回限りの削除結果を JSON オブジェクト 1 行で出します。`jsonl` を指定しても進捗イベント列にはなりません。

## 実行時の動作

`--output` は `strata_cli/update_cmd.py` の共通 parser で追加され、`remove` にも適用されます。`update_cmd.run()` は値が `json` または `jsonl` なら machine mode とし、削除成功時は `schema_version: 1`、`ok: true` と削除結果を含む JSON オブジェクトを stdout に出します。`human` では削除した engine の版と解放容量を表示します。

この option は削除可否の条件を変えません。対象解決後、`engine_library.delete_engine()` が実際の削除を行います。`--json` は共通 one-shot option として登録されており、単独なら `--output json` と同じ扱いです。`--json` と `--output jsonl` を同時指定すると、one-shot command に `--json` は使えないというエラーになり、処理を開始しません。`--quiet` は human mode の情報出力を抑えますが、JSON / JSONL 出力には適用されません。

## 適用条件と副作用

削除対象は、一覧から `--family`（`qwen` または `deepseek`）で絞った上で、版番号または folder 名に一致する導入済み engine です。該当なし、または同じ版番号が複数 family にあるなど対象を一意に決められない場合は削除せず失敗します。

現在使用中の engine、または稼働中プロセスが使用している engine は削除できません。削除時は対象 folder を `.deleting-<乱数>` に rename してから中身を消します。rename に失敗した場合は何も変更しなかった旨を示して失敗します。成功後、Qwen engine では該当 folder を指す previous / pinned 状態や、同版が他に残っていない場合の failed 記録を更新し、履歴を保存します。DeepSeek engine では stale pin があれば解除します。モデルと設定は削除対象外です。

## 出力とエラー

- 成功時の `human` 出力は `Engine <version> deleted (<容量> freed). Models and settings were not touched.` です。`json` / `jsonl` は削除結果を含む JSON オブジェクトを stdout に出します。終了コードは 0 です。
- `json` / `jsonl` で `UpdateError` が起きた場合は `ok: false`、`error.code`、`error.message` を持つ JSON を stdout に出し、その code を終了コードにします。`human` では `strata: <message>` を stderr に出します。
- 対象なし・曖昧・使用中など削除不可は code 2、削除先を rename できない場合は code 6 です。CLI 全体の parser error（不正な `--output` 値など）は argparse の usage / error 表示となり、実行処理には入りません。

## 根拠

- 索引上の scope と掲載位置: `docs/cli/README.md:309-325`。
- parser の `--output` 値と既定値、`remove` への適用: `strata_cli/update_cmd.py:47-57,88-91`。
- `remove` の処理分岐、machine mode と成功時の出力: `strata_cli/update_cmd.py:98-108,233-242,272-273,358-400`。
- JSON エラーと `UpdateError` の code 伝達: `strata_cli/update_cmd.py:233-242,307-319`。
- 対象の照合と曖昧・未導入エラー: `strata_control/engine_library.py:198-211`。
- 使用中 / 稼働中 engine の削除禁止: `strata_control/engine_library.py:167-177,294-309`。
- folder rename・削除・状態更新・rename 失敗: `strata_control/engine_library.py:310-334`。
- `--json` / `--quiet` の共通追加、および alias の変換と quiet の適用条件: `strata_cli/cli.py:508-515,2249-2265`。

調査範囲はこの commit のソースです。同一 revision の CLI `--help`、Release 配布物、および OS ごとの filesystem 挙動は確認していません。
