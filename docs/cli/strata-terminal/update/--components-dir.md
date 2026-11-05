# `--components-dir`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納先のパス（文字列） |

## 役割

`strata update` が engine と Control の既存データを読み、更新状態・ダウンロード・展開先として使うコンポーネントルートを指定します。engine のディレクトリそのものではなく、Strata がその下に `engine/` や `.updates/` を配置するルートです。

```sh
strata update --components-dir /path/to/strata-components
```

## 値と既定値

parser は値を `str` のまま受け取り、既定値は `None` です。`choices`、型変換、存在確認、パスの正規化はこの parser にはありません。値が空文字列なら実行時の真偽判定で未指定と同じ扱いになります。相対パスは `Path` に渡され、その後 `resolve()` されずに使われます。`~` の展開など、追加のパス補正も Strata 側では確認できません（`strata_cli/update_cmd.py:47-57,284`）。

省略時は次の順で決まります。

1. `STRATA_COMPONENTS_DIR` が設定されていればそのパス。
2. 環境変数がなく、ソース checkout 内に engine package を含む `engine-feed/` があり、既定のユーザー用フォルダーに engine package がない場合は、その checkout の `engine-feed/`。
3. それ以外はユーザー用フォルダー。Windows は `%LOCALAPPDATA%\Strata\components`（`LOCALAPPDATA` がなければ home 以下）、その他は `$XDG_DATA_HOME/strata/components`（`XDG_DATA_HOME` がなければ `~/.local/share/strata/components`）。

明示した `--components-dir` はこれらの既定選択より優先します。環境変数とユーザー用フォルダーの規則は [`STRATA_COMPONENTS_DIR`](../../../envvars/STRATA_COMPONENTS_DIR.md) を参照してください（`strata_cli/update_cmd.py:255-270`、`strata_control/engine_component.py:176-186`）。

## 実行時の動作

`strata update` の parser は `_common()` からこのオプションを登録し、CLI dispatcher は `strata update` を `update_cmd.run()` に渡します（`strata_cli/update_cmd.py:47-64`、`strata_cli/cli.py:2144-2146`）。`run()` は指定値を `Path` にし、未指定なら上記の既定選択を行って `updater.Context.components` に設定します（`strata_cli/update_cmd.py:255-295`）。

このルートは engine の検出・既存状態の読取・更新排他ロック・一時ダウンロード・展開・状態保存などに使われます。たとえば更新チェックでも `.updates/update.lock` を作成し、feed の確認結果を `.updates/state.json` に保存します。そのため `--check` を付けてもコンポーネントルートは使用され、更新通知用の状態が書き込まれます（`strata_control/updater.py:136-160,172-208,663-674`）。ダウンロードの部分ファイルは `.updates/partial/`、engine の展開 staging は `.s/` 以下です（`strata_control/updater.py:494-496,690-710`）。

## 適用条件と副作用

- この説明は `strata update` のスコープです。同じ文字列は `strata components update` や他の `strata components` サブコマンドにも別 parser スコープで存在しますが、それらの動作をこの文書の対象には含めません（`strata_cli/update_cmd.py:59-95`、索引 [`docs/cli/README.md`](../../README.md) の各コマンド節）。
- 通常の更新では、指定したルート内の component state を更新し、feed から取得したファイルの一時保存・展開・engine/Control の配置に使います。パスの書込み権限や空き容量が不足すれば処理は失敗し得ます（`strata_control/updater.py:494-496,665-674,703-745`）。
- checkout 固有の `engine-feed/` 選択は、明示的な `--components-dir` または `STRATA_COMPONENTS_DIR` がない場合に限られます。環境変数があれば `engine_component.components_dir()` の選択をそのまま返します（`strata_cli/update_cmd.py:255-270`）。
- 値自体の妥当性検査を行う専用処理は確認できません。実際のファイル操作時に生じた `OSError` は CLI の一般エラー経路に入り、通常は終了コード 6 で報告されます。アクセス権エラーは既知フォルダー修復後に一度再試行される場合があります（`strata_cli/cli.py:2094-2113,2188-2195`）。

## 出力とエラー

このオプション自体は出力を追加しません。出力形式は `--output` / `--json` など他の設定に従います。更新処理の捕捉済みエラーは human 出力なら stderr の `strata: ...`、JSON 系なら標準出力のエラー object になり、`UpdateError` や feed/signature/acquisition error は各エラーコードを返します（`strata_cli/update_cmd.py:273-282,347-359`）。不正なパス文字列専用のエラー文は定義されていません。

## 根拠

- parser と既定値: `strata_cli/update_cmd.py:47-64`
- ルート選択、環境変数および checkout fallback、Context への設定: `strata_cli/update_cmd.py:242-295`
- CLI の dispatch と OS/file error の処理: `strata_cli/cli.py:2144-2146,2188-2195`
- per-user 既定値と `STRATA_COMPONENTS_DIR`: `strata_control/engine_component.py:176-186`
- state、lock、check、部分ダウンロード、stage: `strata_control/updater.py:136-160,172-208,494-496,663-674,690-745`
