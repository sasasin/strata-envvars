# `STRATA_VISION_ENCODE_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve` の Python サーバーが画像 encoder に `ENC` 要求を送った後、encoder の応答行を待つ秒数を指定します。既定は 300 秒です。待ち時間を超えて encoder が何も返さない場合、サーバーは encoder プロセスを終了し、画像読み取りの失敗としてその要求を処理します。これは encoder 起動時の `READY` 待ち時間ではありません（別変数 `STRATA_VISION_READY_S`）。

## 値と判定

値は Python の `float()` で変換されます。文字列全体を浮動小数点数として読めない場合は既定値 `300.0` に戻ります。空文字も変換に失敗するため既定値です。空白を含む数値文字列は `float()` が受理する形式なら有効です。

| 設定 | `VISION_ENCODE_S` の結果 | 動作 |
|---|---:|---|
| 未設定 | `300.0` | 最大300秒待つ |
| 有効な正数 | その浮動小数点数 | 指定秒数待つ |
| `0` または負数 | `None` | encoder 応答を無期限に待つ |
| 空文字、数値でない文字列 | `300.0` | 変換失敗として既定値を使う |

実装は有限値の検査や上限 clamp を行いません。したがって正の `inf` も正数として残ります。`nan` も `float()` で変換され、`v <= 0` に該当しないためそのまま残りますが、その特殊値を timeout に渡した際の具体的な待機挙動はこのコードから保証されません。

根拠: `serve/server.py:315-320,362-364`。

## 有効になる条件

- `serve/server.py` を読み込むサーバープロセスで評価されます。GPU/CPU encoder の別や OS による分岐はこの timeout 設定箇所にはありません。設定された vision encoder が `Vision.encode()` を使う画像処理で適用されます。
- DeepSeek V4.1 の `DsPictures` 経路は、encoder に画像を渡すのではなく `DsPictures.build()` で処理するため、この `Vision.encode()` の待ち時間設定は通りません（`serve/server.py:5235-5241`）。
- CLI 引数や vision 設定ファイルからこの値を上書きする処理は確認できません。`VISION_ENCODE_S` はモジュール変数として import 時に一度設定され、そのプロセス内で再読み込みされません。プロセス起動後に環境を書き換えても反映されません。

## 実行時の詳細

画像が未キャッシュなら、サーバーは画像ファイルを一時ディレクトリに書き、encoder の stdin に `ENC <画像ファイル> <出力ファイル>` を送り、`VISION_ENCODE_S` 秒以内に stdout の一行を待ちます。キャッシュ済み画像は encoder 待ちをせず返されます（`serve/server.py:3011-3026`）。

待ち時間を超えた場合は encoder を kill し、`RuntimeError`（`the image could not be read: it said nothing for N s`）を発生させます。`Vision.encode()` はそれを `ValueError` に変換し、encoder を停止状態として記録します。一時画像ファイルは削除されます。次に vision encoder が必要になったとき、停止状態を検出したサーバーは encoder を再起動します（`serve/server.py:2872-2892,3023-3034,4524-4528,4675-4681`）。

通常のリクエスト画像でこの `ValueError` が上がると、HTTP ハンドラーは `[strata] 400 invalid request: ...` を標準出力に出し、400 の invalid-request 応答を返します（Responses API は個別の Responses エラー形式に変換する経路があります。`serve/server.py:7544-7549,8071-8083`）。ツールが返した画像の場合は別扱いで、サーバーは画像をプロンプトから外して理由をログに出し、その箇所を `[image omitted: ...]` というテキストに置き換えます（`serve/server.py:5147-5179`）。timeout 専用の警告ログは `_readline()` 内にはありません。

## 根拠

- `serve/server.py:312,315-320,362-364` — timeout の説明、変換・fallback・無期限待ち規則、および既定値。
- `serve/server.py:3011-3043` — 画像 cache の確認、`ENC` 送信、timeout 適用、encoder 応答処理。
- `serve/server.py:2872-2892` — 有限待ち、encoder kill、timeout 例外。
- `serve/server.py:4524-4528,4675-4681` — 停止 encoder の検出と再起動。
- `serve/server.py:5147-5179,7544-7549,8071-8083` — ツール画像の省略、および通常リクエストのエラー応答。
- `serve/server.py:5235-5241` — DeepSeek V4.1 の `DsPictures` 経路。
