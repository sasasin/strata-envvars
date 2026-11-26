# `TEMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata のサーバーは、HIP backend を使う子プロセス用環境を作るとき、設定された `TEMP` のディレクトリへ一時ファイルを作れるか確認します。値が空でないのに書き込み不能なら、ログファイルまたは作業ディレクトリの近くに作った `tmp`（作れなければ Strata のルートにある `tmp`）へ差し替えます。値が有効で書き込み可能なら変更しません。このチェックは HIP backend のみで、他 backend では `TEMP` を個別に検査・変更せず、子プロセス環境に渡します（`terminal/serve/server.py:4007-4010,4027-4028,4054-4062,4065-4095`）。

## 値と判定

`child_env` はプロセス環境をコピーし、プロフィールの `cfg.env` をその上に適用します。従って `TEMP` は親プロセスの値を引き継ぎ、プロフィールの `env.TEMP` があればその値が優先されます。HIP backend の `hip_env_guard` は `TEMP`、`TMP`、`TMPDIR` をそれぞれ `env.get(k)` で調べます。未設定と空文字はともに偽として検査対象外です。値の trim、パス正規化、文字列形式検証、大小文字変換はせず、非空の値を `_dir_writable` に渡して `tempfile.TemporaryFile(dir=p)` が成功するかで判定します。失敗する OS エラーは書き込み不可として扱います（`terminal/serve/server.py:4010,4027-4028,4078-4079`; `terminal/serve/server_parts/engines.py:1083-1088`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP backend の `TEMP` 検査 | 検査を行わず、値を新たに設定しない | 空でない値のディレクトリに一時ファイルを作れる場合（例: `C:\\Users\\me\\AppData\\Local\\Temp`、`/tmp`） | 空でない値のディレクトリに一時ファイルを作れない場合。`0`、`true` なども特別扱いせず、文字列が指すディレクトリで通常どおり検査 |
| HIP 以外 | Strata は個別検査を行わない | 子プロセス環境へ値を渡す | Strata による値の判定なし |

空文字と未設定は HIP の書き込み検査上は同じですが、`child_env` がその値をプロセス環境から削除するわけではありません。`TEMP` が無効で、置換先も見つからない場合、Strata は元の値を残します。`TMP` または `TMPDIR` だけが無効なら、その変数だけが差し替えられます（`terminal/serve/server.py:4078-4092`）。

## 有効になる条件

- ディレクトリ書き込みの検査・修正・警告は `cfg.backend == "hip"` のときだけ行います。CUDA、SYCL、CPU など HIP 以外の経路にはこのガードは適用されません（`terminal/serve/server.py:4054-4059`）。
- HIP でも `TEMP` が未設定または空文字なら `bad` に含まれません。`TEMP` 自体は設定されていても、`TMP` や `TMPDIR` のいずれかが書き込み不能なら、それらの無効な変数だけを同じ置換先へ差し替えます（`terminal/serve/server.py:4078-4089`）。
- 無効値の置換先は、`cfg.log`、それがなければ `cfg.cwd`、さらにそれもなければ `ROOT` を基準にした `tmp` が最初の候補です。そこへディレクトリを作成できず、または書き込み検査に失敗した場合は `ROOT/tmp` を試します。どちらにも書けなければ値を直さず、警告だけ出します（`terminal/serve/server.py:4080-4092`）。
- CLI 引数による `TEMP` の優先順位変更はありません。サーバー設定の `env` が親プロセス環境より優先され、HIP の検査・置換後の値がエンジン用環境になります（`terminal/serve/server.py:4010,4027-4028,4054-4059,9391-9394`）。

## 実行時の詳細

サーバーの `child_env` 呼び出しごとに `os.environ` のコピーから環境を組み立て、プロフィールの `env` を適用した後、HIP の場合に `hip_env_guard` を実行します。これは環境スナップショット作成時のチェックで、`TEMP` をプロセス起動後に監視・再読込する処理ではありません。通常の Strata engine 起動では作成した `env` を `StrataEngine` に渡し、分割起動の fallback でも `child_env` を再作成します（`terminal/serve/server.py:4007-4010,4027-4028,4054-4055,8820-8824,9391-9394`）。

空でない `TEMP` が書き込み不能で、置換用ディレクトリを用意できるときは、Strata は `TEMP` の値を置換してからエンジン環境として渡します。候補をどちらも使えない場合は元の `TEMP` を渡し続けます。`TEMP` を単独で既定ディレクトリに設定する処理はありません（`terminal/serve/server.py:4078-4092`）。

## ログと測定値

値を変更した場合、Strata は stderr に `strata serve: AMD: TEMP=<元の値> is not writable: using <置換先>` を出します。`TMP`/`TMPDIR` も同時に置換した場合は変数ごとに行を出します。置換先がない場合は `strata serve: AMD: TEMP, ... not writable (AMD's runtime needs a writable temporary folder)` の形で出し、元の値は維持します。値が unset、空、または書き込み可能ならこの `TEMP` に関する行は出ません（`terminal/serve/server.py:4087-4095`）。

## 根拠

- `terminal/serve/server.py:4007-4010,4027-4028,4054-4062` — 子環境の複製、プロフィール設定の適用、HIP 条件と返却。
- `terminal/serve/server.py:4065-4095` — HIP ガードの対象変数、置換先の順序、警告と stderr 出力。
- `terminal/serve/server_parts/engines.py:1083-1088` — 一時ファイル作成によるディレクトリ書き込み確認。
- `terminal/serve/server.py:8820-8824,9391-9394` — エンジン起動とサーバーモードでの子環境利用。
