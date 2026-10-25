# `strata models move`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/models_move.py` |

## 役割

Strata が管理するモデル関連ファイルを、現在のデータフォルダーから別のフォルダーへ移します。対象は `models`、`packs`、`mtp` ディレクトリ内のファイルで、同じデータフォルダーにあるそれ以外のファイルは対象外です。移動が完了したモデルについて、インストール先で見つかった `strata-*.json` run config のパスも新しいフォルダーへ更新します（`strata_control/models_move.py:57-85,361-365,434-439`）。

## 使い方

```sh
# 移動先を検査して計画を表示
strata models move /mnt/strata-models --plan

# モデル関連ファイルを移動
strata models move /mnt/strata-models

# 実行中の移動を止めるためのファイルを指定
strata models move /mnt/strata-models --cancel-file /tmp/stop-model-move

# 中断状態を確認し、続行または取り消し
strata models move --status
strata models move --resume
strata models move --leave
```

`NEW_FOLDER` は通常の移動先です。省略時はエラーとなりますが、`--status`、`--resume`、`--leave` では省略できます。移動元は `--from OLD_FOLDER` で指定できます。省略時は Terminal CLI のデータフォルダー（設定・Desktop アプリ設定・`Documents/Strata` の候補に基づき、いずれもなければ `~/Strata`）が使われます（`strata_cli/cli.py:162-171,617-626`; `strata_control/discovery.py:241-289`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 計画表示 | `strata models move DEST --plan` | ファイル量、空き容量、移動可能性を表示します。移動は行いません。 |
| 新規移動 | `strata models move DEST` | 同一ボリュームならファイルを移し替え、別ボリュームならコピーを検証してから元ファイルを削除します。 |
| 状態確認 | `strata models move --status` | 現在のデータフォルダーに記録された未完了移動の状態を表示します。 |
| 再開 | `strata models move --resume` | 記録された移動元・移動先を使い、未完了分を続行します。 |
| 中断移動の取り消し | `strata models move --leave` | 移動元を完全な保管場所として残し、途中コピーを消すか、元ファイルが既に消えた分を戻します。 |

通常の移動では、`models`、`packs`、`mtp` の中の `.part` 以外のファイルを調べます。同一ボリュームでは `os.replace` による移動、別ボリュームでは一時 `.part` ファイルへのコピー、サイズと SHA-256 の検証、配置後の元ファイル削除という順序です。取得時の `.done` マークに SHA-256 があればそれとも照合します。既存の run config は、参照先ファイルが新フォルダーに存在し、旧フォルダーには存在しないパスだけを書き換えます（`strata_control/models_move.py:66-85,194-216,223-259,328-358,379-511`）。

## 主な動作・副作用

- 計画では移動元・移動先が同一、または一方が他方の内側にある場合を拒否します。別ボリュームへコピーするときは、必要容量をファイル総量の 105% として見積もります。同一ボリューム上の移動では追加容量を必要としません（`strata_control/models_move.py:137-184`）。
- 移動先に移動元と同じ相対パスのファイルが既にある場合、移動処理はそのファイルを置き換えます。同一ボリュームでは既存移動先を削除してから移し、別ボリュームでは検証済み `.part` を既存パスへ置き換えます（`strata_control/models_move.py:223-250,451-458,467-480`）。
- 通常移動前に移動先の古い `.part` ファイルを削除します。移動の状態は `models-move.json` として移動元・移動先に記録され、正常完了時に両方から削除されます（`strata_control/models_move.py:268-293,395-417,508-511`）。
- `--cancel-file PATH` は、指定パスが存在したときに安全な停止を要求します。移動中のファイルは未完成コピーを破棄し、既に移動済みのファイルは保持します。移動が完了していない場合、状態を記録して再開・取り消し可能にします（`strata_cli/cli.py:640-648`; `strata_control/models_move.py:223-258,441-521`）。
- `--leave` は中断時の状態ファイルに記録されたファイルだけを処理します。元にも存在する移動先コピーは削除し、移動元にないファイルは旧位置へ戻し、run config を旧フォルダーへ戻します（`strata_control/models_move.py:534-573`）。
- `--install-dir DIR` を指定すると、その既存インストールの run config だけが対象です。省略時は検出されたインストール群の run config を対象にします。インストール先の解決に失敗した場合、CLI は空の config 一覧で移動を続行します（`strata_cli/cli.py:635-640,685-689`; `strata_control/models.py:62-81`）。
- `--plan` の CLI 説明は「変更しない」としていますが、実装の計画処理は移動先を作成し、書き込み可否確認用の一時ファイルを作成・削除します。既に存在する内容の移動や run config 更新はしません（`strata_cli/cli.py:167-170,626-634`; `strata_control/models_move.py:123-133,137-169`）。

## 出力と失敗

既定の human 出力では移動中にファイル名と進捗を表示します。`--output jsonl` は進捗イベントと最終結果を JSON Lines で出力し、`--output json`（または alias の `--json`）は単一 JSON 結果を出します。`--quiet` は human の情報出力を抑制します（`strata_cli/cli.py:162-171,508-515,642-660,2217-2245`）。

移動先未指定は終了コード 2、計画・移動の失敗や中断移動がない状態での `--resume` / `--leave` は終了コード 5、キャンセルによる未完了停止は終了コード 6 です。`--status` は未完了状態がなくても終了コード 0 で「No move was interrupted」と返します。human 出力では移動エラーと未完了移動の再開・取り消し失敗は stderr に出ますが、`--plan` の拒否理由は stdout に表示されます。JSON 系出力では error オブジェクトを出力します（`strata_cli/cli.py:617-660,668-705,527-532`）。コピー検証、容量不足、読み書き失敗は移動エラーになり、未完成 `.part` は削除されます。途中まで処理したファイルは維持され、状態を保存して次回の再開・取り消しに備えます（`strata_control/models_move.py:223-258,512-531`）。

## 注意点

- 計画の書き込み確認により、未作成の移動先ディレクトリが作られる場合があります。計画表示はファイル移動をしないものの、移動先を完全に無変更で確認する用途ではありません。
- `--status`、`--resume`、`--leave` は、`--from` で指定したフォルダー（省略時は既定データフォルダー）にある状態記録を調べます。元の実行でカスタム移動元を指定した場合は、同じ `--from` を指定してください（`strata_cli/cli.py:617-622,668-705`）。
- `--output` は `human`、`json`、`jsonl` のみ受け付け、既定値は `human` です。移動のサブコマンドにはトップレベル parser から `--json` と `--quiet` も追加されます（`strata_cli/cli.py:162-171,508-515`）。

個別オプションは [`docs/cli/README.md`](../../../README.md) の `strata models move` 節にある各文書を参照してください。`strata launch` のデータフォルダー設定と `--move-data` は [`strata launch` 概要](../../launch/README.md) にまとめています。

## 根拠

- `strata_cli/cli.py:141-171` — `models move` の登録、位置引数とオプション定義。
- `strata_cli/cli.py:508-515,550-563,617-705` — 共通 `--json` / `--quiet`、コマンド振り分け、計画・移動・再開・取り消し、出力と終了コード。
- `strata_control/models_move.py:57-85,123-184,194-259,268-358,379-573` — 対象ファイル、容量・パス検査、コピー検証、run config 更新、状態記録、中断処理。
- `strata_control/discovery.py:241-289`、`strata_control/models.py:62-81` — 既定データフォルダーとインストール先の解決。
- 索引 [`docs/cli/README.md`](../../../README.md) — コマンド階層と option scope。ソースの parser と照合し、`models/move` の概要・列挙された各オプションは一致。

調査時点で `strata --help` は補助資料として実行していません。実装 checkout の parser と処理経路を根拠にしています。Release 配布物や他 OS 上の実動作は確認していません。
