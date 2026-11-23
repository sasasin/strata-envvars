# `STRATA_STRICT_MODEL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata の Python サーバーが受け付けるモデル ID を厳密に照合するスイッチ。`Service.check_model()` が有効時には、ロード中のモデル名または設定された alias と一致しない `model` をすべて拒否する。無効時は未知の一般的な名前を許容する一方、Strata カタログ名に見える未知 ID は従来どおり拒否する。モデルのロードや推論計算自体は変更しない。読み取りと判定は `terminal/serve/server.py:4030-4038,4394-4424`。

この変数を読むのは `terminal/serve/server.py` のサーバー実装で、エンジンの C++/GPU 実装ではない。`--engine mock` と `--engine strata` のいずれも同じ `Service` を作成する（`terminal/serve/server.py:8870-8873,8974-8979`）。OS、backend、build macro、モデルのロード状態による環境変数自体の値判定の違いはない。

## 値と判定

`Service.__init__()` で `os.environ.get("STRATA_STRICT_MODEL", "")` を読み、前後空白を除去して小文字化した文字列が `1`, `true`, `yes`, `on` のどれかと完全一致する場合だけ真にする（`terminal/serve/server.py:4038`）。数値変換や部分一致は行わない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| サーバーの `Service` 初期化時 | 空文字相当となり false | `1`, `true`, `yes`, `on`。大文字小文字は区別せず、前後空白は無視 | 空文字、空白だけ、`0`, `false`, `no`, `off`, `2`, `0anything`, `true anything` |

この初期値は CLI の `--strict-model` または設定 JSON の `strict_model` が有効なら true に上書きされる。CLI は `store_true` で、設定は値が Python の真偽値 `True` と同一のときだけ有効。どちらも false を指定して環境変数による true を無効化する手段ではない（`terminal/serve/server.py:8699-8701,9045-9046`）。優先順位は「環境変数で初期化し、CLI または設定が true なら true」であり、false への上書きはない。

## 有効になる条件

- `STRATA_STRICT_MODEL` が有効値であるか、`--strict-model` が指定されるか、設定 JSON の `strict_model` が `true` であること。いずれかで strict 判定が有効になる（`terminal/serve/server.py:4038,9045-9046`）。
- モデル名照合の対象は `POST /v1/chat/completions`、`POST /v1/messages`、`POST /v1/responses`。この各経路で `check_model()` が呼ばれる（`terminal/serve/server.py:7463-7472`）。他の API 経路はこのチェックを通らない。
- リクエストに空でない文字列 `model` がある場合に照合する。`model` が欠落、文字列以外、または空白だけならこのチェックは通過する（`terminal/serve/server.py:4399-4402`）。
- ロード中のモデル名と alias は、完全一致または前後空白を除去した大文字小文字を無視する一致なら strict の状態にかかわらず受理される（`terminal/serve/server.py:4403-4409`）。alias は設定の `aliases` から `Service` に設定される（`terminal/serve/server.py:4366-4379,9040-9044`）。
- strict が無効のときだけ、ロード名のハイフン区切りの先行名や `hy4-flash` / `inkling-2-mini` のファミリー名も追加で許容する（`terminal/serve/server.py:4410-4414`）。strict が有効ならこの例外は適用されない。
- strict が無効でも `inkling-2-mini`, `hy4-flash`, `qwen3.8-flash-next`, `qwen3.6-`, `qwen3.5-` で始まる未知 ID は拒否対象。strict が有効なら、これらの prefix に当てはまらない未知名も拒否対象になる（`terminal/serve/server.py:4390-4392,4415-4417`）。

## 実行時の詳細

環境変数は `Service` の生成時に一度読み、`self.strict_model` に bool として保持する。リクエストごとに環境を再読せず、起動後にプロセス環境を変えても既存 `Service` には反映されない。CLI と設定 JSON の true は `Service` 作成後にフラグを true にする。サーバーはこのフラグをリクエストのモデル ID 検査に使い、エンジン起動引数やモデル選択には使わない（`terminal/serve/server.py:4038,4394-4424,8974-8979,9045-9046`）。

`child_env()` はサーバープロセスの環境全体をコピーしてエンジン子プロセス用環境を作り、設定の `env` を重ねるため、この名前も通常は子環境に継承され、設定の `env` に同名キーがあればその値で子環境側が上書きされる（`terminal/serve/server.py:3870-3874,3890-3891`）。ただし、この checkout で `STRATA_STRICT_MODEL` を読み取る Strata 所有コードはサーバーの上記箇所だけであり、子プロセス側での効果は確認できないため記述対象外。

拒否時は推論へ進まず、HTTP 404 と `code: "model_not_found"` を返す。標準の chat/messages 形式では `type: "invalid_request_error"` と `The model '<要求名>' is not loaded; currently serving '<ロード名>'`（alias があれば alias 一覧も続く）を含む。Responses 形式も同じ 404 / code で Responses 用エラー本文にする（`terminal/serve/server.py:4418-4424,7463-7472`）。環境変数の有効化・無効化を示す専用ログ出力はない。

## 根拠

- `terminal/serve/server.py:4030-4038` — `Service` の生成と環境変数の読み取り・値判定。
- `terminal/serve/server.py:4366-4379,4390-4424` — alias とモデル名照合、strict 有効時・無効時の分岐と拒否内容。
- `terminal/serve/server.py:7463-7472` — HTTP 推論経路での呼び出しと拒否応答。
- `terminal/serve/server.py:8699-8701,8870-8873,8974-8979,9040-9046` — CLI、mock/strata の Service 共用、設定・CLI による有効化。
- `terminal/serve/server.py:3870-3874,3890-3891` — 子エンジン環境の継承と設定 `env` の適用。
