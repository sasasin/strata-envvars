# `STRATA_VISION_READY_S`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`serve/server.py` の Python サーバーが、画像 encoder 子プロセスから起動完了を示す `READY` 行を読むまでの待ち時間を秒単位で指定します。画像の encode 応答待ちを制御する `STRATA_VISION_ENCODE_S` や、engine の起動待ちを制御する `STRATA_ENGINE_READY_S` とは別です。画像 encoder が設定されていない構成では、この待ち処理は行われません。

## 値と判定

`_timeout_env()` は `os.environ.get(name, default)` を Python の `float()` に渡します。変換できない値は `ValueError` を捕捉して既定値に戻し、変換後の値が `0` 以下なら `None`（期限なし）にします（`serve/server.py:238-244,262-264`）。

| 環境変数の値 | 待ち時間 |
|---|---|
| 未設定 | 既定値 `300.0` 秒 |
| 有効な正の有限数 | その秒数。小数、指数表記も `float()` が受け付ける形式なら使える |
| `0` または負数 | 期限なし |
| 空文字、数値に変換できない文字列 | `ValueError` となり、既定値 `300.0` 秒 |

文字列全体が `float()` で解釈されます。部分的な数値の読み取りや整数への丸め、上限・下限への clamp はありません。前後空白は `float()` の規則で扱われます。`nan` / `inf` などの非有限値を明示的に拒否する検査もありません。非有限値を使った場合の待ち時間は通常の有限秒数として保証されていません。

CLI 引数や設定ファイルによる上書きはありません。環境変数が明示設定されていても空文字や不正値なら既定値です。

## 有効になる条件

サーバーが `serve.server` を import するときにモジュール定数 `VISION_READY_S` を設定します。したがって通常はサーバー起動前の環境設定が必要です。サーバー稼働中に環境を変えても値は再評価されず、lazy 起動や encoder 再起動でも同じ定数が使われます（`serve/server.py:262,2089-2098,2142-2151`）。

この値を読むのはサーバープロセスです。`Vision` に渡す `env` は encoder 子プロセス用ですが、この変数の parse は子プロセス生成より前に完了します（`serve/server.py:2092-2098,6385-6393`）。

## 実行時の詳細

encoder 起動時、サーバーは encoder を生成して標準出力を接続し、別スレッドで `stdout.readline()` を行いながら、`VISION_READY_S` を上限として結果を待ちます。最初の行が `READY` で始まれば起動済みになります。期限内に別の行が来た場合は「起動前に出力された行」として起動エラーになります（`serve/server.py:2089-2110,2112-2126,2036-2041`）。

期限切れでは encoder を `kill()` し、`RuntimeError` に `the vision encoder did not start: it said nothing for <秒> s` を含めて返します。起動処理は部分起動状態を避けるため `proc` を `None`、`stopped` を `True` に戻します。lazy 起動後や停止した encoder の再起動中に失敗した場合は、サーバーのロード経路が `EngineDied` として扱います（`serve/server.py:2124-2132,2097-2100,3126-3133`）。

値が `0` 以下の場合は `_readline()` に `timeout=None` が渡り、`queue.get()` は期限なしで待ちます。したがって `READY` を出さない encoder は、この待ちだけでは終了されません（`serve/server.py:238-244,2124-2132`）。

## 資料との照合

`docs/DETAILS.md` は lazy 起動では最初の生成リクエストまたは `POST /load` 時に、設定があれば画像 encoder を先に起動することを説明しています（`docs/DETAILS.md:1920-1927`）。確認した該当資料には、この変数の既定秒数や parse 規則の説明はありません。数値と timeout 時の処理は実装に基づきます。

## 根拠

- `serve/server.py:238-244,262-264`: 共通 timeout parser と `VISION_READY_S` の既定値。
- `serve/server.py:2089-2110`: encoder 起動、READY 判定、失敗時の状態初期化。
- `serve/server.py:2112-2132`: 読み取り、timeout、encoder 終了、例外内容。
- `serve/server.py:2142-2151,3126-3133`: 再起動とサーバーロード経路。
- `serve/server.py:6385-6393`: vision encoder の設定有無、lazy 起動、および子プロセス環境。
- `docs/DETAILS.md:1920-1927`: lazy 起動時の画像 encoder 起動順序。
