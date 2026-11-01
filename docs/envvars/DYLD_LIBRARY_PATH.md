# `DYLD_LIBRARY_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

Strata の engine updater が、macOS 上でステージ中の engine をモデルなしで起動確認するとき、子プロセス用の `DYLD_LIBRARY_PATH` を組み立てます。パッケージ内のライブラリディレクトリを先頭に置き、呼び出し元プロセスに既に設定されている値は後ろに残して、engine の `--version` 起動に渡します。Strata の通常の推論処理がこの変数を設定・解釈する実装は確認できません。

## 値と判定

この経路は環境変数の値を真偽値や数値として判定しません。macOS では `sys.platform == "darwin"` の場合に変数名を選び、`os.environ` の値を文字列として子プロセス環境へ連結します。

| 呼び出し元の状態 | 子プロセスに設定される値 |
|---|---|
| `DYLD_LIBRARY_PATH` 未設定 | パッケージのライブラリディレクトリを `os.pathsep`（macOS では `:`）で連結したものの後ろに `:` が付く |
| 空文字で設定 | 未設定時と同じ結果。`env.get(var, "")` は空文字を返す |
| 空でない値 | パッケージのディレクトリ群、`:`, 元の値の順 |

パッケージのディレクトリ群は engine のルートを含み、`BUILD.json` の `lib_dirs` にある相対パスのうち、空でなく、絶対パスでも `..` を含むパスでもなく、実在するディレクトリを追加します。重複するディレクトリは追加しません。変数値自体の parse、正規化、妥当性検証、上限値、CLI 引数との優先順位はありません。既存値を後ろに付加するため、置換はしません。

根拠: `strata_control/updater.py:766-770`、`strata_control/engine_component.py:155-171`。

## 有効になる条件

- `binary_smoke()` は updater の既定テスト起動経路で、モデル設定が見つからず、かつ `ctx.allow_no_model_smoke` が有効な場合に呼ばれます。このとき engine に渡す引数は `--version` だけです。
- updater が macOS 上で動いている場合（`sys.platform == "darwin"`）に限って `DYLD_LIBRARY_PATH` を組み立てます。Windows は `PATH`、その他の platform は `LD_LIBRARY_PATH` を選びます。
- モデル設定がある場合の既定テストは隔離 runtime から engine を起動し、必要なら 1 token の probe も行います。この経路は `binary_smoke()` を通らないため、ここで説明した明示的な `DYLD_LIBRARY_PATH` の前置処理は行われません。
- updater の `ctx.test_start` に独自 runner が渡されている場合はその runner が呼ばれ、`default_test_start()` / `binary_smoke()` を使うとは限りません。

根拠: `strata_control/updater.py:948-956,971-986,1068-1080`。

## 実行時の詳細

`binary_smoke()` の呼び出しごとに `os.environ` をコピーし、選択した変数へパッケージのライブラリディレクトリを前置します。親プロセスの `os.environ` 自体は書き換えません。組み立てた環境は `subprocess.run()` の `env` として渡され、作業ディレクトリを package root にして `component.exe --version` を実行します。既定 timeout は 60 秒です。static cache はなく、各呼び出し時点の環境を読みます。

起動時の `OSError` / `SubprocessError`（timeout を含む）は `TestStartFailed` に変換されます。終了コード 0 は binary-only の成功です。終了コード 2 でも stdout/stderr に少なくとも 5 個の option 行があれば、旧 engine が `--version` に答えず usage を出したケースとして起動確認を成功扱いします。それ以外の非ゼロ終了では stderr（空なら stdout）の末尾行を最大 200 文字で `TestStartFailed` の理由にします。updater はこの失敗を状態履歴に記録し、engine の test-start failure として伝播します。テスト起動に失敗した場合は engine の切り替え処理へ進みません。

このコードが示すのは子プロセス環境への値の設定と起動確認までです。`DYLD_LIBRARY_PATH` を受け取った後の loader や外部ライブラリの探索規則は Strata の動作として扱っていません。

根拠: `strata_control/updater.py:763-785,1075-1096`。

## 根拠

- `strata_control/updater.py:763-785` — platform 別の環境変数名選択、親環境のコピー、パッケージディレクトリと既存値の連結、子プロセス起動、戻り値と失敗判定。
- `strata_control/updater.py:948-956` — モデルなし時に `binary_smoke()` を使う条件。
- `strata_control/updater.py:1068-1096` — staged engine の test-start 呼び出しと失敗記録。
- `strata_control/engine_component.py:155-171` — パッケージからライブラリディレクトリ一覧を作る規則。
