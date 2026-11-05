# `--components-dir`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネントを探すディレクトリのパス（1 値） |

## 役割

切替候補となる導入済みエンジンを探すコンポーネント領域を指定します。`strata components use` は候補から指定エンジンを選び、以後の起動で使うエンジンを切り替えます。ダウンロードは行いません（`strata_cli/update_cmd.py:84-87`, `:398-423`）。

## 使い方

```sh
strata components use 0.1.54 --components-dir /mnt/strata/components
```

`engine` 位置引数にはバージョン、導入フォルダー名、または `newest` を指定します。同じバージョンの候補が複数ある場合は `--family qwen` または `--family deepseek` で絞れます（`strata_cli/update_cmd.py:84-87`; `strata_control/engine_library.py:198-211`）。

## 値と既定値

値は parser では単なる文字列として受け取り、`Path` に変換して使用します。パス形式や存在確認を行う parser-level validation はありません。相対パスはプロセスの現在ディレクトリ基準です。未指定または空文字列なら既定領域を使います（`strata_cli/update_cmd.py:49`, `:284`）。

明示値があれば `STRATA_COMPONENTS_DIR` より優先されます。未指定時は `strata_control.engine_component.components_dir()` が `STRATA_COMPONENTS_DIR`、Windows の `%LOCALAPPDATA%\\Strata\\components`、または Unix 系の `$XDG_DATA_HOME/strata/components`（未設定時 `~/.local/share/strata/components`）を選びます。さらに環境変数がなく、ソース checkout に自身の engine store があり、既定のユーザー領域に engine package がない場合は、その checkout の `engine-feed` が `strata update` 用 root として選ばれます。この checkout fallback は明示した `--components-dir` には適用されません（`strata_cli/update_cmd.py:255-270`; `strata_control/engine_component.py:176-186`）。

## 実行時の動作

この option は `strata components update`、`rollback`、`engines`、`use`、`remove`、`install-file` と `strata update` の共通 parser 定義です。ここでは `use` の挙動だけを扱います（`strata_cli/update_cmd.py:47-56`, `:59-95`）。実行時には選択された root を `Context.components` に渡し、一覧検索とエンジン切替に使用します（`strata_cli/update_cmd.py:284-296`, `:398-423`; `strata_control/updater.py:337-358`）。

Qwen 系エンジンは指定 root 内を走査し、同じ root の選択状態を参照・更新します（`strata_control/engine_library.py:91-123`, `:242-262`; `strata_control/updater.py:1303-1352`）。DeepSeek エンジンは保存済み run config や `STRATA_INSTALL_DIR` が指す領域も候補に含め、加えて指定 components directory の親にある `engine-dsv41` も調べます。そのため DeepSeek の候補全体が指定 root のみに限定されるわけではありません（`strata_control/updater.py:1455-1466`; `strata_control/engine_library.py:128-162`）。

`--backend` はハードウェア選択を上書きし、候補がこの PC で実行可能かの判定に関わります。`--family` は同一バージョンの曖昧さを解消します。`--wait` は実行中 server があるときの待機秒数を指定します（`strata_cli/update_cmd.py:50-52`, `:84-87`, `:286-296`; `strata_control/engine_library.py:64-80`, `:136-160`, `:198-211`）。

## 適用条件と副作用

候補が見つかり、現在の PC で実行可能な場合に切替処理へ進みます。Qwen では package の署名と全ファイルを検証してから切り替えます。DeepSeek では選択対象の engine を `--version` で起動確認してから pin を更新し、対象 engine と同種の保存済み run config を切替先へ向けます（`strata_control/engine_library.py:246-289`）。

切替時には指定 root の `.updates` に lock と `state.json` を作成・更新します。Qwen の選択状態、履歴、以前の engine 等を保存し、DeepSeek でも root の state に履歴を記録します。最新 engine を選んだ場合は pin を解除して以後の更新に追従し、それ以外では選択を pin します。保存 tuning preset は短い再確認対象として印が付く場合がありますが、削除はされません（`strata_control/updater.py:141-160`, `:172-210`, `:1303-1352`; `strata_control/engine_library.py:265-289`）。

実行中の model があると、対話端末では待機するか尋ねます。`--wait` 指定時はその時間だけ待ち、JSON 出力や非対話実行では待機確認をせず busy エラーになります。切替中にも idle を再確認するため、server が稼働中なら変更せず終了コード 7 になります（`strata_cli/update_cmd.py:443-458`; `strata_control/engine_library.py:216-239`）。

## 出力とエラー

- 一致する導入済み engine がない、または version 指定が複数候補に一致する場合はエラーコード 2。メッセージは `strata components engines` で一覧する方法や folder 名での指定を案内します（`strata_control/engine_library.py:198-211`）。
- PC で実行できない候補、署名・ファイル検証の失敗、DeepSeek engine の起動確認失敗はコード 5 です（`strata_cli/update_cmd.py:420-423`; `strata_control/engine_library.py:246-260`, `:265-279`）。
- 成功時は人向け出力で切替先と preset の扱いを表示します。`--output json` または `jsonl` では成功・失敗を JSON として出力します（`strata_cli/update_cmd.py:275-282`, `:423-433`）。
- 指定 path のアクセス権・I/O 失敗の詳細な表示と終了コードは、実行環境に依存する箇所までこの調査では実行確認していません。

## 根拠

- parser 定義、共通 scope、既定値: `strata_cli/update_cmd.py:47-56`, `:84-87`
- CLI から root を決め Context へ渡す処理: `strata_cli/update_cmd.py:255-270`, `:273-296`
- 候補探索、名前解決、適合条件: `strata_control/engine_library.py:91-123`, `:128-162`, `:180-211`
- Qwen / DeepSeek の切替と状態保存: `strata_control/engine_library.py:225-289`, `strata_control/updater.py:1303-1352`, `strata_control/updater.py:1455-1466`
- ソース checkout / per-user directory の既定解決: `strata_control/engine_component.py:176-186`, `strata_cli/update_cmd.py:255-270`

調査対象の `git status --short --branch` は `## main...origin/main`（clean）でした。CLI `--help` は実行せず、parser と実処理のソースを確認しました。OS ごとの実ファイル権限や I/O 失敗時の挙動は実機確認していません。
