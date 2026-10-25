# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets delete` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

プリセット削除の結果を、人向けの短いメッセージか JSON で表示します。出力形式だけを選び、削除対象や削除処理は変えません。

## 使い方

```sh
strata presets delete my-preset --output json
```

`my-preset` にはプリセット名、完全な ID、または4文字以上の一意な ID 接頭辞を指定できます。名前の照合は大文字・小文字を区別しません（`strata_control/presets.py:218-231`）。

## 値と既定値

- `human`: 人向けの削除完了メッセージを標準出力に表示します。省略時の既定値です。
- `json`: `{"schema_version":1,"ok":true,"deleted":"<preset-id>"}` を標準出力に表示します。
- その他の値は parser の `choices` により拒否されます。`--output` は `presets` の各サブコマンドに個別に定義されており、`delete` でも位置引数 `preset` とともに指定します。短縮別名はありません（`strata_cli/tune_commands.py:49-55,68-69`）。

## 実行時の動作

`--output json` のときだけ JSON モードになり、削除対象を検索してから削除処理を呼び出します。成功時、人向け出力は `Deleted '<name>'.`、JSON はプリセット名ではなく ID を `deleted` に格納します。どちらも終了コードは `0` です（`strata_cli/tune_commands.py:95-100,289-293,317-320`）。

削除処理はプリセットの保存先にある `active.json` の全スロットを調べ、削除 ID を履歴から除きます。削除対象が現役なら履歴の最後の ID を現役に戻し、履歴が空なら現役を `None` にします。その後 index を保存し、プリセット個別の JSON ファイルを削除します（`strata_control/presets.py:374-387`）。保存先は `STRATA_PRESET_DIR` が設定されていればその値、そうでなければプロファイルディレクトリの隣にある `presets` です（`strata_control/presets.py:45-50`）。

このコマンドはプリセット store のファイルと index を更新します。削除処理自体はエンジンを起動せず、モデルファイルやチューニング測定値を変更する処理は呼び出しません（`strata_control/presets.py:1-17,374-387`）。

## 適用条件と副作用

このオプションは `strata presets delete` における表示形式の指定です。削除対象が active だった場合、直前の履歴が active に戻るため、以後の起動時に適用されるプリセットが変わる場合があります。履歴からも削除 ID を除去します（`strata_control/presets.py:374-387`。active preset の起動時適用については同ファイル `:11-17,441-475`）。

個別ファイルの削除で `OSError` が起きても例外は握りつぶされます。その場合も index 保存が成功していれば呼び出し側は成功出力を返すため、ファイルが残る可能性があります。対して index の保存で失敗した場合は、削除処理から `OSError` が伝播してエラー経路になります（`strata_control/presets.py:207-208,374-387`）。

## 出力とエラー

- 存在しない名前・ID、曖昧な名前または ID 接頭辞の場合、`PresetError` を捕捉して終了コード `5` を返します。人向けモードでは `strata: <message>` を標準エラーへ、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":5,"message":"..."}}` を標準出力へ出します（検索エラー: `strata_control/presets.py:218-231`、エラー整形: `strata_cli/tune_commands.py:103-108,344-347`）。
- index 保存などの `OSError` は、通常は人向けモードで標準エラー、JSON モードで JSON エラーとして返り、終了コードは例外の `exit_code` 属性がなければ `2` です（`strata_cli/tune_commands.py:344-347`）。
- `--output` に `human` / `json` 以外を渡した場合は argparse が値を拒否し、通常の parser エラー（終了コード `2`）になります（定義: `strata_cli/tune_commands.py:53-55`、CLI の parser 呼び出し: `strata_cli/cli.py:2217-2231`）。

## 根拠

- `strata_cli/tune_commands.py:49-55,68-69` — `presets delete` parser と `--output` の値・既定値。
- `strata_cli/tune_commands.py:95-108,289-293,317-320,344-348` — 出力形式、削除の呼び出し、成功・失敗時の出力と終了コード。
- `strata_control/presets.py:45-50,218-231,374-387` — 保存先、対象の検索規則、active 履歴の更新とファイル削除。
- `strata_control/presets.py:11-17,441-475` — active preset の起動時適用についての説明と実装。
- `strata_cli/cli.py:2217-2231` — parser の実行と引数エラー経路。

調査時点で Strata checkout は `main`（`origin/main` と同期）で、`git status --short --branch` に未コミット変更はありませんでした。CLI の `--help` は補助資料として実行していません。記述は上記 commit の parser と実装を根拠にしています。
