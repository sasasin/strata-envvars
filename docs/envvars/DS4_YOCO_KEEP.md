# `DS4_YOCO_KEEP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek-V4.1 の `strata-dsv41` エンジンで、長い prompt の chunked prefill における layer skip の再計算保持行数 `keep` を指定します。正の値を設定すると、skip 対象 layer 群を入力末尾の少なくともその行数ぶん再計算します。ただし最低でもモデルの window (`g.win`) 行を保持します。

この変数は skip の有効化を単独では行いません。skip mode が無効、layer 構成が対象条件外、全行 logits の経路、または入力が十分長くない場合には cutoff が作られず、通常の全 layer 処理になります。

## 値と判定

値は `std::atoi` で整数化され、文字列全体の検証はありません。

| 環境値 | `keep_env` | `keep` への影響 |
|---|---:|---|
| 未設定 | 0 | `DS4_YOCO` / `STRATA_DS4_PROMPT_SKIP` の mode に応じた既定計算を使う |
| 空文字、整数 prefix のない文字列（例: `abc`） | 0 | 同上 |
| 0 または負の整数 | 0 以下 | 同上。skip を無効にはしない |
| 正の整数 `N` | `N` | mode にかかわらず `keep = max(N, g.win)` |

`atoi` のため、先頭の空白や符号を含む整数 prefix は変換され、数字の後ろは無視されます（例: `128tail` は 128）。大文字小文字の判定はありません。値の設定有無を確認した後、変換時にもう一度 `getenv` しています。

`keep_env` は `forward_chunks()` 内の `static const int` です。同関数が最初にこの行へ到達した時点の値がプロセス内で保持され、その後の環境変更では再評価されません。`forward_chunks()` が一度も呼ばれなければ読み取られません。

## 有効になる条件

`keep` が skip cutoff に反映されるには、`forward_chunks()` で `yoco_layer()` が layer を返す必要があります。主な条件は次のとおりです。

- `DS4_YOCO` または、前者が未設定の場合の `STRATA_DS4_PROMPT_SKIP` が `atoi` で 0 にならない。両方未設定なら mode の既定値は 1。
- chunking が有効で、2 layer 以上あり、compression ratio の配列が layer 数を満たす。
- 最初の compression ratio 1 の layer が layer 0 より後にあり、その layer に KV source がある。
- 全 layer が単一 member で同じ GPU にあり、対象 layer より後は ratio 1 かつ KV source を持たない。
- `forward_chunks()` が全行 logits のため skip を止める経路ではない（`logits_rows <= kWin`）。

さらに、cutoff の先頭位置 `a = n - keep` が 1024 行以上の skip 部分を残す場合（`n - keep >= kYocoMin`）に限り、実際に `run.yoco` が設定されます。条件に達しない場合は `a = 0` となり、`DS4_YOCO_KEEP` の値にかかわらず layer skip は行われません。`Model::feed()` は chunk が有効で入力が `chunk_min` 以上のときに chunked 実行を検討し、選択されなければ window 経路を使います。

## 実行時の詳細

正の `DS4_YOCO_KEEP=N` は、既定 mode（1）と DeepSeek serving 方式（mode 2）のどちらでも、保持数を `max(N, g.win)` にします。未設定または 0 以下なら、mode 2 は `g.win`、それ以外の非ゼロ mode は `(g.nl - yl) * (g.win - 1) + g.win` を使います。したがって正値は既定の再計算範囲を小さくも大きくもでき、入力長に対する上限 clamp はありません。

skip が成立すると、`a` より前の chunk は対象 layer で KV-only 処理を行い、その後の layer を省略します。cut を含む chunk は `a` より前の行を KV-only で処理し、`a` 以降を通常処理します。後続 chunk は全 layer を処理します。保持数が大きく `n - keep < 1024` になると、この skip 処理は適用されません。

環境変数の読み取りや値の採用に伴うログ、警告、エラー出力は確認できませんでした。ソースコメントは DeepSeek serving の短い再計算方式について「answers shift a little」としていますが、`DS4_YOCO_KEEP` の任意値による出力差や性能を測定した資料は確認できませんでした。

## 根拠

- `CMakeLists.txt:797-811` — `STRATA_BUILD_DSV41` は既定 OFF で、条件を満たすと独立実行ファイル `strata-dsv41` に `src/dsv41/ds4_model.cu` を含める。
- `src/dsv41/ds4_model.cu:8165-8171` — skip mode の既定値、`DS4_YOCO` 優先、`STRATA_DS4_PROMPT_SKIP` fallback、`atoi` と static cache。
- `src/dsv41/ds4_model.cu:8173-8184` — skip 対象 layer の構造条件。
- `src/dsv41/ds4_model.cu:8202-8217` — 全行 logits 時の除外、`DS4_YOCO_KEEP` の読み取り、keep の優先規則、1024 行閾値。
- `src/dsv41/ds4_model.cu:7459-7465,7467-7488,7520-7525` — cutoff 前・cut chunk・後続 chunk の layer 処理。
- `src/dsv41/ds4_model.cu:9356-9367,9369-9383` — `feed()` / `feed_mark()` から chunked prefill が選ばれる条件。
- `docs/DETAILS.md` と `docs/DEEPSEEK41.md` — 本変数の個別仕様や測定値は確認できず、挙動の説明は現行ソースに基づく。
