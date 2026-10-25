# `--vision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 family 用 parser）または `strata-q36` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | 取らない boolean flag |

## 役割

Qwen3.6 エンジンで画像入力経路を有効にします。サーバーモードでは画像を含む `GENI` リクエストを許可し、単発生成では `--tokens` の画像 token 列と `--emb` の `strata-vision` 埋め込みファイルを組み合わせて処理します。画像のエンコードをこの flag 自身が行うわけではなく、エンコーダーの出力をエンジンへ渡します。

## 使い方

サーバーとして起動する例:

```sh
strata --model /models/qwen36.gguf --serve --vision
```

単発で、画像用 token を含む prompt と埋め込みファイルを使う例:

```sh
strata-q36 --model /models/qwen36.gguf --tokens '248045,248056,248056,248045' --emb /tmp/image.sve --vision --n 64
```

2例目の token ID は構文例であり、画像 token の個数は埋め込みファイルの画像行数に一致させる必要があります。

## 値と既定値

`--vision` は値を取りません。指定すると parser が `vision = true` にし、省略時は `false` です。`--vision on` のように値を続ける構文ではありません。flag 自体に数値範囲や追加の parser validation はありません。

## 実行時の動作

`strata` は `--model` / `--native` で指定された GGUF の architecture が `qwen35moe` なら、引数全体を Qwen3.6 用 `strata::qwen35::run` に渡します。単独 executable `strata-q36` も同じ実装を呼び出します。その parser で `--vision` を受け、値を取らず boolean を有効にします（`src/program/generate.cpp:2393-2406`、`src/qwen35/q36_main.cpp:1-5`、`src/qwen35/q36_engine.cu:3735-3742,3774-3776`）。

有効時、エンジン初期化に flag が渡され、コンテキスト長に応じた M-RoPE 位置テーブル、prompt chunk に応じた cell-to-image-row map、および host 側 map バッファを確保します（`src/qwen35/q36_engine.cu:1339-1346,1497-1501,3863`）。そのため画像を含まない利用でも、起動時に画像経路用メモリを追加で必要とします。具体的なバイト数や VRAM 使用量はモデル形状・コンテキスト・chunk に依存します。

サーバーでは `GENI` リクエストが画像埋め込みファイルを伴います。`--vision` なしでその要求を送ると `ERR this engine was started without --vision` が返り、その要求は処理されません。flag の有無だけで encoder helper の起動、画像ファイルのダウンロード、ネットワークアクセスは発生しません（`src/qwen35/q36_engine.cu:3485-3504`）。

単発生成では `--emb` の指定も必要です。ファイルの各画像 record は `SVE1` magic、行数 `n`、格子幅 `nx`、高さ `ny`、埋め込み幅 `n_embd`、続いて `n × n_embd` 個の float です。`--tokens` 内の `<|image_pad|>` に対応する ID は `248056` で、record の行は prompt 内の連続した画像 token に割り当てられます。画像位置は M-RoPE の `(t,h,w)` に設定され、画像後のテキスト位置は格子の `max(nx, ny)` 分だけ進みます（`src/qwen35/q36_engine.cu:3083-3097,3127-3156,3916-3929`）。

`--serve` と `--emb` / `--tokens` は別の利用経路です。`--serve` では request ごとに `GENI` を用い、単発経路では起動引数の `--emb` ファイルを読みます。

## 適用条件と副作用

- Qwen3.6 (`qwen35moe`) parser に限る設定です。同じ `--vision` でも通常 engine や他の engine family では別スコープ・別実装です（索引の [`strata-engine/root/--vision.md`](../root/--vision.md) を参照）。
- ビルドに Qwen3.6 engine が含まれる必要があります。CMake は `strata-q36` を作り、`strata` に同じ engine library をリンクします（`CMakeLists.txt:782-792`）。
- `--vision` の指定単体には、モデルが vision をサポートするかの事前検証はありません。画像を処理する場合は、幅がモデルの `n_embd` と一致する有効な `strata-vision` record が必要です。
- 単発実行で `--emb` を使い `--vision` を省略すると stderr に `strata-q36: --emb needs --vision` を出して終了コード 2 になります（`src/qwen35/q36_engine.cu:3922-3926`）。
- 埋め込みファイルが開けない、record header が不正、float データが不足、prompt の画像 token が足りない、または prompt に余分な画像 token / 末尾画像 token がある場合、入力検証エラーで単発経路は終了コード 2 になります（`src/qwen35/q36_engine.cu:3096-3118,3129-3155,3924-3926`）。サーバー経路では対応する `GENI` request に `ERR ...` を出して要求を拒否します（`src/qwen35/q36_engine.cu:3505-3516`）。

## 出力とエラー

- サーバーの画像 request に対して flag が無効なら stdout に `ERR this engine was started without --vision` を出します（`src/qwen35/q36_engine.cu:3500-3504`）。
- 単発経路で `--emb` と flag の組み合わせが不正、または埋め込みファイルの形式・prompt との対応が不正なら stderr に `strata-q36: ...` を出し、終了コード 2 です（`src/qwen35/q36_engine.cu:3922-3926`）。
- 単発経路で画像を正しく読み込むと、stderr に画像数・埋め込み行数・画像後テキストの位置差分を出します（`src/qwen35/q36_engine.cu:3927-3929`）。
- 画像位置テーブルなどの GPU 確保は CUDA helper `CK` を通ります。個別の割り当て失敗メッセージや終了コードはこの箇所で明示されず、今回の調査では実行確認していません（`src/qwen35/q36_engine.cu:1497-1501`）。

## 根拠

- parser の既定値と `--vision` の flag 処理: `src/qwen35/q36_engine.cu:3735-3742,3774-3776`
- `strata` から Qwen3.6 parser への振り分け、および別 executable: `src/program/generate.cpp:2393-2406`、`src/qwen35/q36_main.cpp:1-5`
- engine 初期化と画像用 GPU / host buffer: `src/qwen35/q36_engine.cu:1339-1346,1497-1501,3863`
- server request の gate と入力検証: `src/qwen35/q36_engine.cu:3485-3516`
- 埋め込み file format と prompt への割り当て: `src/qwen35/q36_engine.cu:3083-3156`
- 単発経路の `--emb` 必須条件・エラー: `src/qwen35/q36_engine.cu:3916-3929`
- executable / library の build 定義: `CMakeLists.txt:782-792`

調査時点の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。CLI の help は実行せず、parser と使用箇所をソースで確認しました。
