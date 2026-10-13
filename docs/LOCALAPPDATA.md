# `LOCALAPPDATA`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`START-HERE.bat` の Python 探索コードは、`LOCALAPPDATA` 配下のユーザー別 Python インストール先を候補にしています。ただし、現行バッチの制御フローではその行に到達しないため、通常の実行でこの環境変数は実効的な動作を変えません。Strata の Python アプリケーションや `setup.py` がこの変数を読む箇所もありません。

## 値と判定

到達可能な場合のコード上の扱いは、値を数値や真偽値として parse せず、`%LOCALAPPDATA%` をパス文字列に展開するものです。候補行は `Python313`、`Python312`、`Python311`、`Python310` の順に各ディレクトリ内の `python.exe` の存在を調べ、存在すれば `PY` に設定する形です。ただし、現行コードではこの候補行は通常の `:findpy` 呼び出しから到達不能です（次節）。したがって、下表は候補行の字面上の処理であり、通常実行時に観測される `LOCALAPPDATA` の効果ではありません。

| 状態 | バッチでの扱い |
|---|---|
| 設定済み | `%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe` の候補パスに展開し、`if exist` で確認します。 |
| 未設定または空文字 | バッチ内に専用の既定値やエラー処理はありません。空の値として同じパス式に展開され、各候補の存在確認が行われます。 |
| その他の文字列 | 値の形式・大文字小文字・内容の検証や正規化はありません。展開後のパスの存在だけを確認します。 |

## 到達性と有効になる条件

- `START-HERE.bat` は `.venv\Scripts\python.exe` がない場合に `:findpy` を呼びます。
- `:findpy` の47行目で `py -3` を実行した後、48行目は `if not errorlevel 1 set "PY=py -3" & goto :eof` です。`&` は cmd.exe のコマンド区切りなので、`goto :eof` は `if` の成否にかかわらず実行され、サブルーチンを終了します。
- このため、`py -3` の検査が成功しても失敗しても、通常の制御フローは49行目以降へ進みません。コメントが示す `python` / `PATH` および `LOCALAPPDATA` 配下の探索は実行されず、`LOCALAPPDATA` を設定してもこの経路の `PY` は変わりません。
- 47行目の `py -3` が成功した場合だけ `PY` は `py -3` に設定されます。失敗した場合は空のまま `:findpy` から戻り、呼び出し側は Python の自動導入へ進みます。

## 実行時の詳細

`START-HERE.bat` は `setlocal` の後、既存の仮想環境がなければ `:findpy` を呼びます。コメントと後続コードは `py -3`、`python`、`LOCALAPPDATA` 配下の候補の順に検出する意図を示しますが、48行目の無条件 `goto :eof` により現行実行では `py -3` の検査までで戻ります。成功時は `.venv` を作り、後続の起動では `.venv\Scripts\python.exe setup.py %*` を実行します。`LOCALAPPDATA` を変更する処理や子プロセス向けの個別上書きはこのバッチにはありません。

## 根拠

- `START-HERE.bat:7-10,31-40` — 既存仮想環境の判定、Python 検出後の仮想環境作成と `setup.py` 起動。
- `START-HERE.bat:44-52` — Python の検出処理と `LOCALAPPDATA` 配下の候補コード。特に48行目の `& goto :eof` が49–51行目の通常実行を遮ります。
- `&` が cmd.exe のコマンド区切りであることと `goto :eof` がバッチ末尾へ移動することは、[Microsoft の cmd コマンド資料](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmd)および [goto コマンド資料](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/goto)に記載されています。
- `setup.py:3703-3706` — 設定ファイルの Windows パスには `APPDATA` を使い、`LOCALAPPDATA` は参照しない。
- ソース全体での `LOCALAPPDATA` 完全一致検索では `START-HERE.bat:51` のみが該当しました。関連ドキュメント `README.ja.md:91,108` は Windows の起動入口として `START-HERE.bat` を案内していますが、この変数の個別動作は説明していません。
