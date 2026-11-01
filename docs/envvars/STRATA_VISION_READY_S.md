# `STRATA_VISION_READY_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`serve/server.py` が画像用の外部 vision reader を起動した後、その reader が `READY` 行を返すまで待つ秒数を設定します。既定値は 300 秒です。期限内に何も返さない場合は reader プロセスを kill し、サーバー側で起動失敗として扱います。これは Strata の Python サーバーの待機時間であり、reader 内部の処理時間設定ではありません。

候補一覧には名前があります（`docs/envvars/000_envvers.md:1646`）。Strata ソースでの実参照は `serve/server.py:312,362` で、コメントと `_timeout_env` の引数です。名前を動的に受ける helper の定義は `serve/server.py:315-320` です。

## 値と判定

`_timeout_env` は `os.environ.get(name, default)` の結果を Python の `float()` に渡し、`ValueError` のとき既定値へ戻します。その後 `v <= 0` なら `None`（無期限待ち）、それ以外なら数値を返します。既定値は `300.0` です（`serve/server.py:315-320,362`）。

| 環境変数の状態・値 | `VISION_READY_S` | 結果 |
|---|---:|---|
| 未設定 | 300.0 | 300 秒待つ |
| 空文字、数値でない文字列 | 300.0 | `float()` の `ValueError` を捕捉し、既定値へ戻る |
| `0`、負数 | `None` | `_readline` が timeout なしで待つ。従来どおり無期限待ち |
| 正の数値 | その float 値 | 指定秒数待つ。整数への丸めや上限 clamp はしない |

`float()` が認識する表記を使い、文字列全体を数値として解釈します。たとえば前後空白のある数値や指数表記は変換できますが、数値の後ろに余分な文字があれば変換失敗して既定値になります。`NaN` / `Infinity` なども有限性の検査はなく、`v <= 0` の判定を通った値がそのまま待機関数へ渡ります。これら非有限値を意図した設定として扱う分岐はありません。

## 有効になる条件

- `serve/server.py` のサーバープロセスで有効です。変数はモジュール読み込み時に `VISION_READY_S` へ格納されます。その後の環境変更を再読込するコードはありません（`serve/server.py:362`）。
- `Vision` オブジェクトが作られる必要があります。`Service` 初期化は `cfg.get("vision")` が真のとき Vision reader を構成します（`serve/server.py:9202-9224`）。`Vision.__init__` は `lazy` でなく、かつ `elastic` でない場合にその場で起動します（`serve/server.py:2770-2790`）。lazy または elastic の構成では起動が遅延し、後の reader 起動時に同じ値が使われます。
- 実際の適用箇所は GPU/CPU の reader に共通する `_start_reader` です。GPU reader の起動が失敗して CPU fallback が設定されている場合、fallback reader の起動にも同じ `VISION_READY_S` が適用されます (`serve/server.py:2830-2857`).
- サーバーが vision reader を持たない場合、この待機はありません。画像を送ると reader がない旨のエラーになります（`serve/server.py:5221-5226`）。DeepSeek-V4.1 の `DsPictures` 経路はエンジン内蔵 tower に画像を渡し、通常の `Vision.encode()` を通らないため、この reader の READY 待機も対象外です（`serve/server.py:5235-5242`）。
- CLI 引数や設定ファイルから `VISION_READY_S` を上書きする処理は確認できません。別名の `STRATA_VISION_ENCODE_S` は画像 encode 応答の待機用であり、この変数とは別設定です（`serve/server.py:362-364,3023-3029`）。

## 実行時の詳細

`_start_reader` は `popen()` で reader を起動し、その標準出力の1行を別スレッドで読みます。`_readline` は `queue.get(timeout=...)` で待ち、期限切れではプロセスを kill して `RuntimeError` を送出します。`None` が渡る場合は queue の無期限待ちになります（`serve/server.py:2844-2857,2872-2892`）。応答が `READY` で始まらない場合も起動失敗で、プロセスを停止し `vision_start_error()` のメッセージを返します（`serve/server.py:2858-2869,2703-2742`）。

timeout の場合、`_start_reader` は `self.proc` をクリアして停止状態にし、正の timeout なら `vision_start_error(..., waited=VISION_READY_S)` に変換します。通常はそのエラーが `_start()` に戻り、CPU fallback があれば警告ログを出して fallback を起動します。fallback がない場合は呼び出し元へ伝播します（`serve/server.py:2830-2842,2852-2857`）。モデル再ロードに伴う Vision 再起動時は、エラーを `EngineDied` として送出する経路があります（`serve/server.py:4675-4682`）。

`Vision` の初回起動はサーバーの画像機能初期化時、遅延起動なら画像リクエスト時です。画像エンコード要求への待機時間は別変数 `STRATA_VISION_ENCODE_S` によって定まり、`STRATA_VISION_READY_S` はその値を変更しません（`serve/server.py:3023-3029,362-363`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:1644-1647`
- helper の変換・既定値・無期限判定と定数設定: `serve/server.py:312-320,362-364`
- reader の構成・lazy/elastic 条件・起動: `serve/server.py:2770-2790,2829-2857`
- timeout 待機・kill とエラー文言: `serve/server.py:2703-2742,2872-2892`
- 画像処理の有無・DeepSeek 経路: `serve/server.py:5221-5242`
- モデル再ロードでの再起動: `serve/server.py:4675-4682`
