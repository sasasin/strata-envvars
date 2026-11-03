# `STRATA_DS4_READ_PIECE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`maya-ds4` の複数会話サーバーで、プロンプトを分割して順番に読むときの 1 回分の大きさを指定します。単位は prompt chunk で、1 piece のトークン数は「モデルの prompt chunk × pipeline stage 数 × この変数の値」です。これはプロンプト読み込みのスケジューリングを変える設定で、生成 token 数や回答の設定値ではありません。

## 値と判定

値は共通 lambda `env_count` で `std::getenv` と `std::atoi` を通して読み、変換結果が正数なら採用し、それ以外なら呼び出し側の既定値にします。対象変数の既定値は `1` です。

| 環境値 | `atoi` の結果と採用値 |
|---|---|
| 未設定 | `0` として扱い、既定値 `1` |
| 空文字、数値に変換できない文字列、`0`、負数 | 正数でないため `1` |
| 正数（例: `2`） | その整数を採用 |
| 数字の後ろに文字が続く値（例: `2x`） | `atoi` が先頭の整数部分を返すため `2` |

全体一致の検査、空白除去、値の上限 clamp はありません。`atoi` が `int` の範囲外の値を変換した場合の動作は規定されません。採用値は `size_t` に変換され、chunk と stage 数に乗算されます。

## 有効になる条件

- `--serve` で serve loop に入り、モデルの `seq_count()` が 1 より大きい必要があります。通常は `--serve --parallel N`（`N` は 2〜8）で複数会話を構成します。VRAM が足りず会話数を 1 に縮退した場合は、複数会話ループ自体に入りません。非 serve の `--parallel` / `--multi-check` 経路ではこの変数を読みません。
- `m.prompt_chunk() > 0` が必要です。0 のとき `STRATA_DS4_READ_PIECES` 側の条件が成立せず、対象変数の値による分割読み込みは有効になりません。chunk 数は `--prefill-chunk`、モデルの既定選択、または `DS4_CHUNK` などで決まり、`--prefill-chunk 0` は chunked prompt path を無効にできます。
- 実際にプロンプト間で piece ごとの読み込みを行うには、別変数 `STRATA_DS4_READ_PIECES` の `env_count` 結果も正数である必要があります（既定は 0）。対象変数だけ設定しても分割スケジューリングは有効になりません。
- piece サイズは `m.pipeline_stages()` を掛けた値です。モデル実装は stage 数を少なくとも 1 として返します。画像付き要求は `STRATA_DS4_READ_PIECES` が有効でも、受け入れ時にプロンプト全体を読む経路を通ります。

## 実行時の詳細

環境変数は `--parallel` の会話数をモデルが確定した後、複数会話の serve loop に入る際に読みます。値を `static` に保存する処理はなく、ループ開始時に `env_count` から一度取得してローカル変数 `read_piece` に置きます。そのためループ開始後の環境変更はこの値に反映されません。Strata 内にこの変数を子プロセスへ転送する処理は見つかりませんでした。

`STRATA_DS4_READ_PIECES` が有効な場合、複数の prompt 読み込みを順番に進める際に、各回 `read_piece` tokens まで `prompt_piece` に渡します。モデルの `feed_unit()` を上限として読み、piece が終わると他の要求の token round と交互に進みます。読み込み中の prompt が 1 件だけで回答も動いていない場合は、要求の到着まで一度の読み込みを続けます。この変数は「1 stage あたり何 chunk まとめるか」を変更し、複数の読み込みの交替頻度と、短い prompt が長い prompt より先に並ぶ判定にも使われます。

この変数専用の警告・エラー出力はありません。未設定・無効値は既定値へ黙って戻ります。複数会話ループ開始時の stderr には会話数が出ます。実行中の `PP` 進捗行、`DONE` 行と stderr の prompt/生成時間は観測できますが、ログに採用した piece サイズ自体は表示されません。prompt feed の一般的なエラー処理はありますが、この設定値に固有の失敗経路は見つかりませんでした。

## 根拠

- `src/dsv41/ds4_main.cpp:1532-1541` — `env_count` の変換・fallback、読み取り条件、piece サイズの計算。
- `src/dsv41/ds4_main.cpp:1355-1356,1495-1503,2582-2588,2609-2613,2621-2629,2668-2669` — serve loop と複数会話ループの条件、`--parallel` の指定範囲、非 serve の multi-check 分岐。
- `src/dsv41/ds4_main.cpp:1851-1859,1886-1894` — 画像付き prompt の全体読み込み、piece 単位の turn と単独読み込み。
- `src/dsv41/ds4_main.cpp:1201-1203,1228-1235` — piece 上限と feed ごとの読み込み量。
- `src/dsv41/ds4_model.cu:7037-7048,7058` — VRAM 不足時に `--parallel` 会話数が縮退する経路と実際の sequence 数。
- `src/dsv41/ds4_model.cu:14938,14943-14944`、`src/dsv41/ds4_model.hpp:185-188` — `feed_unit`、prompt chunk、pipeline stage 数の定義。
- `src/dsv41/ds4_main.cpp:2549`、`src/dsv41/ds4_model.cu:2788-2805` — `--prefill-chunk` と `DS4_CHUNK` を含む prompt chunk の決定。
- `src/dsv41/ds4_main.cpp:1035-1039,1316-1330,1475-1486,1550-1551` — prompt error/cancel の出力、DONE と serve loop のログ。
