# `strata components remove --components-dir`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント保存先を表すパス。文字列を `Path` に変換する |

## 役割

削除対象の engine を探すコンポーネント保存先を指定します。指定を省略すると通常のユーザー別保存先（または `STRATA_COMPONENTS_DIR`）を使い、source checkout に専用 engine store がある場合はその store が選ばれることがあります。別の保存先にある engine を削除するときに明示します（parser: `strata_cli/update_cmd.py:47-56,88-91`、保存先選択: `strata_cli/update_cmd.py:255-270,284`）。

## 使い方

```sh
strata components remove 0.1.54 --components-dir /path/to/strata-components
```

`engine` には engine の版番号または folder 名を指定します。削除コマンドなので、実行前に `strata components engines --components-dir /path/to/strata-components` で対象を確認してください（登録: `strata_cli/update_cmd.py:88-91`、一覧出力: `strata_cli/update_cmd.py:403-416`）。

## 値と既定値

- 値は必須の文字列で、parser は既定値を `None` とします。型変換や存在確認の validation は parser では行わず、値が truthy なら `Path(a.components_dir)` に変換します（`strata_cli/update_cmd.py:49,284`）。相対パスはプロセスの作業ディレクトリ基準です。
- オプションを省略するか空文字列を渡した場合は、`default_components_dir()` の結果を使います。`STRATA_COMPONENTS_DIR` が設定されていれば `engine_component.components_dir()` がその値を先に選びます。環境変数もなければ通常は Windows の `%LOCALAPPDATA%/Strata/components`（未設定時は home 配下）、または `XDG_DATA_HOME/strata/components`（未設定時は `~/.local/share/strata/components`）です（`strata_control/engine_component.py:176-186`）。
- 明示した `--components-dir` は環境変数より優先します。省略時、環境変数がなく、checkout 内の `engine-feed` に engine があり、ユーザー別保存先に engine がない場合は checkout 内 `engine-feed` を選びます（`strata_cli/update_cmd.py:255-270,284`）。
- 同じオプションを複数回指定した場合の値は `argparse` の通常動作に従い、最後に指定した値になります。独自の重複指定処理はありません（`strata_cli/update_cmd.py:49`）。

## 実行時の動作

選ばれたパスは `updater.Context.components` に設定され、`strata components remove` の engine 一覧検索と削除処理へ渡されます（`strata_cli/update_cmd.py:284-295,398-418`）。Qwen 系 engine はそのパスの `engine/` 以下から検索されます。DeepSeek engine は保存済み run config と `STRATA_INSTALL_DIR` も探索し、追加で `<components-dir の親>/engine-dsv41` を調べます。そのため DeepSeek の列挙・削除範囲は指定パス直下だけとは限りません（`strata_control/engine_component.py:988-1001`、`strata_control/updater.py:1455-1466`、`strata_control/engine_library.py:91-123,128-162`）。

対象は `engine` の版番号か folder 名で照合されます。版番号が複数の engine に一致する場合や対象が見つからない場合はエラーになり、folder 名を使うよう案内されます（`strata_control/engine_library.py:198-211`）。削除時は component 保存先の update lock を取得し、対象 folder を一時名 `.deleting-<id>` に rename してから削除します（`strata_control/engine_library.py:294-317`）。

## 適用条件と副作用

- 指定パスの書式・存在・書き込み権限を事前に検証する専用処理はありません。Qwen engine の scan は `engine/` を読めない場合に空一覧を返すため、誤ったパスや読めないパスでは engine が見つからない結果になり得ます（`strata_cli/update_cmd.py:284`、`strata_control/engine_component.py:988-1001`）。
- 現在使用中の engine、または実行中のプログラムが使っている engine は削除できません。対象 engine folder はファイルシステムから削除されます。Qwen engine では `.updates/state.json` の previous/pinned 情報や該当 version の failed 情報を更新し、削除履歴を保存します。DeepSeek engine では、残存する engine がない場合に stale pin を解除します（`strata_control/engine_library.py:167-176,294-334`）。
- モデル、設定、別 family の engine は削除処理の対象外です（`strata_control/engine_library.py:294-296`）。
- 指定 path の親・子関係や symlink に関する追加制限は、このオプションの parser および削除処理では確認できません。実際の rename・削除の可否は OS のファイル操作結果に依存します（`strata_cli/update_cmd.py:49,284`、`strata_control/engine_library.py:310-318`）。

## 出力とエラー

成功時、人間向け出力は削除した engine と解放容量を表示します。`--output json` / `--output jsonl` または共通の `--json` を使う場合は成功 JSON を出力します（`strata_cli/update_cmd.py:98-107,435-440`）。

対象なし・曖昧な版番号・使用中の engine は終了コード 2、rename に失敗して削除できなかった場合は終了コード 6 で失敗します。後者は「何も変更していない」と報告します。これらのエラーは人間向けでは stderr の `strata:` メッセージ、JSON 出力では `ok: false` と error object になります（`strata_control/engine_library.py:198-210,294-316`、`strata_cli/update_cmd.py:277-282,347-351`）。

## 根拠

- parser と remove 登録: `strata_cli/update_cmd.py:47-56,88-95`
- 既定保存先と source checkout fallback: `strata_cli/update_cmd.py:255-270,284`
- 環境変数・ユーザー別保存先: `strata_control/engine_component.py:176-186`
- command dispatch と共通出力 option: `strata_cli/cli.py:510-518,2144-2146`
- engine 検索・削除対象判定・rename と state 更新: `strata_control/engine_library.py:91-123,128-162,167-176,198-211,294-334`
- Qwen engine scan と DeepSeek 探索範囲: `strata_control/engine_component.py:988-1001`、`strata_control/updater.py:1455-1466`
