# `--emb`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--emb` |
| 別名 | なし |
| 値 | `strata-vision` が出力した埋め込みファイルのパス |

## 役割

`--tokens` で与える prompt に含まれる画像位置 (`<|image_pad|>` token ID `248056`) へ、画像 encoder が作成した埋め込み行を割り当てます。画像埋め込みを使うには `--vision` も指定します。Qwen3.6 エンジンは `--emb` のファイルを読み、画像位置に対応する行を GPU に転送して、通常の token embedding の代わりに使用します（`src/qwen35/q36_engine.cu:3074-3096`, `src/qwen35/q36_engine.cu:3922-3929`, `src/qwen35/q36_engine.cu:2381-2400`, `src/qwen35/q36_engine.cu:2088-2091`）。

## 使い方

`strata-q36` を利用する例です。`IDS` は通常の token ID 列に、画像ごとの行数だけ連続した `248056` を含むカンマ区切り列です。`image.sve` は対応する `strata-vision` の出力ファイルです。

```sh
strata-q36 --model model.gguf --vision --tokens IDS --emb image.sve --n 64
```

ソースには比較用ツールから同じ指定を渡す例があります（`tools/qwen35/q36_vision_cmp.py:117-119`）。`strata-q36` は `src/qwen35/q36_main.cpp:1-5` の専用 entry point で、通常の `strata` もモデルを Qwen3.6 family に振り分けると同じ `run()` parser を使います（`src/qwen35/q36_engine.cu:3735-3742`）。

## 値と既定値

- 値は parser が次の argv 要素から文字列として受け取り、形式・拡張子の検査は行いません。値を省略すると `strata-q36: --emb needs a value` を stderr に出し、終了コード 2 で終了します（`src/qwen35/q36_engine.cu:3742-3747`, `src/qwen35/q36_engine.cu:3761`）。
- 既定値は空文字列です。`--emb` を省略した場合は画像ファイルを読みません。空文字列を値にした場合も空のままなので、後段の読み込み処理は行われません（`src/qwen35/q36_engine.cu:3736`, `src/qwen35/q36_engine.cu:3922`）。
- 複数回指定した場合は parser が同じ変数へ順に代入するため、最後の値が残ります（`src/qwen35/q36_engine.cu:3742-3747`, `src/qwen35/q36_engine.cu:3761`）。
- ファイルは複数 record を連結した形式です。各 record は int32 5個（magic `SVE1`、行数 `n`、幅 `nx`、高さ `ny`、埋め込み幅 `n_embd`）に続いて `n × n_embd` 個の float32 を持ちます。encoder 側の書き出しと engine 側の読み込み形式は一致します（`tools/vision/strata_vision.cpp:14`, `tools/vision/strata_vision.cpp:324-326`, `src/qwen35/q36_engine.cu:3092-3097`）。engine は行数・幅・高さが正、`nx × ny == n`、`n_embd` がモデルの埋め込み幅と一致することを検証します（`src/qwen35/q36_engine.cu:3100-3115`）。

## 実行時の動作

- `--emb` は値を保存するだけで、単発実行の処理に入った後、prompt を parse したうえで読み込みます。`--vision` がない場合は stderr に `strata-q36: --emb needs --vision` を出し、終了コード 2 になります（`src/qwen35/q36_engine.cu:3758-3762`, `src/qwen35/q36_engine.cu:3916-3926`）。
- ファイルを開けない場合、header 不正またはモデルの埋め込み幅と不一致の場合、float32 payload が不足する場合はエラーになります。さらに、prompt と file の画像数、および各画像 record の行数と連続する `248056` の数が一致しなければ拒否します。画像位置が prompt の末尾にある場合も拒否します（`src/qwen35/q36_engine.cu:3096-3118`, `src/qwen35/q36_engine.cu:3127-3155`）。
- record の行は順番に画像位置へ割り当てられます。各行の座標は record の `nx` を使って `(t, h, w) = (p, p + row, p + column)` とし、画像の後の text の位置は `max(nx, ny)` だけ進めます（`src/qwen35/q36_engine.cu:3092-3095`, `src/qwen35/q36_engine.cu:3141-3155`）。
- 読み込み成功後、埋め込み行と cell→row map、M-RoPE table を GPU 側へ転送します。forward 時には画像 cell の行を `d_img` から入力 hidden rows へ書き込みます（`src/qwen35/q36_engine.cu:2386-2400`, `src/qwen35/q36_engine.cu:2410-2426`, `src/qwen35/q36_engine.cu:2088-2091`, `src/qwen35/q36_engine.cu:2139-2142`）。
- `--serve` は model load 後に単発実行の分岐へ進まず serve loop に入るため、起動時の `--emb` ファイルはそこで消費されません。serve の画像要求は `GENI` protocol の各要求が埋め込みファイル名を持ち、`build_images()` を要求単位で呼びます。serve で画像を受けるには起動時 `--vision` が必要です（`src/qwen35/q36_engine.cu:3888-3890`, `src/qwen35/q36_engine.cu:3486-3516`）。

## 適用条件と副作用

- `--emb` は Qwen3.6 parser のオプションです。通常 engine parser の `--embd-gguf` とは別の名前・用途です（索引 [`README.md`](../../../README.md) の Qwen3.6 scope、および `src/qwen35/q36_engine.cu:3761`）。
- prompt 上の各画像は、対応する行数分の連続した image-pad token を必要とします。record が余る、足りない、あるいは prompt が画像 token で終わる場合は失敗します（`src/qwen35/q36_engine.cu:3127-3155`）。
- ファイルは `fopen(..., "rb")` で読み、成功時に閉じます。読み込み後の embedding row buffer GPU へ転送され、モデル forward 中に参照されます（`src/qwen35/q36_engine.cu:3099-3118`, `src/qwen35/q36_engine.cu:2391-2400`）。ファイルへの書き込みや削除はこの経路では行いません。
- `--emb` の単発画像処理は `--tokens` 実行経路であり、`--serve` の画像入力とは形式の渡し方が異なります。単発経路では file の画像 embedding の hash を画像識別子に含めます（`src/qwen35/q36_engine.cu:3133-3140`）。

## 出力とエラー

単発経路ではファイル読込や画像配置のエラー文を stderr に出し、終了コード 2 を返します。確認できる失敗には、`--vision` の欠落、ファイルを開けない、bad embeddings file、short embeddings file、prompt/file 間の画像数不一致、画像 row 数に対する image-pad token 不足、prompt が画像で終わる場合があります（`src/qwen35/q36_engine.cu:3100-3114`, `src/qwen35/q36_engine.cu:3130-3155`, `src/qwen35/q36_engine.cu:3922-3926`）。正常時は画像数・行数・画像後の text の cell offset を stderr に出力します（`src/qwen35/q36_engine.cu:3927-3929`）。

## 根拠

- parser と既定状態: `src/qwen35/q36_engine.cu:3735-3762`
- ファイル形式と検証、画像位置への配置: `src/qwen35/q36_engine.cu:3092-3157`
- encoder のファイル書き出し形式: `tools/vision/strata_vision.cpp:14`, `tools/vision/strata_vision.cpp:324-326`
- GPU への設定と forward 入力への反映: `src/qwen35/q36_engine.cu:2381-2426`, `src/qwen35/q36_engine.cu:2088-2091`, `src/qwen35/q36_engine.cu:2139-2142`
- 単発実行での条件・エラー・ログ: `src/qwen35/q36_engine.cu:3916-3929`
- serve 要求ごとの画像指定と検証: `src/qwen35/q36_engine.cu:3486-3516`, `src/qwen35/q36_engine.cu:3888-3890`
- CLI 使用例: `tools/qwen35/q36_vision_cmp.py:117-119`
