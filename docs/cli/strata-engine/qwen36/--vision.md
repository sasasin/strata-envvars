# `strata` / `strata-q36` `--vision`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata --model`（Qwen3.6-35B-A3B 選択時）または `strata-q36` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Qwen3.6 エンジンで画像を含む入力を処理できるようにする。`--vision` 自体は画像をエンコードせず、画像エンコーダーが出力した `strata-vision` 埋め込みを、プロンプト内の `<|image_pad|>` token に対応づけて推論する機能を有効にする。エンジン起動時に画像位置テーブル等の領域を用意し、画像を含む要求で埋め込み行と M-RoPE 位置情報を利用する（`engine/src/qwen35/q36_engine.cu:2213-2217,3637-3657,3670-3708`）。

## 使い方

```sh
# サーバーモード。画像要求は strata-vision の埋め込みファイルを使う GENI/BGENI プロトコルで送る
strata --model Qwen3.6-35B-A3B.gguf --serve --vision

# 事前に用意した token 列と strata-vision 埋め込みファイルで単発推論
strata --model Qwen3.6-35B-A3B.gguf --vision --tokens '1,248056,2' --emb /path/to/image.sve --n 64
```

`strata` はモデルの GGUF architecture が `qwen35moe` の場合に Qwen3.6 専用 parser へ引数を渡す。`--vision` はこの専用 parser で値なしとして認識される（`engine/src/program/generate.cpp:3804-3818`, `engine/src/qwen35/q36_engine.cu:5348-5382`）。

## 値と既定値

値を取りません。省略時は `false`、指定時は `true` です。重複指定を拒否する分岐はなく、繰り返し指定しても同じ真偽値のままです。値を消費しないため、直後に別の位置引数を置くとその引数は未対応として usage を出して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:5346-5353,5381,5405-5417`）。

## 実行時の動作

- `--vision` が真なら `Engine::init` が画像位置テーブルとセル対応 map を確保する。画像埋め込み本体の GPU バッファは、画像要求で `set_images` が呼ばれた際に必要量を確保・転送する（`engine/src/qwen35/q36_engine.cu:2213-2217,3641-3656`）。
- 単発推論では `--emb FILE` も必要で、`--tokens` の ID 列中の `<|image_pad|>` token 群とファイル内の画像レコードを対応づける。`build_images` は `SVE1` ヘッダー、行数・画像グリッド、モデル埋め込み幅を確認し、画像 token の埋め込み行と M-RoPE 座標を組み立てる（`engine/src/qwen35/q36_engine.cu:4621,4638-4702,5364-5368,5601-5608`）。エンジンは対応する prompt cell の埋め込みを画像行で置き換え、画像位置テーブルを prompt の forward に使う（`engine/src/qwen35/q36_engine.cu:3637-3640,3666-3708`）。
- `--serve` ではクライアントが `GENI`（batch 時は `BGENI`）要求に埋め込みファイルを指定する。通常の `GEN` / `BGEN` は画像入力要求ではない。Qwen3.6 engine は `--vision` を起動時に保持し、画像要求を受け付ける（`engine/src/qwen35/q36_engine.cu:4720-4723,5004-5009,5073-5090,5130-5131`）。このオプションは画像エンコーダーを起動せず、画像ファイルを直接読み込むオプションでもない。

## 適用条件と副作用

Qwen3.6 専用 parser のスコープです。`strata` では `--model` / `--native` で指定した GGUF の architecture が `qwen35moe` のときに専用 parser に振り分けられます。別 architecture では通常のエンジン parser が使われます（`engine/src/program/generate.cpp:3804-3819`）。

`--vision` だけでは画像入力は行いません。単発モードで `--emb` を指定したのに `--vision` がなければエラーになります。画像を使わない起動でも指定すれば、初期化時に画像位置情報用の device / host 領域を追加で確保します（`engine/src/qwen35/q36_engine.cu:2213-2217,5601-5605`）。

## 出力とエラー

- 単発モードで `--emb` を `--vision` なしに指定すると、stderr に `strata-q36: --emb needs --vision` を出し、終了コード 2 で終了する（`engine/src/qwen35/q36_engine.cu:5601-5603`）。
- 埋め込みファイルを開けない、ヘッダーやモデル幅が不正、データが不足、画像レコード数と `<|image_pad|>` 群が合わない、または prompt が画像 token で終わる場合、単発モードは理由を stderr に出して終了コード 2 となる（`engine/src/qwen35/q36_engine.cu:4642-4664,4673-4702,5603-5605`）。
- server が `--vision` なしで `GENI` / `BGENI` を受けた場合は stdout に `ERR this engine was started without --vision` を返して要求を拒否する。要求形式・context 長・token ID・埋め込みの不整合も stdout の `ERR` 応答で拒否する（`engine/src/qwen35/q36_engine.cu:5067-5089`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3819` — `qwen35moe` architecture を Qwen3.6 parser に振り分ける箇所。
- `engine/src/qwen35/q36_engine.cu:5346-5417` — `--vision` の値なし parser、serve 時の未知 option 処理と usage/error 経路。
- `engine/src/qwen35/q36_engine.cu:2213-2217,3637-3708` — vision 用領域の確保、埋め込み行・M-RoPE の適用。
- `engine/src/qwen35/q36_engine.cu:4621-4702,5004-5090,5130-5131,5601-5608` — 埋め込みファイル形式、GENI/BGENI と単発推論での適用・拒否経路。
