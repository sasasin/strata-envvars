# `--tokens`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 parser（または専用実行ファイル `strata-q36`） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | 10 進整数の token ID 列。カンマまたは空白で区切る |

## 役割

Qwen3.6 エンジンに token ID の prompt を直接渡し、その prompt を処理して greedy decode した token ID 列を得る単発実行用オプションです。テキスト tokenizer で prompt を変換する経路ではありません。画像を含む prompt は、`<|image_pad|>` の ID 列に `--emb` と `--vision` を組み合わせて渡します。

## 使い方

```sh
# Qwen3.6 モデルの token ID 1, 42, 314 を prompt として処理し、既定数を生成
strata --model /path/to/qwen36.gguf --tokens 1,42,314

# 専用エンジンを直接呼び出し、生成数を 8 にする
strata-q36 --model /path/to/qwen36.gguf --tokens "1 42 314" --n 8
```

## 値と既定値

- `--tokens` は次の引数を文字列として受け取り、`parse_ids()` が `strtol(..., 10)` で先頭から整数を読みます。カンマと空白を読み飛ばし、整数に変換できない位置に達するとそこで解析を止めます。したがって値全体が厳密に検証されるわけではありません（`engine/src/qwen35/q36_engine.cu:4604-4615`）。
- 省略時は空文字列です。`--serve` またはベンチマーク経路でない通常実行では、解析後に prompt が空なら `strata-q36: --tokens, --serve or --bench-pp is required` を標準エラーに出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5340-5343, 5595-5596`）。
- 同じオプションを複数回指定すると parser の文字列代入により最後の値が残ります（`engine/src/qwen35/q36_engine.cu:5364`）。値を省略すると `--tokens needs a value` を標準エラーに出して終了コード 2 です（同 `5350-5352`）。
- token ID の範囲はこの単発経路で事前検証されません。サーバーの `GEN` request には別途語彙範囲検証がありますが（`engine/src/qwen35/q36_engine.cu:5067-5085`）、その検証を `--tokens` に適用するコードは確認できません。

## 実行時の動作

通常経路では解析した ID 列を `E.process()` に渡し、prompt 全体の状態と最後の token の logits を作ってから `E.greedy()` で次 token を生成します（`engine/src/qwen35/q36_engine.cu:3685-3727, 5595-5612, 5639-5649`）。生成列は標準出力へ `gen: <ID> ...` の形式で出力し、prompt/生成時間などの集計は標準エラーへ出します（同 `5650-5657`）。`--tokens` 単独では出力テキストに復号しません。

既定の生成数は 64 で、`--n` がその数を設定します。`--max-new` も同じ変数を設定するため、両方を指定したときは引数列で後に現れた方が有効です。強制 token 列の `--force` が空でなければ、生成数はその列の長さ + 1 に置き換わり、通常の逐次 decode 経路で指定した token を次の入力として使います（`engine/src/qwen35/q36_engine.cu:5340-5343, 5356, 5365-5366, 5595-5597, 5639-5649`）。

`--mtp N` が有効でモデルに MTP block がある場合、`--force` が空かつ `--dump-full-logits` の出力ファイルを開けていない単発経路では speculative decode 分岐を通ります。ここでも prompt は `--tokens` の ID 列で、生成は greedy です（`engine/src/qwen35/q36_engine.cu:5614-5637`）。`--greedy` はこの parser では何もしません。`--tokens` 経路自体が greedy と明記されています（同 `5360`）。

`--serve` が指定されている場合は `serve(E)` に入り、通常の `--tokens` 処理より先に戻ります。正の `--bench-pp` または `--bench-tg` があればベンチマーク経路も token 列の処理より先に実行されます（`engine/src/qwen35/q36_engine.cu:5561-5564, 5595-5596`）。

## 適用条件と副作用

- Qwen3.6 専用 parser のオプションです。`docs/cli/README.md` は `strata` / `strata-q36` の Qwen3.6 専用 scope に索引し、parser は `engine/src/qwen35/q36_engine.cu` の `strata::qwen35::run()` にあります（`docs/cli/README.md:1242-1275`; ソース `engine/src/qwen35/q36_engine.cu:5339-5348`）。
- `--emb FILE` を使う場合は `--vision` も必要です。ファイルが開けない、形式・幅が不正、画像数と `<|image_pad|>` の数が合わない、prompt が画像 marker で終わる場合などはエラー文字列を標準エラーへ出して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:4638-4702, 5601-5608`）。
- `--dump-full-logits FILE` を併用し、出力ファイルを開けた場合は `wb` で開くため同名ファイルが切り詰められます。各生成 step で logits を float のバイナリとして書き込み、MTP speculative 分岐は使いません（`engine/src/qwen35/q36_engine.cu:5598-5599, 5614, 5640-5645, 5650`）。
- `--model` は `--tokens` とは別に必須です。モデル読込後に `--tokens` が空と判定されたときの終了コードは 2 です（`engine/src/qwen35/q36_engine.cu:5420, 5458-5464, 5595-5596`）。

## 出力とエラー

- `--tokens` の値がない場合、または単発実行で prompt が空の場合は標準エラーにエラーを出し終了コード 2 です（`engine/src/qwen35/q36_engine.cu:5350-5352, 5595-5596`）。
- `--tokens` が空で、`--serve` もベンチマークも指定されていない場合も同じ空 prompt エラーになります（同 `5561-5564, 5595-5596`）。
- 成功時は生成 token ID を標準出力へ、処理時間と生成速度を標準エラーへ出します（`engine/src/qwen35/q36_engine.cu:5650-5657`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5368` — Qwen3.6 parser と `--tokens`、`--n`、`--force`、`--emb` の受理。
- `engine/src/qwen35/q36_engine.cu:4604-4615` — token ID 列の変換規則。
- `engine/src/qwen35/q36_engine.cu:3685-3748, 5595-5657` — prompt 処理、greedy decode、MTP 分岐、出力。
- `engine/src/qwen35/q36_engine.cu:5067-5085` — サーバー request 側にある token ID の範囲検証。
- `engine/src/qwen35/q36_engine.cu:4638-4702, 5601-5608` — 画像埋め込みファイルの読み込みと条件・失敗経路。
- `docs/cli/README.md:1242-1275` — `strata-engine` の Qwen3.6 command path と索引項目。

調査対象は指定 revision の checkout 内ソースに限定しました。既存バイナリの `--help` は実行していません。
