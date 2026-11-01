# `EDITOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

`EDITOR` は Strata のローカル管理 CLI で、一時 JSON ファイルを編集するエディタコマンドを指定します。対象は `strata profile edit NAME` と `strata ops edit NAME --profile PROFILE` です。いずれも保存済みプロファイルまたはレシピを読み込んだ後、`VISUAL` が空または未設定の場合に `EDITOR` を参照します。推論エンジン、サーバー、モデルの実行設定を直接変更する環境変数ではありません。

根拠: `strata_control/profiles.py:349-362`, `strata_control/recipes.py:299-312`, `strata_cli/cli.py:96-98,255-267,998-1005,1419-1422`。

## 値と判定

| 状態 | Strata の扱い |
|---|---|
| `VISUAL` が空でない | `EDITOR` は参照されず、`VISUAL` が使われる。 |
| `VISUAL` が未設定または空、`EDITOR` が空でない | `EDITOR` を使う。 |
| 両方が未設定または空 | プロファイル編集では `set VISUAL or EDITOR, or use strata profile set`、レシピ編集では `set VISUAL or EDITOR, or use strata ops set` という `ProfileError`。通常の終了コードは 2。 |
| 選択された値が空白だけなどで `shlex.split` の結果が空 | `VISUAL or EDITOR is empty` という `ProfileError`。通常の終了コードは 2。 |
| 選択された値を argv に分割できる | `shlex.split(editor, posix=os.name != "nt")` の結果をコマンドとし、末尾に一時 JSON ファイルのパスを追加して起動する。 |

値を真偽値や実行ファイル名一つとして単純に扱うのではなく、引用符などを考慮してコマンド文字列を分割します。変数展開やシェル実行はこの箇所では行いません。空文字の `EDITOR` は、`VISUAL` が空なら「未設定または空」と同じ経路になり、上記の「set VISUAL or EDITOR」エラーになります。`VISUAL` に空白だけが設定されている場合は truthy な選択値となり、分割結果が空なので「VISUAL or EDITOR is empty」になります。

根拠: `strata_control/profiles.py:351-356`, `strata_control/recipes.py:301-306`, `strata_control/profiles.py:30-35`。

## 有効になる条件

- `profile edit` または `ops edit` の実行時に限り参照されます。ほかの CLI コマンド、サーバーモード、backend、build macro、GPU やモデル状態による条件分岐はこの読み取り箇所にはありません。
- `VISUAL` に空でない値があれば、そちらが優先されます。`EDITOR` に CLI 引数、設定ファイル、別環境変数からの上書きを加える処理はありません。
- プロファイル編集は現在のプロファイルを `load()` した後、レシピ編集は対象レシピを `load()` した後にエディタ環境を評価します。
- 子プロセスは `subprocess.run` に `env` を渡されないため、Python の標準動作で現在のプロセス環境を継承します。エディタ文字列をシェルへ渡す指定はありません。

根拠: `strata_control/profiles.py:349-362`, `strata_control/recipes.py:299-312`, CLI の分岐 `strata_cli/cli.py:998-1005,1419-1422`。

## 実行時の詳細

エディタ起動前に、プロファイル編集ではプロファイルディレクトリ、レシピ編集ではそのレシピのディレクトリに一時 `.json` ファイルを作り、現在の内容を書き込みます。選択したコマンドにその一時ファイルのパスを引数として追加し、終了を待ちます。終了コードが 0 なら編集後の JSON を読み込んで検証し、保存します。正常終了後は一時ファイルを削除します。エディタが非 0 で終了した場合や、編集内容が不正な場合はドラフトを残して `ProfileError` を返します。プロファイル編集のエディタ非 0 終了は終了コード 6 です。レシピ編集も同じく非 0 終了をコード 6 とし、編集 JSON の読み込み・検証失敗は既定コード 2 です。

環境値は編集関数が呼ばれるたびに `os.environ.get` で読み、関数内またはプロセス内に結果をキャッシュしません。したがって、同一プロセス内で環境を書き換えた後に編集関数を再度呼べば、その時点の値が判定されます。

`ProfileError` は CLI の `_run` に捕捉され、通常出力では `strata: <エラー文>` を stderr に出して終了コードを返します。JSON 出力ではエラーオブジェクトを stdout に出します。コマンド起動などで `OSError` が発生した場合も `_run` が捕捉し、終了コード 6 とファイル操作エラーを報告します。子エディタの stdout/stderr は `capture_output` なしで起動されるため、Strata は内容を加工せず親プロセスの標準出力・標準エラーへ流します。

根拠: 一時ファイルと起動・検証・保持処理 `strata_control/profiles.py:357-379`, `strata_control/recipes.py:307-326`; CLI エラー処理 `strata_cli/cli.py:527-542,2166-2183`; プロファイル編集エラー既定コード `strata_control/profiles.py:30-35`。

## 根拠

- 候補名 `EDITOR` の本番コード参照は `strata_control/profiles.py:351-353` と `strata_control/recipes.py:301-303` の2箇所です。`rg -n --hidden --glob '!.git/**' 'EDITOR' .` で全参照を調べ、CLI の呼び出し元まで追跡しました。
- CLI の説明にも `profile edit` が `VISUAL` または `EDITOR` を使うことが記載されています（`strata_cli/cli.py:96`）。プロファイルおよびレシピの編集コマンドから、上記2関数がそれぞれ呼ばれます（`strata_cli/cli.py:998-1005,1419-1422`）。
- `docs/TERMINAL.md:120,156` は `ops edit` と `profile edit` のエディタ利用を説明しています。ここではコードで確認できた Strata の選択・起動・検証動作のみを記載しています。
