# `strata` / `strata-q36 --dump-full-logits`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--dump-full-logits` |
| 別名 | なし |
| 値 | 出力ファイル名。引数は文字列として受け取る。 |

## 役割

`--tokens` による単発生成で、生成各ステップの全語彙 logits を float32 のバイナリファイルへ順に保存します。推論結果の token ID だけではなく、各 token 候補の logits を後から比較・解析したい場合に使います。Qwen3.6 用 parser がこのオプションを登録し、通常の `strata` はモデル GGUF の architecture が `qwen35moe` の場合に同じ parser へ処理を渡します（`engine/src/qwen35/q36_engine.cu:5368`, `engine/src/program/generate.cpp:3805-3817`）。

## 使い方

```sh
strata --model model.gguf --tokens 1,2,3 --n 4 --dump-full-logits logits.f32
```

`strata-q36` を直接使う場合も、同じ引数を指定します。`--tokens` は prompt の token ID 列、`--n` は生成数です。実運用ではモデルと ID を対象データに合わせてください。

## 値と既定値

- 値を1つ必須で受け取ります。値を省略すると `strata-q36: --dump-full-logits needs a value` を標準エラーへ出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。
- option を指定しない場合、ファイル出力はありません。指定値は `std::string` に保持され、空文字列なら出力ファイルを開かず、非空文字列ならそのパスを `fopen(..., "wb")` に渡します（`engine/src/qwen35/q36_engine.cu:5340`, `5368`, `5598`）。数値範囲などの値検証はありません。
- 同じ option を複数回指定すると parser の代入により最後の値が使われます（`engine/src/qwen35/q36_engine.cu:5368`）。

## 実行時の動作

出力ファイルを開くのは、`--serve` と benchmark の分岐を抜け、`--tokens` の prompt が空でないことを確認した後です。ファイルは `wb` モードで開かれるため、同名ファイルがあれば内容を切り詰めて作り直します。`--n` が省略された場合は生成数の初期値 64 が使われます。`--force` に有効な ID 列がある場合は、生成数がその列の長さ + 1 に設定されます（`engine/src/qwen35/q36_engine.cu:5342`, `5593-5598`）。

各生成ステップで `E.host_logits` が現在ステップの語彙 logits を GPU から host にコピーし、stream を同期します。その後 `fwrite` で `m->g.n_vocab` 個の float（各4 byte）をそのまま書き込みます。ヘッダーや token ID は含まれず、行境界もない連続した float32 配列です。1ステップの出力サイズは `4 * n_vocab` byte です（`engine/src/qwen35/q36_engine.cu:4061-4065`, `5640-5645`）。

`--force` を併用すると、そのステップの logits を保存した後、次の入力 token として forced 列の対応 ID を `E.process` に渡します。forced 列を使い切った後は直前の greedy token を渡します（`engine/src/qwen35/q36_engine.cu:5646-5648`）。

## 適用条件と副作用

- 実際のダンプ処理は `--tokens` の単発生成経路だけです。`--serve` は serve loop を呼んで先に return し、benchmark も反復計測後に先に return するため、これらのモードではこの指定はファイルを作成せず出力にも使われません（`engine/src/qwen35/q36_engine.cu:5562-5598`）。
- Qwen3.6 の MTP が有効で、`--force` と正常に開いたダンプファイルのどちらもない場合は speculative decode の分岐になります。ファイル出力が有効な場合はこの分岐を通らず、通常の1 token ごとの greedy 生成ループで logits を保存します（`engine/src/qwen35/q36_engine.cu:5614-5648`）。
- ファイルを開けなかった場合の戻り値は検査されていません。`ff` が null となるため、エラーメッセージなしでダンプが無効になり、MTP 条件にも「ファイルなし」として扱われます。また、`fwrite` の書き込み件数も確認されず、書き込み失敗を報告する処理はありません（`engine/src/qwen35/q36_engine.cu:5598`, `5614`, `5642-5645`）。
- 空でない出力パスはモデル準備と prompt の検査後に開きますが、画像入力の `--emb` が `--vision` なし、または画像組み立て失敗となると、ファイルを開いた後で終了コード 2 を返します。その際に `ff` を閉じる処理は確認できません（`engine/src/qwen35/q36_engine.cu:5595-5605`, `5650`）。

## 出力とエラー

成功時は通常の `gen: ...` token ID 列を標準出力へ出し、生成時間などを標準エラーへ出します。logits 本体は指定ファイルへバイナリ出力されます（`engine/src/qwen35/q36_engine.cu:5650-5656`）。ファイル open / write 失敗を検出して通知する処理はありません（`engine/src/qwen35/q36_engine.cu:5598`, `5642-5645`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5368` — Qwen3.6 parser の状態、値取得方法、オプション登録。
- `engine/src/qwen35/q36_engine.cu:5350-5352`, `5412-5417` — 値不足と未知引数のエラー・終了経路。
- `engine/src/program/generate.cpp:3805-3817` — `qwen35moe` architecture を検出し、Qwen3.6 parser へ振り分ける箇所。
- `engine/src/qwen35/q36_engine.cu:5593-5605`, `5614-5656` — prompt 条件、ファイル open、MTP との相互作用、logits の書き込みと通常出力。
- `engine/src/qwen35/q36_engine.cu:4061-4065` — logits を host に取得する処理。
