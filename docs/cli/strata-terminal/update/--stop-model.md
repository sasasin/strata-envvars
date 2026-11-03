# `strata update --stop-model`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--stop-model` |
| 別名 | なし |
| 値 | 値を取らないフラグ。未指定時は無効 |

## 役割

更新前に Strata のモデルが稼働中の場合、更新処理がそのモデルを停止することを許可します。稼働モデルを停止してよいという明示的な指定であり、停止後に再起動する指定は別の `--start-again` です。parser は `store_true` で定義されています（`strata_cli/update_cmd.py:60-69`）。

この文書は索引上の `strata update` スコープを扱います。同じオプションは `strata components update` にも個別に定義されていますが、リンク先は別文書です（`strata_cli/update_cmd.py:70-79`、[索引](../../README.md)）。

## 使い方

```sh
strata update --stop-model
```

スクリプトなど非対話実行で、停止後に同じ設定で再起動する場合は次のように指定します。

```sh
strata update --stop-model --start-again
```

## 値と既定値

値は不要です。`argparse` の `action="store_true"` なので、指定すると `stop_model=True`、省略時は `False` です。値の範囲や値に対する追加 validation はありません（`strata_cli/update_cmd.py:67-69`）。

## 実行時の動作

`strata update` は `update_cmd.run()` から更新処理に入り、`--check` の場合は更新候補を表示して終了するため、モデル停止ゲートには進みません（`strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:290-301`）。通常更新では、更新候補がある場合にダウンロード前の `consent()` が稼働モデルを確認します。`--stop-model` があれば、モデル停止の同意を得たものとして記録します（`strata_control/updater.py:1696-1710`、`strata_control/engine_update.py:292-332`）。

パッケージのダウンロード中はモデルを稼働させたままにし、ダウンロード後、最初の staging / test start の前に `release()` が同意済みモデルを停止します。停止は `runtime.stop()` に委譲され、停止後に残る起動トンネルも停止を試みます（`strata_control/engine_update.py:217-224,334-364`、`strata_control/updater.py:325-331`）。停止したモデルの再起動は別処理です。`--start-again` があれば更新の成否にかかわらず再起動を試み、なければ非対話実行では停止状態のままとなり、手動起動方法を表示します。対話端末では再起動を確認し、質問の既定値は「はい」です（`strata_control/engine_update.py:376-406`、`strata_cli/update_cmd.py:333-350`）。

`--yes` は質問を省略するフラグですが、単独ではモデル停止を許可しません。端末外または `--yes` 指定時にモデルが稼働していて `--stop-model` がなければ、更新は停止を拒否します（`strata_cli/update_cmd.py:67-69,333-350`、`strata_control/engine_update.py:317-324`）。JSON / JSONL 出力も対話質問を無効にするため、スクリプトでは必要に応じて `--stop-model` と `--start-again` を明示します（`strata_cli/update_cmd.py:98-107,333-350`）。

## 適用条件と副作用

- 稼働モデルがなければ、停止処理は発生しません。候補更新がなければモデル確認も行われません（`strata_control/updater.py:1677-1693,1696-1710`）。
- Strata が管理していないサーバー（サービス、`strata serve`、別プログラムなど）は自動停止できず、`--stop-model` を付けても更新を拒否します（`strata_control/engine_update.py:189-209,308-315`）。
- 同意後に新しいモデルがダウンロード中に起動した場合、そのモデルは同意対象に含まれません。対話時は追加確認できますが、同意が得られなければ停止ゲートで中断します。ダウンロード済みデータは保持されます（`strata_control/engine_update.py:335-352`）。
- `--stop-model` は更新許可の指定であり、自動再起動は行いません。スクリプトで再起動も行うには `--start-again` が必要です（`strata_control/engine_update.py:376-406`）。

## 出力とエラー

モデルが稼働中で停止を拒否された場合は終了コード `7`（変更なし）です。管理外サーバー、停止失敗、停止後に GPU / lease が解放されない場合も同じコードで中断します。停止失敗時には「稼働中の可能性がある」と報告し、解放待ちのタイムアウト時には再実行方法を案内します（`strata_control/engine_update.py:34-35,312-324,350-374`）。

停止後に再起動を選ばなかったモデルには手動起動方法が表示されます。再起動を試みて失敗し、更新自体は成功していた場合は終了コード `8` となり、新エンジンは使用中です。更新自体が失敗した場合はその更新エラーが返されます（`strata_control/engine_update.py:376-432`、`strata_cli/update_cmd.py:303-319`）。通常の human 出力では失敗メッセージを stderr に `strata:` 接頭辞付きで出し、JSON / JSONL では機械向け出力になります（`strata_cli/update_cmd.py:98-117,237-242`）。

## 根拠

- parser とオプション定義: `strata_cli/update_cmd.py:59-79`
- コマンドから更新処理への振り分け、`--check` の早期終了、ゲート生成: `strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:290-306,333-350`
- モデル稼働時の同意・停止・再起動: `strata_control/engine_update.py:189-224,292-432`
- ダウンロード前のモデル確認とダウンロード後の停止ゲート: `strata_control/updater.py:325-331,1696-1726`
- 確認範囲: 上記 revision の Strata Python parser と更新実装。CLI help、Release 配布物、各 OS 上の実行挙動は別途確認していません。
