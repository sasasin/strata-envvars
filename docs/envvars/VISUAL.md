# `VISUAL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のローカル管理 CLI で、保存済みプロフィールまたは ops レシピの一時 JSON を編集するコマンドを指定します。対象は `strata profile edit NAME` と `strata ops edit NAME --profile PROFILE` です。推論エンジンやサーバーの環境設定を直接変えるものではありません。

ソース内で値を読む箇所は `strata_control/profiles.py` と `strata_control/recipes.py` の各1か所です。CLI からそれぞれの関数が呼ばれます。候補一覧にある名前は実際に環境から読まれており、候補一覧との食い違いはありません。

## 値と判定

両編集経路とも `os.environ.get("VISUAL") or os.environ.get("EDITOR")` で選択します。Python の真偽値判定なので、未設定と空文字の `VISUAL` は `EDITOR` へフォールバックし、空でない `VISUAL` は `EDITOR` より優先されます。

| `VISUAL` | `EDITOR` | 結果 |
|---|---|---|
| 空でない | 任意 | `VISUAL` を使用。`EDITOR` は読みません。 |
| 未設定または空 | 空でない | `EDITOR` を使用。 |
| 未設定または空 | 未設定または空 | `ProfileError`。プロフィールでは `set VISUAL or EDITOR, or use strata profile set`、レシピでは `set VISUAL or EDITOR, or use strata ops set`。 |
| 空白のみ、または分割後に引数が残らない文字列 | 問わない | `shlex.split` 後に空となり、`VISUAL or EDITOR is empty`。 |

選ばれた値は `shlex.split(..., posix=os.name != "nt")` でコマンドと引数の列に分割され、文字列の全体一致、数値変換、真偽値 parse はありません。プロセス名と引数を別々に書けます。引用符の不整合など `shlex.split` の構文エラーは `ValueError` となり、CLI の通常エラー経路で終了コード 2 になります。コマンドの存在確認やシェル展開はこの処理では行いません。

## 有効になる条件

- `strata profile edit NAME` または `strata ops edit NAME --profile PROFILE` を実行したときだけ参照されます。プロフィール編集は `profiles.edit`、レシピ編集は `recipes.edit` を呼びます。
- OS による backend 差はありません。OS によって `shlex.split` の `posix` 引数が変わるだけです。
- これらの編集コマンドにエディタ指定 CLI 引数はありません。`VISUAL` が空でない場合は `EDITOR` より優先されます。
- 通常の `subprocess.run` 呼び出しで `env` は指定されないため、選択したエディタプロセスは親プロセスの環境を継承します。選択するコマンドの値は編集関数が呼ばれた時に読み、static cache はありません。

## 実行時の詳細

プロフィール編集では既存プロフィールを読み込んだ後に `VISUAL` を判定し、プロフィール保存先ディレクトリ内に一時 JSON を作り、選択したコマンド列の末尾へそのパスを追加して起動します。終了コード 0 の場合はファイルを JSON として読み、既存のプロフィール検証・revision 照合を経て保存します。正常終了後、一時ファイルを削除します。エディタが非 0 で終了した場合は一時ファイルを残し、終了コード 6 と `editor exited with status N; draft kept at PATH` をエラーにします。JSON 不正や保存時の検証失敗でも、修復用 draft を残します（`strata_control/profiles.py:349-379`）。

レシピ編集もレシピ保存先に一時 JSON を作って同様に起動し、終了コード 0 なら JSON を読み込んでレシピ検証・revision 照合後に保存します。非 0 終了では draft を残し、終了コード 6 と同じ形式のエラーにします。無効な JSON または保存時の検証エラーも draft を保持します（`strata_control/recipes.py:299-326`）。

両関数ともエディタ起動の `OSError` は CLI 共通処理で終了コード 6 に変換されます。空の指定や不正 JSON などの `ProfileError` は既定の終了コード 2 です。通常出力では `strata: ...` が stderr に出て、`--output json` では JSON エラーになります（`strata_control/profiles.py:30-35`, `strata_cli/cli.py:527-532,2166-2183`）。CLI のヘルプと利用者向け文書も両コマンドが `VISUAL` または `EDITOR` を使うと記載しています（`strata_cli/cli.py:96-98`, `docs/TERMINAL.md:120,156`）。

## 根拠

- 全読み取り箇所: `strata_control/profiles.py:351-356`, `strata_control/recipes.py:301-306`。
- 呼び出し元: `strata_cli/cli.py:998-1005,1419-1422`。
- エディタ起動と編集結果の処理: `strata_control/profiles.py:357-379`, `strata_control/recipes.py:307-326`。
- CLI エラー表示・終了コード: `strata_cli/cli.py:527-532,2166-2183`。
- CLI のコマンド定義: `strata_cli/cli.py:69-98,255-267`。
