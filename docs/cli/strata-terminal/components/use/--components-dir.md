# `--components-dir`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納先のパス（文字列） |

## 役割

このコマンドが導入済み engine を探し、使用する engine を切り替えるときのコンポーネント基準ディレクトリを指定します。既定値は per-user の格納先で、`STRATA_COMPONENTS_DIR` が設定されていればそちらが優先されます。

## 使い方

```sh
strata components use 0.1.54 --components-dir /path/to/strata-components
```

指定先に対象 engine が導入済みで、現在の PC で実行可能である必要があります。このコマンドはダウンロードを行いません。導入済み engine は `strata components engines --components-dir /path/to/strata-components` で確認できます。

## 値と既定値

- parser は文字列値を受け取り、既定値は `None` です。型・存在確認・書き込み可能性の事前 validation は parser にありません（`strata_cli/update_cmd.py:47-50,84-87`）。実行時に truthy な値があれば `Path` に変換されます（`strata_cli/update_cmd.py:244-245`）。
- 省略時は `strata_control.engine_component.components_dir()` を使います。同関数は `STRATA_COMPONENTS_DIR` が truthy ならその値を使い、それ以外は Windows で `%LOCALAPPDATA%/Strata/components`（`LOCALAPPDATA` がなければ home 配下）、その他の OS で `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）を返します（`strata_control/engine_component.py:176-186`）。
- 空文字列を明示すると `if a.components_dir` が偽となるため、指定先ではなく上記の既定解決に戻ります（`strata_cli/update_cmd.py:244`）。空白だけの値を trim したり正規化したりする処理はこの箇所では確認できません。
- 同じ option の複数指定時に独自処理はありません。独自の範囲・形式 validation や `--components-dir` と環境変数の併用時の警告も確認できません。

## 実行時の動作

`run()` は選択されたパスを `updater.Context.components` に渡します。`use` の実行経路ではその Context を使って導入済み engine 一覧を作り、指定された版番号または folder 名を解決します。従って、option は engine の選択対象となるコンポーネント格納先を変えます（`strata_cli/update_cmd.py:244-255,272-273,358-383`; `strata_control/engine_library.py:91-105,180-195,198-211`）。

- `--family qwen|deepseek` は同じ版番号が複数 family にある場合の絞り込みに使われます。`--backend` は PC の hardware 情報の backend を上書きし、導入済み engine の適合判定に影響します。いずれも `--components-dir` とは異なる選択条件です（`strata_cli/update_cmd.py:85-87,247-252`; `strata_control/engine_library.py:91-110,136-161,198-211`）。
- 指定した engine が既に使用中なら「already」となり、engine の切り替え state は更新されません（`strata_control/engine_library.py:242-254,265-276`）。別の engine への切り替えでは Qwen family は `.updates/state.json` に pin・前回選択・履歴などを保存します。最新の適合 engine を選ぶ場合は pin を外して更新追従に戻します（`strata_control/updater.py:172-210,1303-1352`）。DeepSeek family は選択状態をその family の `.chosen` に反映し、保存済み設定を選択 engine に向け直します（`strata_control/engine_library.py:265-289`）。
- 切り替え処理は指定コンポーネント格納先を単位に update lock を取得します。lock は `<components-dir>/.updates/update.lock` を作成して開くため、既にその engine が選択中の場合や後続処理が失敗する場合も、指定先への lock 作成が先行することがあります（`strata_control/engine_library.py:225-239`; `strata_control/updater.py:136-160`）。
- engine の一覧解決に失敗したり、指定先に該当 engine がない場合は選択に進みません。ダウンロードや engine package の削除はこの切り替え処理では行いません（`strata_control/engine_library.py:198-211,225-239,246-262`）。

## 適用条件と副作用

- この option は `strata components use` だけに閉じた parser 定義ではなく、`strata_cli/update_cmd.py` の `_common()` が `strata components` 配下の複数コマンドに追加する共通 option です。索引では各コマンド階層ごとに別文書として扱われています（`strata_cli/update_cmd.py:47-57,80-94`、索引 [`docs/cli/README.md`](../../../README.md) の `strata components use` 節）。
- 指定先の engine が現在の OS / backend に適合しない、または engine の検証に失敗する場合は選択できません。適合しない engine は CLI 側で exit code 5 の `UpdateError` になります。Qwen の切り替え経路は署名と全ファイル検証を行い、DeepSeek は起動確認を行います（`strata_cli/update_cmd.py:378-383`; `strata_control/engine_library.py:59-80,246-260,265-283`）。
- model が実行中なら切り替え前に idle を待ち、待機できない場合は Busy 系エラー（exit code 7）になります。実行中の model は起動時の engine のままです（`strata_control/engine_library.py:216-239`）。
- 指定先の `.updates` 以下に lock や state を書き込む可能性があります。ディレクトリへのアクセス権、パスの有効性、他プロセスとの競合に関する個別の事前検証は parser では行いません。

## 出力とエラー

- 成功時は通常出力で「Engine ... is now in use」または「already in use」を表示します。`--output json` / `--json` では JSON 結果を標準出力へ出します（`strata_cli/update_cmd.py:384-393`; `strata_cli/cli.py:508-515`）。
- 未導入・曖昧な engine 指定は `UpdateError` exit code 2、実行不可・検証失敗は code 5、実行中 model により切り替えられない場合は code 7 です（`strata_control/engine_library.py:198-211,216-221,246-260`; `strata_cli/update_cmd.py:307-311,378-383`）。JSON モードでは失敗を `ok: false` と error code/message を含む JSON にして出力し、通常モードでは `strata: ...` を標準エラーへ出します（`strata_cli/update_cmd.py:233-242`）。

## 根拠

- Strata `strata_cli/update_cmd.py:47-57,84-87,233-255,272-283,307-319,358-394` — parser、既定 path 解決、Context への適用、`use` の出力・例外処理。
- Strata `strata_control/engine_component.py:176-190` — `STRATA_COMPONENTS_DIR` と OS 別既定 path。
- Strata `strata_control/engine_library.py:91-123,128-162,180-211,216-289` — 対象ディレクトリ配下の engine inventory、fit 条件、指定 engine の検証・切り替え副作用。
- Strata `strata_control/updater.py:136-160,172-210,1303-1352` — lock と Qwen engine の永続 state。
- 調査範囲は上記 checkout の Terminal CLI parser と呼び出し先です。Release 配布物や OS ごとの実動作、ファイルシステム権限による失敗詳細は実行確認していません。
