# `--data-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models explain` |
| オプション | `--data-dir` |
| 別名 | なし |
| 値 | データフォルダーのパス（文字列） |

## 役割

`strata models explain` がモデルファイルの所在を調べるデータフォルダーを、この呼び出しに限って指定します。`strata launch` が通常使うデータフォルダーを変更・移動・記憶するオプションではなく、別のフォルダーを調査した場合の探索結果を確認するための指定です。

## 使い方

```sh
# 指定したフォルダーの models 以下で IQ3_S の格納先を調べる
strata models explain IQ3_S --data-dir "$HOME/Strata-data"
```

## 値と既定値

値は `--data-dir` の後ろに置く任意の文字列です。parser は型変換や存在確認を行わず、未指定時の既定値も parser では設定しません。空文字列は処理側の真偽判定で未指定と同じ扱いになります。値がある場合は `Path(...).expanduser()` で `~` を展開しますが、絶対パス化はしません。相対パスはプロセスの作業ディレクトリを基準に扱われます。指定先が存在しない場合も拒否せず、探索先として処理します。

## 実行時の動作

`models explain` はモデル名と任意の `--family` をモデル表に照合してから、`--data-dir` が空でない場合はそのパスをデータフォルダーとして使います。指定がなければ、対象モデルのインストール済み run config に記録されたデータフォルダーを優先し、それがなければ Strata 共通のデータフォルダーを使います。明示したパスはこの探索先選択を上書きします。

選ばれたフォルダーの `models` 以下でモデル用フォルダーを探索します。通常のモデルでは setup の表記、run config の小文字 tag、同じ名前の大文字小文字違いの順に確認し、どれもなければ setup の表記をダウンロード先候補として返します。Hy4 / Inkling 系は family 名のフォルダーを確認します。見つかったモデルフォルダー直下の `.gguf` ファイル名とサイズを結果に含め、名前が `mmproj` で始まるファイルは picture reader として区別します。

このコマンドは結果を表示する調査用で、`--data-dir` に指定した場所へモデルを移動したり、設定として保存したりしません。出力形式は同じコマンドの `--output human|json` で選択します（既定は `human`）。JSON の場合は成功 payload にデータフォルダー、探索候補、見つかったファイル等が含まれます。

## 適用条件と副作用

値が有効なのは `strata models explain` のスコープです。`strata models explain NAME --data-dir DIR` の形で指定し、`strata launch` や他の `models` サブコマンドの保存先設定にはなりません。ファイル・ディレクトリーの存在確認とファイルサイズの読み取りは行いますが、このオプションによる書き込みやダウンロードはありません。探索先にアクセスできない場合、一部のディレクトリー列挙は「見つからない」ものとして結果に反映されます。なお、CLI 共通の起動処理は Windows で実行ユーザー向けにプロセスの既定 owner / DACL を設定します（このオプション固有の処理ではありません）。

## 出力とエラー

成功時は人間向けの説明または JSON を stdout に出し、終了コード `0` を返します。モデル名、family 名、または family とモデルサイズの組み合わせがモデル表に合わない場合は、エラーメッセージ（近い候補を含む場合があります）を返し、終了コード `2` になります。JSON 出力ではエラーも JSON payload です。処理中に捕捉されない `OSError` が発生した場合、共通エラー処理は終了コード `6` で報告します。parser が値を受け取れない場合などの引数構文エラーは argparse の usage error です。

## 根拠

- `terminal/strata_cli/cli.py:178`–`182` — `models explain` parser、引数名、`--family` / `--data-dir` / `--output` の登録と説明。
- `terminal/strata_cli/cli.py:581`–`589` — `--data-dir` を explain 関数に渡し、`ValueError` を終了コード `2` のエラーとして扱う分岐。
- `terminal/strata_cli/models_explain.py:23`–`37` — モデル名解決、明示パスの `expanduser()`、未指定時のデータフォルダー選択、探索処理への引き渡し。
- `terminal/strata_cli/launch/catalog.py:550`–`572` — モデル名・family の照合と不一致時の `ValueError`。
- `terminal/strata_cli/launch/catalog.py:592`–`621` — モデルフォルダー探索の順序、family 固有の場所、未発見時の fallback。
- `terminal/strata_cli/models_explain.py:38`–`61` — `.gguf` ファイルの列挙・サイズ取得、fallback 時のフォルダー一覧、返却データ。
- `terminal/strata_cli/models_explain.py:64`–`84` — 人間向け出力の構成。
- `terminal/strata_cli/cli.py:566`–`573` — stdout への human / JSON 出力と成功時の終了コード。
- `terminal/strata_cli/cli.py:2314`–`2324` と `terminal/strata_control/private_files.py:349`–`388` — 全コマンド共通の Windows 起動時に行う token owner / DACL 設定。
- `terminal/strata_cli/cli.py:2248`–`2265` — `ValueError` と `OSError` の共通エラー処理および終了コード。
