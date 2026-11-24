# `STRATA_INKLING_EFFORT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata の Inkling-2-Mini サーバーで、リクエストが思考レベルを指定しなかったときに chat template へ渡す既定の `reasoning_effort` を設定する。値は `inkling_dialect.py` の import 時に読み取られ、`normalize_effort(None)` が有効な名前なら採用し、そうでなければ `low` に戻す。`template_kwargs()` はそのレベル名を `reasoning_effort` として、レベルが `none` なら `enable_thinking=False`、それ以外なら `True` として template に渡す（`terminal/serve/inkling_dialect.py:407-419,439-456`）。

実際のサービス経路では、engine が Inkling と識別された場合だけ `Service.render_prompt()` がこの変換を使う。サーバー起動時に `svc.inkling` から family を設定し、Inkling のとき `inkling2` とする（`terminal/serve/server.py:4292-4299,4314-4318,9492-9506`）。この変数は C++ engine や GPU backend の設定ではなく、Python サーバーが template に渡す既定値である。

## 値と判定

環境変数は `os.environ.get("STRATA_INKLING_EFFORT", "low").strip().lower()` で読み取る。外側の空白を除いて小文字化し、空文字なら `low`。その後、有効な既定値かどうかを `EFFORT_LEVEL` のキーとの完全一致で判定する。有効値は次の7個だけである（`terminal/serve/inkling_dialect.py:407-419`）。

| 条件 | unset | 有効になる値（例） | 無効な値・扱い |
| --- | --- | --- | --- |
| Inkling の既定レベル | `low` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`。例: ` HIGH ` は `high` | 空文字・空白だけは `low`。`off`, `min`, `med`, `auto`, `default`, `maximum`, `0`, `0.5`, `low!` などキーに完全一致しない値はすべて `low` に fallback。例外・警告は出さない |

環境変数の値自体は数値として parse されず、`0` や `0.5` はレベル値にならない。リクエスト側の値は別の処理で、文字列を trim/lowercase して alias を判定し、数値なら `0` 以下を `none`、`0.99` 超を `max`、その間を数値のまま扱う（`terminal/serve/inkling_dialect.py:416-436`）。これは環境変数の受け付け規則ではない。

## 有効になる条件

- Inkling-2-Mini を扱う Strata の Python サーバー経路で、engine が Inkling と識別されていること。起動処理で `svc.inkling` に基づいて family が設定され、Inkling の `render_prompt()` が dialect の `template_kwargs()` を呼ぶ（`terminal/serve/server.py:4292-4299,4314-4318,9500-9506,5425-5436`）。
- リクエストに有効な思考指定がなく、別の処理が `enable_thinking=False` を設定していないこと。`effort_of()` は明示的な `enable_thinking is False` を優先して `none` とする（`terminal/serve/inkling_dialect.py:439-456`）。
- OpenAI Chat Completions では `reasoning_effort`、`reasoning.effort`、または `chat_template_kwargs` の指定が既定値に優先する（`terminal/serve/frontend.py:699-716`）。Responses API では `reasoning.effort` がある場合に用いられ、無ければ空の kwargs が template に渡って既定値が使われる（`terminal/serve/responses.py:646-653`; 呼び出し: `terminal/serve/server.py:8439-8445`）。
- Anthropic Messages では `thinking.type="disabled"` は既定値より優先する。`output_config.effort` または `thinking.budget_tokens` によるレベル指定があればそれを使う。レベルも budget も指定されない場合、config の `anthropic_thinking="on_request"` は `enable_thinking=False` を設定して既定値を抑止し、通常の `model` 設定では template 既定値を使う（`terminal/serve/frontend.py:825-828,904-927`; 設定: `terminal/serve/server.py:9637-9640`）。
- **config/shared setting の相互作用:** 現行コードの `Service.effort_default()` は Inkling の場合に `None` を返す。そのため `config_effort` や Chat settings shared の `reasoning_effort` を `with_shared()` 経由で補う処理は Inkling では行われず、未指定ならこの環境変数（無効値時は `low`）に到達する（`terminal/serve/server.py:5148-5174`）。`STRATA_INKLING_EFFORT` を CLI 引数で上書きする読み取り箇所は見つからなかった。

## 実行時の詳細

`terminal/serve/server.py` は `inkling_dialect` を import し（`336` 行）、その時点で `DEFAULT_EFFORT` が一度だけ計算される。以降の request では `normalize_effort()` がこの定数を参照するため、サーバープロセス起動後に環境を変更しても反映されない。リクエストごとの再読み取りや、この値を子プロセスへ転送する処理はない（`terminal/serve/inkling_dialect.py:408,416-419`）。

未指定時の既定値は通常 `low`（template に `reasoning_effort="low"`, `enable_thinking=True`）。`none` を環境変数に設定した場合は `reasoning_effort="none"`, `enable_thinking=False` となる。`medium` 等の他の許可値は対応する名前と `enable_thinking=True` を渡す。Inkling で prompt を描画する際は `Service.render_prompt()` が kwargs を作り、template の描画と Inkling の prompt 終端処理へ渡す（`terminal/serve/server.py:5425-5436`）。この環境変数が生成結果や思考の長さを保証する処理は Strata 側にはない。

config との資料上の差がある。`docs/MODELS.md:311` は config の `reasoning_effort` またはこの環境変数で既定レベルを変更できると説明する。しかし現行コードでは Inkling 時の `effort_default()` が `None` を返し、`with_shared()` は config/shared の値を request に追加しない（`terminal/serve/server.py:5148-5174`）。そのため、この commit のコードでは当該 config/shared 値は Inkling の未指定 request に適用されず、環境変数または `low` fallback が使われる。

## ログと測定値

この環境変数の読み取り、fallback、有効化を知らせる専用ログはない。未知の環境変数値も起動時に拒否せず、黙って `low` に fallback する。無効な**リクエスト値**は別で、`normalize_effort()` が `unknown reasoning effort ...` の `ValueError` を発生させ、Chat API の通常リクエストでは HTTP 400 の `invalid_request_error` になる（`terminal/serve/inkling_dialect.py:430-436`; `terminal/serve/server.py:8122-8123`）。

測定値は該当なし。この変数の性能測定や生成内容の比較は行っていない。

## 根拠

- 環境変数の読み取り、既定値の許可キー検査、正規化: `terminal/serve/inkling_dialect.py:407-436`
- kwargs への反映、`enable_thinking` の決定: `terminal/serve/inkling_dialect.py:439-456`
- Inkling server/runtime 判定と family 設定: `terminal/serve/server.py:4292-4299,4314-4318,9492-9506`
- Inkling prompt 描画: `terminal/serve/server.py:5425-5436`
- API リクエスト値の優先・Anthropic の未指定時分岐: `terminal/serve/frontend.py:699-716,825-828,904-927`; `terminal/serve/responses.py:646-653`
- config/shared effort が Inkling で fallback されないこと: `terminal/serve/server.py:5148-5174`
- Strata 資料との記載差: `docs/MODELS.md:311`
