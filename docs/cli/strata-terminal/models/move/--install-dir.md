# `strata models move --install-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--install-dir` |
| 別名 | なし |
| 値 | Strata installation のディレクトリパス。help/parser の説明は絶対パスを指定する形式 |
| 既定値 | 明示値なし。省略時は検出されたインストール群を対象にする（`STRATA_INSTALL_DIR` がある場合はその指定が優先される） |

## 役割

モデルデータの移動先を指定するオプションではありません。移動に伴ってモデルの run config 内に記録されたファイルパスを書き換える際、対象にする Strata installation を指定します。省略時は検出された installation 群の config が対象です（`strata_cli/cli.py:635-639`）。

## 使い方

```sh
strata models move /mnt/strata-models --install-dir /opt/strata
```

ここで `/mnt/strata-models` は移動先、`/opt/strata` は run config を探す installation ディレクトリです。まず変更せず移動計画を確認する場合は `strata models move /mnt/strata-models --plan` を使えますが、この経路では `--install-dir` は処理に使われません（`strata_cli/cli.py:623-634`）。

## 値と既定値

parser は値を取る引数として定義し、絶対パスの installation を説明しています。値の存在・絶対パス・ディレクトリかどうかの検証は parser ではなく `models.resolve_install()` が行います。空でない明示値は `~` を展開し、絶対パスかつ既存ディレクトリでなければ `ProfileError` を送出します（`strata_cli/cli.py:168`、`strata_control/models.py:62-72`）。

ただし move コマンド側では installation 解決全体を `except Exception` で捕捉して空のリストに置き換えるため、不正な値でも CLI エラーにはならず、run config の書き換え対象なしで移動処理が続きます（`strata_cli/cli.py:635-639`）。また空文字列は truthy でないため明示指定として扱われず、省略時の探索経路に入ります（同:636）。

値を省略した場合、`models.all_installs()` は installation を検出し、各 installation の run config 群を対象にします。環境変数 `STRATA_INSTALL_DIR` が設定されている場合は `resolve_install()` がそれを明示指定として扱い、その installation だけが返ります（`strata_control/models.py:62-81`）。

## 実行時の動作

`--install-dir` が truthy な値なら `models.resolve_install(value)` で一つの installation を解決し、そうでなければ `models.all_installs()` で候補を得ます。各 installation から `strata-*.json` を集めますが、`*.shared-settings.json` は除外します（`strata_cli/cli.py:635-639`、`strata_control/models_move.py:361-365`）。

移動処理は run config の JSON 値を再帰的に調べ、旧データフォルダ配下の `models`、`packs`、`mtp` のパスについて、新しい場所にファイルが存在し、旧場所には存在しなくなった場合に新パスへ置き換えます。変更があれば `<config名>.move-tmp` を書いてから元の config と置換します（`strata_control/models_move.py:328-358`）。モデルのグループが移りきるごと、および処理の完了・停止・失敗時に config の再ポイント処理を行います（同:434-439、504-530）。

`--resume` と `--leave` の経路でも同じ installation 選択が行われます。`--leave` は移動を取り消し、config 内のパスを新フォルダから旧フォルダへ戻します（`strata_cli/cli.py:668-705`、`strata_control/models_move.py:534-572`）。`--status` は中断状態を表示するだけで、installation や config を調べません（`strata_cli/cli.py:672-678`）。

## 適用条件と副作用

- config の再ポイントはモデルファイルが実際に移動済みで、移動先に同じ相対パスのファイルがあり、元の場所にはファイルがないパスに限られます。JSON が読めない場合や該当するパスがなければ、その config は変更されません（`strata_control/models_move.py:331-358`）。
- `--plan` は移動元・移動先の計画だけを評価して早期終了するため、`--install-dir` による config 探索や書き換えはありません（`strata_cli/cli.py:627-634`）。
- `--status` も `--install-dir` を参照しません。`--resume` と `--leave` では参照しますが、値が不正で installation 解決に失敗した場合は config を一件も集めず処理を続けます（`strata_cli/cli.py:621-622, 672-689`）。
- 実際の移動では config ファイルが書き換わるほか、モデルファイルを移動します。移動処理は同一ドライブなら rename、別ドライブならコピーを検証してから旧コピーを削除する実装です（`strata_control/models_move.py:1-8, 451-500`）。

## 出力とエラー

このオプション固有の不正値エラーは、move の呼び出し元が installation 解決例外を捕捉するため表面化しません。無効な installation を指定すると config の追従更新が省かれ得ますが、移動自体は続行します（`strata_cli/cli.py:635-639`）。

移動そのものが `MoveError` で失敗した場合、human 出力では stderr に `strata:` 付きのエラーを出し、JSON/JSONL 指定では JSON エラーを出して終了コード 5 になります。正常完了は 0、キャンセル等で未完了なら結果を出して 6 です（`strata_cli/cli.py:649-660`）。中断 move がない状態で `--resume` / `--leave` を使うと、stderr または JSON エラーを出して 5 になります（同:679-684）。

## 根拠

- parser とオプション説明: `strata_cli/cli.py:162-171`
- move、plan、installation/config 選択、出力・終了コード: `strata_cli/cli.py:617-660`
- status/resume/leave の分岐と config 選択: `strata_cli/cli.py:668-705`
- installation パスの検証と探索優先順位: `strata_control/models.py:62-81`
- 対象 run config の列挙、パス書き換え、書き込み: `strata_control/models_move.py:328-365`
- move の進行時・停止時・失敗時の config 追従: `strata_control/models_move.py:434-439, 504-530`
- leave 時の config 復元: `strata_control/models_move.py:534-572`

調査は上記 revision の Python parser と実装ソースに限定しました。CLI help の実行、build、テスト、実データを使った移動は行っていません。
