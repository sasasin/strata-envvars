# `STRATA_INKLING_PROMPT_CKPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling サーバーの生成パスが engine に送る `ckpt=0` キーを、通常は同一リクエストの後続 pass に付けるところ、値が文字列 `0` のときは最初の pass にも付けます。サーバー内の `KEEP_CKPT_KEY` を設定し、Inkling 用の sampling-key 変換が engine の `GEN` / `BGEN` 行に `ckpt=0` を追加します。環境変数自体を読むのは `terminal/serve/server.py` の生成ループです。`ckpt_key=1` を engine 情報が通知し、Inkling engine として扱われている場合に限ってキーを送ります。`terminal/serve/server.py:1385-1387, 6108-6115, 4292-4299`

この環境変数による分岐は Strata の prompt や生成 token を直接書き換えず、engine へ渡す sampling/protocol key を変えます。server の通常の pass では、`pass_n` が真（2 回目以降）ならこの変数に関係なく同じ key を付けます。`terminal/serve/server.py:6096-6115`

## 値と判定

各 pass の準備時に `os.environ.get("STRATA_INKLING_PROMPT_CKPT") == "0"` を評価します。文字列全体の大小文字を区別する完全一致で、数値変換、trim、真偽値変換はありません。未設定や空文字は一致せず、`0` 以外の値も一致しません。`"00"`、`"0anything"`、`" 0"`、`"false"` も `"0"` とは異なる文字列です。`terminal/serve/server.py:6108`

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Inkling engine かつ engine 情報の `ckpt_key` を文字列化した値が `1` | 最初の pass には key を付けない。後続 pass は pass 番号により付く | 正確に `0`: 最初の pass にも key を付ける | 空文字、`1`、`00`、`0anything`、空白付きの `0` など: 最初の pass には付けない。後続 pass は pass 番号により付く |
| 上記以外 | key をこの環境変数によって追加しない | なし | すべて |

判定は各 pass のたびに行われ、環境変数用の cache はありません。環境変数の読み取りより前に、サーバー初期化時に `self.inkling` は engine の `inkling_engine` 属性から決まり、各 pass では engine の `info["ckpt_key"]` を `str(...)` に通した結果が `"1"` か確認します（数値の `1` も一致します）。`terminal/serve/server.py:4292-4299, 6108`

## 有効になる条件

- `self.inkling` が真であること。これは server が engine の `inkling_engine` 属性を `True` と認識した場合です。`terminal/serve/server.py:4292-4299`
- `engine.info` の `ckpt_key` が文字列化後に `1` となること。無い場合、`None` の場合、別の値の場合は key を追加しません。`terminal/serve/server.py:6108`
- これらの条件が満たされ、環境変数が正確に `0` なら最初の pass を含め key を追加します。後続 pass は `pass_n` が真になるため、変数の値にかかわらず key を追加します。`terminal/serve/server.py:6096-6113`
- CLI 引数、設定値、他の環境変数によるこの変数の上書き・優先順位処理は、この名前の読み取り箇所にはありません。Inkling の sampling-key 分岐は内部 `KEEP_CKPT_KEY` を処理して return するため、その後にある汎用 `strata_checkpoint=False` の処理はこの経路では評価されません。`terminal/serve/server.py:1373-1387, 1410-1413, 6108`

## 実行時の詳細

リクエスト生成の `while` ループでは、最初の pass の `pass_n` は `0` です。条件を満たす場合、既存の `pass_sampling` のコピーへ内部キー `KEEP_CKPT_KEY` を `True` として設定してから `self.engine.generate(...)` を呼びます。次の pass では `pass_n` が増えているため、同じ内部キーが環境変数なしでも設定されます。`terminal/serve/server.py:6096-6115`

Inkling 用 `sampling_keys` は内部キーが `True` のとき `ckpt=0` を追加して返します。単独の生成ではそのキーを含めて `GEN` または `GENI` の行を構築し engine の stdin に書き込みます。バッチ生成経路も同じ `sampling_keys` を使って制御行のキーを作ります。`terminal/serve/server.py:1336-1387, 2032-2039, 2625-2656`

この値はサーバー起動時に一度保存されるのではなく、各 pass の分岐で `os.environ` から直接参照されます。プロセス内で環境辞書が更新されれば後の評価に反映されます。親 shell 側の変更がすでに起動済みプロセスの環境辞書へ自動反映される処理はありません。`terminal/serve/server.py:6108`

## ログと測定値

この変数の値や判定結果を専用に記録するログ、警告、エラー文言は読み取り箇所にありません。観測可能な Strata 側の差は engine に渡す制御行の `ckpt=0` の有無です。制御行の書き込み時に pipe が失われるなどのエラーは通常の engine 死亡経路へ進みますが、この変数専用の失敗処理はありません。`terminal/serve/server.py:1385-1387, 2653-2660, 6108-6112`

測定値は該当資料にありません。

## 根拠

- `terminal/serve/server.py:1336-1387` — Inkling 用 sampling-key 変換と `ckpt=0` の付加。
- `terminal/serve/server.py:2032-2039, 2625-2656` — sampling key の生成と engine 制御行の送信。
- `terminal/serve/server.py:4292-4299` — Inkling engine の判定。
- `terminal/serve/server.py:6096-6115` — pass 番号、環境変数の評価、engine 生成呼び出し。
- `terminal/serve/server.py:2653-2660` — 制御行書き込み時の engine 死亡処理。
