# `strata components update --start-again`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--start-again` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（`store_true`）。 |

## 役割

更新のために停止したモデルを、更新処理の終了後に同じ設定で再起動する指定です。更新が失敗して旧 engine が引き続き使われる場合も、停止済みモデルの再起動を試みます。モデル停止の許可も更新する意思表示も兼ねません。停止を自動許可するスクリプトでは `--stop-model` と組み合わせます（`strata_cli/update_cmd.py:77-79`、`strata_control/engine_update.py:292-302,376-405`）。

## 使い方

```sh
strata components update --stop-model --start-again
```

この例では、更新対象がある場合、更新処理がモデルを停止してよいことを明示し、停止したモデルの再起動も自動で選びます。更新があれば engine / Control 等のインストールを行うため、実行前に更新内容を確認してください（`strata_cli/update_cmd.py:60-79,299-306`）。

## 値と既定値

- parser は `action="store_true"` で登録され、未指定時は `False`、指定時は `True` です。引数値は取りません。別名はありません（`strata_cli/update_cmd.py:77-79`）。
- 同じフラグを複数回指定しても真のままです。値を付ける構文はこの option の定義では受理されません（同箇所）。
- `strata update` にも同名・同動作の別 parser 定義がありますが、この文書の対象 scope は `strata components update` です（`strata_cli/update_cmd.py:67-69,77-79`）。

## 実行時の動作

`strata components update` は `strata_cli/update_cmd.py` で parser を作り、`strata_cli/cli.py` がその parser を登録します。`--json` と `--quiet` も後から同 parser 群に追加されます（`strata_cli/update_cmd.py:70-79`、`strata_cli/cli.py:139-140,508-515`）。実行時には `start_again` の真偽が `ModelGate` に渡されます（`strata_cli/update_cmd.py:347-350`）。

再起動が起きるのは、更新 gate が同意済みの実行中モデルを実際に停止して `stopped` に記録した場合だけです。更新候補がなければモデル gate の同意確認へ進みません。モデル停止後は、更新成功時には同じ設定で、更新失敗で変更もなかった場合には旧 engine 上で再起動を試みます（`strata_control/updater.py:1696-1710,1713-1726`、`strata_control/engine_update.py:353-363,376-405,412-431`）。

相互作用と適用範囲:

- `--stop-model` は更新処理が実行中モデルを停止する許可です。`--start-again` 単独では停止を許可しません。対話端末では停止確認が行われますが、確認できない実行（`--yes`、`--output json/jsonl`、または入出力が TTY でない場合）では、`--stop-model` がなければ実行中モデルを停止せず、終了コード 7 で拒否されます（`strata_cli/update_cmd.py:333-350`、`strata_control/engine_update.py:307-330`）。
- モデルが停止された後、対話端末では通常再起動を尋ねます。`--start-again` を指定するとその質問への同意として扱い、自動で再起動を呼び出します（`strata_control/engine_update.py:376-400`）。
- `--check` は feed の確認後に戻り、更新処理とモデル gate を呼ばないため、このフラグによる再起動はありません（`strata_cli/update_cmd.py:290-296`）。また engine / Control の対象更新がなくモデル gate が通らない場合にも、停止・再起動対象は作られません（`strata_control/updater.py:1677-1710`）。
- `--json` / `--output json` と `--output jsonl` では対話質問を行いません。`--start-again` は明示的な自動再起動指定としてなお使われますが、停止許可には別途 `--stop-model` が必要です（`strata_cli/update_cmd.py:98-107,333-350`）。

## 適用条件と副作用

- Strata が停止できると判定した実行中モデルに限ります。Strata が起動していないサービスや `strata serve` 等のモデルが実行中なら、更新 gate は終了コード 7 で拒否し、ユーザー自身で停止するよう案内します（`strata_control/engine_update.py:308-324`）。
- 更新中に新たなモデルが起動し、事前同意の対象外だった場合は、そのモデルを勝手に停止せず終了コード 7 で処理を拒否します（`strata_control/engine_update.py:334-352`）。停止後に engine が GPU 等の資源を解放するまで最大 120 秒待つ実装です。待ち切れなければ再起動・更新続行の前に終了コード 7 となります（`strata_control/engine_update.py:297-302,363-374`）。
- 再起動は保存済みのモデル設定を使う `start_model` 経路に委譲されます。開始に失敗した場合はモデルを停止状態のままにし、手動での開始方法を案内します（`strata_control/engine_update.py:397-405`）。
- 停止済みモデルの再起動に失敗し、更新自体は成功していた場合、終了コードは 8 となり、新 engine は有効のままです。更新処理自体が終了コード 6 で失敗していた場合は、その終了コードを保ちます（`strata_control/engine_update.py:412-431`、`strata_cli/update_cmd.py:13-15,302-306`）。

## 出力とエラー

- 人向け出力では、再起動を試す前に更新結果を表示します。再起動失敗があれば停止状態と手動開始の案内が出て、更新成功かつ再起動失敗のときは「更新済みだがモデルが再起動しなかった」旨を表示して終了コード 8 を返します（`strata_control/engine_update.py:397-405,422-431`、`strata_cli/update_cmd.py:302-306`）。
- JSON 系出力では `update_with_models` の結果に停止モデルと再起動結果が含まれます。失敗経路では `strata_cli/update_cmd.py` の `fail` が JSON のエラー object（`--output json/jsonl`）または stderr の `strata: ...`（human）を出し、該当する終了コードを返します（`strata_control/engine_update.py:408-432`、`strata_cli/update_cmd.py:98-107,233-242,307-319`）。
- 確認した代表的な失敗条件は、停止許可なしの実行中モデル（7）、更新中に新たに起動した未同意モデル（7）、再起動失敗（更新成功なら 8）です。その他の feed・署名・取得エラーの詳細は本 option 固有ではなく、例外ごとのコードで処理されます（`strata_cli/update_cmd.py:307-319`）。

## 根拠

- parser と `strata update` との同名 option: `strata_cli/update_cmd.py:59-79`
- Terminal parser 登録と共通 `--json` / `--quiet`: `strata_cli/cli.py:139-140,508-515`
- option 値の `ModelGate` への接続、対話可否・停止許可: `strata_cli/update_cmd.py:333-350`
- 実行中モデルの同意・停止要件、同意前の拒否: `strata_control/engine_update.py:292-332`
- 更新後の再起動、再起動失敗記録、終了コード: `strata_control/engine_update.py:376-432`
- 更新対象がない場合の gate 条件と update の各段階: `strata_control/updater.py:1677-1726`

調査範囲は上記 Strata checkout のソースです。別 OS での実モデル起動結果や、配布済み Release archive の個別挙動は実行・取得して確認していません。
