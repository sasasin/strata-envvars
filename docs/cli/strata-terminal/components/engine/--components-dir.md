# `--components-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネントフォルダーのパス（文字列）。parser に型・選択肢・存在確認の指定はない |

## 役割

このコマンドがエンジンコンポーネントを探すルートフォルダーを指定します。指定先の `engine/` 以下にあるローカルのパッケージを走査し、この PC で利用できるものを報告します。コマンドは読み取り専用で、エンジンをダウンロードしません（`strata_cli/cli.py:132-138,2014-2020`、`strata_control/engine_component.py:1-16,780-793`）。

## 使い方

```sh
strata components engine --components-dir /srv/strata/components
```

JSON で結果を受け取る例:

```sh
strata components engine --components-dir /srv/strata/components --output json
```

このオプションは `components engine` の parser に属します。兄弟サブコマンドや `strata update` の同名オプションとは別のスコープです（`strata_cli/cli.py:114-140`）。

## 値と既定値

- 値は `argparse` が受け取る文字列です。`type`、`choices`、必須指定、パス検査は parser に設定されていません（`strata_cli/cli.py:132-138`）。
- 省略時、または空文字列の場合は明示パスを使わず、`strata_control.engine_component.components_dir()` の既定先を使います。まず `STRATA_COMPONENTS_DIR` が設定されていればその値を使い、そうでなければ Windows では `%LOCALAPPDATA%\Strata\components`（未設定ならホーム配下）、その他では `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）です（`strata_cli/cli.py:2017-2020`、`strata_control/engine_component.py:176-186`）。
- 空でない明示値は `Path(value)` に渡され、環境変数や既定先より優先します。相対パスを絶対化したり、`~` を展開したりする処理はこの経路にはありません（`strata_cli/cli.py:2017-2020`）。
- 存在しない、または読み取りできないディレクトリを parser 段階で拒否する検証はありません。`engine/` の走査で `OSError` が起きると空の一覧として扱われ、通常は利用可能エンジンなしの報告になります（`strata_control/engine_component.py:780-793,969-988`）。

## 実行時の動作

CLI は指定値を `Path` にし、`engine_component.status(root, backend=..., full=...)` に渡します。status はそのルートの `engine/` 配下を列挙し、各パッケージの `engine-component.json` を読みます。選択候補は OS/プラットフォーム、backend、Control の最低バージョン、GPU アーキテクチャやドライバー条件などに照らして判定されます（`strata_cli/cli.py:2014-2022`、`strata_control/engine_component.py:780-793,859-944,969-988`）。

指定ルートは一覧・整合性確認のほか、同じルートにある rollback pin、前回更新状態、キャッシュ済み更新通知の参照にも使われます（`strata_control/engine_component.py:202-225,228-246,969-981`）。関連オプションとの関係は次のとおりです。

- `--backend` は候補選択に使う backend を指定します。省略時は自動検出されます。`--components-dir` は検索場所を選び、backend 選択は変更しません（`strata_cli/cli.py:134-136,2018-2020`、`strata_control/engine_component.py:869-881`）。
- `--full` は通常 entrypoint だけの SHA-256 検証を全ファイルに広げます。ファイルサイズ等の検査は通常時にも行われます（`strata_cli/cli.py:137,2020`、`strata_control/engine_component.py:402-427`）。
- `--output` は人向け表示と JSON を切り替えます。JSON には選択されたコンポーネントルート（`components_dir`）と利用可否などが含まれます（`strata_cli/cli.py:138,2024-2041`、`strata_control/engine_component.py:977-981`）。

## 適用条件と副作用

この指定は `strata components engine` の状態照会だけに適用されます。ローカルのディレクトリ、manifest、コンポーネントファイル、およびキャッシュ状態を読み取ります。コード上、この照会がファイルを書き換えたり、取得処理を開始したりする経路はありません。出力にも「何もダウンロードまたは変更していない」と表示されます（`strata_cli/cli.py:2014-2016,2040`、`strata_control/engine_component.py:1-6,969-988`）。

状態報告時には backend 検出が行われ、解決処理では対象 backend に応じたローカル環境の GPU/driver 情報照会が行われる場合があります（`strata_control/engine_component.py:973-976,869-880`）。ネットワーク取得はこのコマンドの動作に含まれません。

## 出力とエラー

- 利用可能な engine があれば終了コード `0` で、human 形式ではコンポーネントフォルダー、PC/backend、インストール済み候補、選択 engine を表示します。JSON 形式では `ok: true` と状態レポートを出します（`strata_cli/cli.py:2023-2035`）。
- 利用可能な engine がない、または候補がプラットフォーム/backend/整合性等の条件を満たさない場合は、終了コード `5` です。human 形式では notice を標準エラーへ、JSON 形式では `ok: false` を含む状態レポートを標準出力へ出します（`strata_cli/cli.py:2023-2036`、`strata_control/engine_component.py:918-936,982-988`）。
- `engine/` を列挙できない場合も `scan()` は空一覧を返すため、通常は上記の「利用可能 engine なし」経路になります。壊れた manifest は問題一覧に記録されます（`strata_control/engine_component.py:780-793`）。
- `status()` から `ComponentProblem` が伝播した場合、CLI は終了コード `2` として human なら `strata: ...` を標準エラーへ、JSON 指定時なら error オブジェクトを標準出力へ出します（`strata_cli/cli.py:2019-2022,527-532`）。

## 根拠

- parser と help 文言: `strata_cli/cli.py:132-138`
- parser 値から `Path` 化して status に渡す箇所、および終了・出力処理: `strata_cli/cli.py:2014-2041`
- 環境変数と OS 別既定フォルダー: `strata_control/engine_component.py:176-186`
- 指定ルートの走査、パッケージ検証、候補選択、status レポート: `strata_control/engine_component.py:780-793,859-944,969-988`
- 関連状態ファイルの読み取り: `strata_control/engine_component.py:202-246`

この文書は指定 revision のソースを根拠にしています。Release 配布物や異なる platform 上での実機実行は照合していません。
