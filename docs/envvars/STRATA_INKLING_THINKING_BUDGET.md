# `STRATA_INKLING_THINKING_BUDGET`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`terminal/serve/server.py` の API サーバーが、Inkling-2-Mini の推論予算の既定値を全 reasoning effort level 共通の token 数に置き換える。対象は各リクエストが予算を指定せず、設定ファイルにも `reasoning_budget_tokens` がない場合の既定予算である。値 `0` は level 別の既定予算を無効にするが、既定で有効な `answer_room` が別の上限を設定する場合がある。モデルに渡す effort level や生成上限そのものを設定する変数ではない。予算到達時の処理はサーバー側で思考を閉じて回答へ進める。`Service.__init__` の値保持、既定値の選択、生成処理への適用は `terminal/serve/server.py:4174-4188,4613-4625,5886-5910,6073-6076`。

これは `terminal/serve/server.py` のサービス設定であり、単独の engine CLI 引数ではない。値は `Service` 作成時に読み、インスタンスに保持する。したがって同じサーバープロセスの実行中に環境変数を変更しても反映されない。Inkling-2-Mini engine のときだけ既定予算の選択に使われ、通常の別モデルや `--engine mock` では適用されない（`terminal/serve/server.py:4292-4300,5886-5890,9492-9505`）。

## 値と判定

起動時に `os.environ.get(..., "").strip()` で取得し、空でなければ Python の `int()` で文字列全体を整数変換してから `max(0, ...)` を適用する。変換に失敗した `ValueError` は握りつぶされ、環境変数由来の既定値を `None`（effort level ごとの既定へ）にする。未設定、空文字、空白だけも同じく `None`。ログや起動失敗にはならない（`terminal/serve/server.py:4184-4188`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全 server 起動時 | `None`。Inkling で有効な場合は effort level ごとの値を使う | 整数として読める文字列。例: `0`, `1`, `+12`, `01`, `1_000`。負数も変換後 `0` になる | 空白除去後に整数変換できない値。例: `true`, `1.0`, `0anything`。例外は捕捉され level ごとの既定に戻る |

大文字小文字は整数変換の対象外であり、`true` / `false` を特別扱いしない。前後の空白は `strip()` で除去する。整数全体を変換するため、数値の後ろに文字があれば無効。数値の上限チェックはここでは行わない。生成時に予算が `max_tokens` の範囲を超える場合は回答用の余白を残す値まで調整される（`terminal/serve/server.py:4185-4188,5902-5910`）。

## 有効になる条件

- Inkling-2-Mini 用 server service であること。予算既定値の採用判定は `self.inkling` が真の場合に限られる。server の通常の Strata engine 経路で Inkling family を検出したときにこの状態になる（`terminal/serve/server.py:4292-4300,9500-9505,5886-5890`）。
- リクエストに予算が指定されておらず、設定ファイルの `reasoning_budget_tokens` も未指定であること。リクエストの `reasoning_budget_tokens` が最優先で、次に `thinking_token_budget`、`thinking_budget`、`thinking_budget_tokens` の順に採用される。`null` は次の名前へ進むが、`0` は明示値として環境変数への fallback を止める。設定ファイルの `reasoning_budget_tokens` が存在する場合（`0` を含む）も family default へ進まない。設定ファイルの `inkling_thinking_budget` はこの環境変数の値を上書きするが、リクエスト自身の予算は引き続き優先する（`terminal/serve/server.py:4633-4646,9519-9523,9657-9665`）。
- 別環境変数 `STRATA_INKLING_EFFORT` や設定・リクエストの reasoning effort は level を決めるが、この変数に有効な整数が設定されれば予算は全 level 共通になる。環境変数が未設定または不正なら level ごとの既定は `none` / `minimal`: 1,024、`low`: 2,048、`medium`: 4,096、`high`: 8,192、`xhigh` / `max`: 16,384 tokens（`terminal/serve/server.py:4613-4625`、`terminal/serve/server_parts/base.py:104-108`）。
- リクエスト予算の数値が整数でない場合は予算計算時にエラーとなる。予算に関係する API 経路では送信前に検証され、不正な値は HTTP 400 になる（Responses API は `ResponsesError` として変換）。これは環境変数自体の不正値処理とは別である（`terminal/serve/server.py:4642-4646,8233-8235,8461-8463,8527-8529`）。

## 実行時の詳細

`Service.__init__` が server 起動時に環境変数を一度読み、`self.inkling_thinking_budget` に保存する。リクエスト処理ごとに環境を再読せず、値をキャッシュする。設定ファイルの `inkling_thinking_budget` があればサービス作成後に検証し、同じ属性を上書きする。これは bool でない非負整数のみ受理し、それ以外なら `[strata] config "inkling_thinking_budget" must be a whole number of tokens (0: none), not ...` で起動を終了する（`terminal/serve/server.py:4184-4188,9519-9523`）。

各 API リクエストでは、まずリクエスト内の budget 名を所定順に確認し、次に config の `reasoning_budget_tokens` を確認する。どちらも指定されておらず Inkling engine なら `inkling_default_budget()` が環境変数の共通値を返し、共通値が `None` の場合はそのリクエストの effort に対応する表の値を返す。これにより環境変数は既定値だけを変え、明示した request/config budget を上書きしない（`terminal/serve/server.py:4613-4625,4627-4646`）。

実際の生成では `reasoning_budget()` の結果を `thinking_budget` として生成状態に渡す。予算が `max_tokens` に対して大きい場合、Inkling では回答用の余白（少なくとも 512 tokens。ただし最大でも出力上限の半分）を残す値へ切り詰める。予算がなく `answer_room` が有効なら、Inkling は `max_tokens` が 16 以上のリクエストに対して別途、回答用余白を残す予算を設定する。これは `STRATA_INKLING_THINKING_BUDGET=0` でも起こり得る。設定ファイルの `answer_room: false` で無効化できる。予算到達時に思考を閉じる経路では、`[strata] thinking budget reached (<実消費> tokens): wrapping up the thinking` を出し、短い wrap-up と `</think>` を生成して回答を続ける。予算は全思考 token を厳密に出力から差し引く CLI 上限ではなく、サーバーが思考を閉じるための上限として使われる（`terminal/serve/server.py:5886-5910,6073-6076,6375-6402`）。

## 根拠

- `terminal/serve/server.py:4174-4188` — 起動時の環境読み取り、整数変換、無効値 fallback。
- `terminal/serve/server.py:4292-4300,9492-9505` — Inkling engine 判定と server service の作成経路。
- `terminal/serve/server.py:4613-4625,4627-4646` — level 既定値、request/config/environment の優先順位と値検証。
- `terminal/serve/server.py:9519-9523,9657-9665` — `inkling_thinking_budget` と `reasoning_budget_tokens` config の検証・設定。
- `terminal/serve/server.py:5886-5910,6073-6076,6375-6402` — 予算の適用、回答用余白、思考終了時のログと処理。
- `terminal/serve/server_parts/base.py:104-108` — level ごとの既定予算。
