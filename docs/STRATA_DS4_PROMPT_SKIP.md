# `STRATA_DS4_PROMPT_SKIP`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek-V4.1 用の `strata-dsv41` エンジンで、長い prompt の prefill 時に一部の後段層の expert 計算を省略する制御です。既定でこの skip を試みます。実際に省略できるのは、chunked prompt 経路でモデルの層構成などが条件を満たし、skip 対象が少なくとも 1024 行になる場合です。通常の短い feed、window 経路、または全行の logits を要求する経路では適用されません。

このコードは CMake の `STRATA_BUILD_DSV41` が ON かつ `STRATA_HIP_GFX906` が OFF のときに作られる独立実行ファイル `strata-dsv41` に含まれます。同オプションはビルド時設定で、環境変数ではありません。

## 値と判定

値は文字列全体ではなく `std::atoi` で整数化されます。`DS4_YOCO` が存在すれば、空文字を含め、その値を先に使います。`DS4_YOCO` が未設定の場合に限り `STRATA_DS4_PROMPT_SKIP` を読みます。両方が未設定ならモードは `1` です。

| 選択された環境値 | `atoi` の結果 | モードの扱い |
|---|---:|---|
| 両変数とも未設定 | 1（既定値） | skip を試みる |
| `0`、空文字、整数として読めない文字列（例: `abc`） | 0 | skip しない |
| `2` で始まる整数表記（例: `2`, `2tail`） | 2 | DeepSeek serving 方式の短い再計算範囲を使う |
| その他の非ゼロ整数（例: `1`, `-1`） | 非ゼロ | 既定方式の skip を試みる |

`atoi` のため、先頭の空白や符号を含む整数 prefix は変換され、数字の後ろの文字列は判定されません。たとえば `2tail` は 2、`1tail` は 1、`true` は 0 です。大文字小文字の比較はありません。選択した値は関数内の `static const int` に保存され、最初の評価後にプロセス環境を書き換えても再評価されません。

## 有効になる条件

モードが 0 でない場合も、`yoco_layer()` が以下を満たす layer を見つける必要があります。

- prompt chunking が有効（`chunk > 0`）で、モデルに少なくとも 2 layer があり、全 layer の compression ratio が参照可能である。
- 最初の compression ratio 1 の layer が layer 0 より後にあり、その layer が KV source を持つ。
- すべての layer が単一 member で、layer 0 と同じ GPU に配置される。
- cut layer より後のすべての layer も compression ratio 1 で、KV source を持たない。

さらに `Model::feed()` は `n >= chunk_min` かつ `chunk > 0` のときだけ長い入力の経路を選びます。その経路でも、全行の logits を要求せず、適応型の `pick_path(n)` が chunked 経路を選ぶ必要があります（全行 logits の場合は chunked 実行を使いますが、skip 自体は無効です）。`forward_chunks()` は `logits_rows > kWin` の場合に layer skip を明示的に止めます。これらの条件を満たした後も、入力長 `n` から再計算保持行数 `keep` を引いた skip 部分が `kYocoMin`（1024 行）未満なら skip は適用されません。

## 実行時の詳細

skip 対象 layer は最初の compression ratio 1 の layer からです。通常モードでは、その layer から後段が必要とする過去の window を満たす行数として `keep = (nl - yl) * (win - 1) + win` を再計算し、それより前の chunk では対象 layer の KV/index key のみを作り、expert 計算と後続 layer の処理を省きます。cut を含む chunk は cut 行から後段 layer の処理を行い、後続 chunk は全 layer を通常どおり実行します。

値が `2` の場合は `keep = win` とし、より少ない末尾行だけを対象 layer 群に通します。ソースコメントはこの挙動を「DeepSeek's own serving's (the last 128 rows only)」と説明し、回答が少し変わるとしています。実装上の `win` 値を使うため、ここでは固定の行数として一般化しません。`DS4_YOCO_KEEP` が正の値ならモードにかかわらず `keep = max(DS4_YOCO_KEEP, win)` で上書きされます。

skip を利用できない場合の fallback は同じ `forward_chunks()` 内で全行を layer に通す通常処理です。環境変数を読み取る箇所に、この設定値についてのログ出力や警告はありません。既定 skip が token や回答を同一に保つという保証や性能測定値は、調査対象 commit の説明資料では確認できませんでした。

## 根拠

- `CMakeLists.txt:797-811` — `STRATA_BUILD_DSV41` による独立 `strata-dsv41` target、既定 OFF と `STRATA_HIP_GFX906` のビルド条件。
- `src/dsv41/ds4_model.cu:7862-7886` — モードの既定値、`DS4_YOCO` の優先、`atoi` と static cache、対象 layer の構造条件。
- `src/dsv41/ds4_model.cu:7891-7929` — `forward_chunks()` 内の全行 logits 除外、keep の計算、1024 行の閾値、cut の設定。
- `src/dsv41/ds4_model.cu:7176-7211,7242-7248,7290-7294` — chunk/layer ごとの通常処理、KV-only 処理、対象層 skip の実装。
- `src/dsv41/ds4_model.cu:9056-9067` — `Model::feed()` から chunked prompt 経路または window 経路を選ぶ条件。
- `src/dsv41/ds4_model.cu:1968-1977,810,820` — chunk 数・chunk 経路の設定と `kYocoMin = 1024`。

`docs/DETAILS.md` および他の設計資料には、この環境変数の個別説明は見つかりませんでした。ソース内コメントと分岐を現行実装の根拠としています。
