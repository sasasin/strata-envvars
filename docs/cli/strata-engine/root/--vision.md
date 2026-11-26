# `strata --vision`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

`--serve` の永続エンジンに画像入り `GENI` リクエストを受け付けさせます。画像そのものをこの引数に渡すのではなく、`strata-vision` が出力した埋め込みファイルと、画像位置を示す `<|image_pad|>` トークン列をリクエストで渡します。エンジンは画像埋め込みを対応するトークン位置へ入力し、画像用の M-RoPE 位置テーブルを使います（`engine/src/program/generate.cpp:1292`, `engine/src/program/generate.cpp:16531-16535`）。

## 使い方

```sh
# 永続エンジンを画像リクエスト対応で起動する
strata --model ./model.strata --serve --vision
```

起動後の標準入力で、画像埋め込みファイルへのパスを含む `GENI` 行を送ります。形式は `GENI <max_new> <embeddings-file> <id,id,...>` です。各画像には、埋め込み行数と同数の連続した `<|image_pad|>` token ID が必要です（`engine/src/program/generate.cpp:18808-18823`, `engine/src/program/generate.cpp:19059-19085`）。

## 値と既定値

引数値は取りません。指定されると `o.vision` が `true` になり、未指定時は `false` のままです。繰り返し指定しても同じ真偽値を設定するだけです（`engine/src/program/generate.cpp:1082-1083`, `engine/src/program/generate.cpp:4069-4070`）。

## 実行時の動作

起動時、指定されていれば `max_context + 64` セル分の `(t, h, w)` 位置表をホスト上に作り、全セルを `(c, c, c)` の恒等位置で初期化して CUDA デバイスへコピーします。割り当てまたはコピーに失敗すると `cannot allocate the image position table` を stderr に出し、終了コード `1` で終了します。複数 GPU の layer split では各 stage のデバイスにも同じ表を配置し、どのデバイスでもグラフ取得前に設定します（`engine/src/program/generate.cpp:6124-6140`, `engine/src/program/generate.cpp:6698-6708`）。

`--serve` の入力ループは `GENI` を画像リクエストとして認識します。埋め込みファイルは1件以上の連続レコードで、各レコードは `int32` の `{0x31455653 ('SVE1'), n, nx, ny, n_embd}` と、それに続く `n × n_embd` 個の `float32` です。`n`、`nx`、`ny` は正、`nx × ny == n`、`n_embd` はロードしたモデルの埋め込み幅でなければなりません。Strata の `strata-vision` もこの形式を書き出します（`engine/src/program/generate.cpp:16531-16535`, `engine/src/program/generate.cpp:19039-19054`, `terminal/tools/vision/strata_vision.cpp:3-13`）。

画像レコードは prompt 中の `<|image_pad|>` の連続領域に順番に対応します。レコード行ごとに埋め込みを入力し、位置を `t=p, h=p+y, w=p+x` と設定します。画像の後のテキスト位置は `p + max(nx, ny)` から続きます。構築した位置表は CUDA0 と layer split の各 stage に転送され、テキストだけの次のリクエストでは恒等位置へ戻されます（`engine/src/program/generate.cpp:19057-19087`, `engine/src/program/generate.cpp:19091-19114`）。

## 適用条件と副作用

- 画像リクエスト処理は `--serve` の `GENI` 経路にあります。通常の非 serve 実行では `GENI` 入力ループを通らず、`--vision` を付けても画像ファイルを読む処理はありません（serve ループの説明: `engine/src/program/generate.cpp:11095-11116`）。
- `--vision` は起動時に画像位置表を GPU メモリへ確保します。さらに vision 有効状態は reader 用 VRAM reserve の計算にも渡されます。resident RAM mode が reserve を調整する場合、stderr に調整値を出します（`engine/src/program/generate.cpp:8975-8984`）。
- このオプションだけでは画像をデコード・埋め込み化しません。`strata-vision` で生成した埋め込みファイルを `GENI` リクエストから参照します（`terminal/tools/vision/strata_vision.cpp:3-13`, `engine/src/program/generate.cpp:18808-18823`）。
- `strata-engine/qwen36` の `--vision` は別コマンド階層・別 parser で、`engine/src/qwen35/q36_engine.cu` が定義します。本書は索引上の root scope（`engine/src/program/generate.cpp`）だけを扱います（ツール parser の所在と scope: `docs/cli/000_cli_tools.md:10`, qwen36 の option 索引: `docs/cli/README.md:1228`, `docs/cli/README.md:1242-1275`）。

## 出力とエラー

- `GENI` を受けたがエンジン起動時に `--vision` がなかった場合、stdout に `ERR this engine was started without --vision` を出して、そのリクエストを拒否します（`engine/src/program/generate.cpp:19011-19012`）。
- 埋め込みファイルを開けない、ヘッダーや幅が不正、データが短い、prompt と画像レコード数または image-pad 数が合わない、末尾が image-pad である、位置表の転送に失敗した場合は stdout に `ERR <理由>` を出します。失敗時は位置表を恒等位置に戻してから次のリクエストを処理します（`engine/src/program/generate.cpp:19039-19056`, `engine/src/program/generate.cpp:19059-19111`）。
- 画像 request の `max_new`・token 列の構文不正は `ERR bad request: ...` として拒否されます（`engine/src/program/generate.cpp:18974-18979`）。

## 根拠

- `engine/src/program/generate.cpp:1292` — help 文の説明（`--serve` が GENI 画像リクエストを受け付ける）。
- `engine/src/program/generate.cpp:4069-4070` — root parser の `--serve` / `--vision` 分岐。
- `engine/src/program/generate.cpp:6124-6140`, `engine/src/program/generate.cpp:6698-6708` — 位置表の作成と各 CUDA device への配置。
- `engine/src/program/generate.cpp:16531-16535`, `engine/src/program/generate.cpp:18808-18823`, `engine/src/program/generate.cpp:19039-19114` — GENI 形式、埋め込みレコード、対応検証、位置表更新と失敗処理。
- `engine/src/program/generate.cpp:8975-8984` — vision 有効時の reader reserve 調整。
- `terminal/tools/vision/strata_vision.cpp:3-13` — `strata-vision` が出力する SVE1 レコード形式。
