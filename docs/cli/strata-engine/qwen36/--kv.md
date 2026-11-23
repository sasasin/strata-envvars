# `strata` / `strata-q36`（Qwen3.6）`--kv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--kv` |
| 別名 | なし（値の別表記は「値と既定値」を参照） |
| 値 | K/V cache の形式。`fp32`、`fp16`、`fp8`、`fp4` と、それぞれの受理別表記。`--kv=value` 形式も可 |

## 役割

Qwen3.6 エンジンの attention 層に置く key/value cache の格納幅・量子化形式を選ぶ。既定の `fp32` から `fp16`、`fp8`（内部では INT8）、`fp4`（内部では Q4_0 形式）へ変更すると、cache の要素あたりの保存量を小さくできる。形式は起動時に選択され、cache の確保と attention の書き込み・読み出しに一貫して適用される。Qwen3.6 以外の engine parser にある同名 `--kv` とは別スコープである。モデルの architecture が `qwen35moe` のとき `strata` は引数を Qwen3.6 engine に渡し、単体実行ファイル `strata-q36` も同じ `run` parser を使う（`engine/src/program/generate.cpp:3799-3813`、`engine/src/qwen35/q36_main.cpp:1-5`）。

## 使い方

```sh
strata --model /path/to/qwen36.gguf --kv fp16 --tokens '1,2,3'
strata-q36 --model /path/to/qwen36.gguf --kv=fp8 --serve
```

`--model` で Qwen3.6 GGUF を選び、`--kv` の後に形式を 1 つ渡す。parser は別引数形式と `--kv=value` 形式の両方を受け付ける（`engine/src/qwen35/q36_engine.cu:5393-5403`）。

## 値と既定値

| 指定値 | 同等な受理値 | 内部形式 | K/V row の保存幅 |
| --- | --- | --- | --- |
| 省略時 | — | `fp32` | 1 要素 4 byte |
| `fp32` | `f32` | FP32 | 1 要素 4 byte |
| `fp16` | `f16`、`half` | FP16 | 1 要素 2 byte |
| `fp8` | `int8`、`q8`、`q8_0` | INT8 | 1 要素 1 byte と K/V それぞれ 1 float scale / KV head / cell |
| `fp4` | `q4`、`q4_0` | 4-bit Q4_0 形式（Hadamard 回転） | 1 要素 0.5 byte と K/V それぞれ 1 FP16 scale / 32 要素 |

parser 初期値は `KV_FP32`。値の比較は大文字小文字を区別し、上表にない値は受け付けない。値の別表記はオプション名の alias ではない。`--kv` を複数回指定した場合、parser は同じ変数を都度更新するため最後の指定が残る（`engine/src/qwen35/q36_engine.cu:5347-5348,5393-5403`）。

各幅と scale 配列の大きさは `kv_row_bytes` / `kv_scale_bytes` で算出される（`engine/src/qwen35/q36_engine.cu:104-118`）。FP32 と FP16 は追加 scale なし、INT8 は 1 float / cell、Q4 は 1 FP16 / 32 要素である。これは cache row の保存量であり、その他の engine バッファを含む VRAM 全体の量ではない。

## 実行時の動作

`--kv` の選択は `Engine` に渡され、各 attention 層および GGUF 内の MTP attention block の K/V cache と scale 配列を、その形式の幅で GPU に確保する。recurrent state 用の領域はこの選択の対象外（`engine/src/qwen35/q36_engine.cu:5466-5468,1888-1903,1905-1933`）。

Attention の cache 書き込み側は FP32 / FP16 / INT8 / Q4 ごとの kernel を選択する。INT8 は K と V の各 row の最大絶対値から scale を計算して符号付き 8-bit 値にし、Q4 は K/V を 256 要素 Hadamard 基底に回転して 4-bit code と block scale を保存する（`engine/src/qwen35/q36_engine.cu:405-457,460-526,2774-2800`）。Q4 の読み出しでは query も同じ基底へ回転し、prompt 用に展開する経路では K/V を dequantize して逆回転する（`engine/src/qwen35/q36_engine.cu:659-690,834-857,2810-2825`）。FP16/INT8/Q4 には、それぞれ対応する attention reader が使われる（`engine/src/qwen35/q36_engine.cu:2866-2888`）。

`--max-context` と `--batch` は必要な cache 容量に関係する。起動時の必要 VRAM 判定は選択中の KV 形式の byte 数を用いており、複数 session の見積もり・不足判定にも反映する（`engine/src/qwen35/q36_engine.cu:2142-2159`）。形式は cache 確保前に選ぶ起動時設定で、実行中に切り替える仕組みは確認できない。

## 適用条件と副作用

- `fp4` / `q4` / `q4_0` は model の `head_dim` が 256 の場合に限り初期化を続ける。異なる場合は `strata-q36: --kv fp4 rotates 256-value rows, this model's head_dim is ...` を stderr に出して終了コード 2 で終了する。この検査は session cache の確保後に行われる（`engine/src/qwen35/q36_engine.cu:2140-2184,2249-2252`）。
- `fp32` 以外は cache と scale 用に形式別の GPU メモリを確保する。GPU メモリ不足時には、複数 session の事前見積もりで拒否して理由を stderr に出し終了コード 1 となる場合がある。その他の CUDA allocation/API エラーも共通 `CK` 経由で stderr にエラーを出し終了コード 1 で終了する（`engine/src/qwen35/q36_engine.cu:82-89,2151-2181,1888-1903`）。
- 起動時には選択した cache 形式、attention 層あたりの KiB/token、空き VRAM を stderr に表示する（`engine/src/qwen35/q36_engine.cu:2254-2259`）。ファイル・ネットワークへの副作用はこのオプションの実装では確認できず、変更対象は実行中の GPU cache である。

## 出力とエラー

`--kv` に値が続かない場合は `strata-q36: --kv needs a value` を stderr に出し、終了コード 2 で終了する。未知の値では `strata-q36: --kv takes fp32, fp16, fp8 or fp4 (not <値>)` を stderr に出し、終了コード 2 を返す（`engine/src/qwen35/q36_engine.cu:5350-5352,5393-5403`）。受理時の形式とメモリ表示は前節のとおり。CUDA メモリ/API の失敗経路は「適用条件と副作用」を参照。

## 根拠

- `engine/src/program/generate.cpp:3799-3813` — `--model` / `--native` の GGUF architecture を見て、`qwen35moe` の場合に Qwen3.6 parser へ切り替える。
- `engine/src/qwen35/q36_main.cpp:1-5` — 単体 `strata-q36` の入口が共通の `strata::qwen35::run` を呼ぶ。
- `engine/src/qwen35/q36_engine.cu:5347-5403,5466-5468` — parser の既定値、受理値・値別表記、形式設定と `Engine` への引き渡し。
- `engine/src/qwen35/q36_engine.cu:104-118,1888-1933,2142-2184` — row / scale のサイズ計算、attention と MTP cache の確保、VRAM 見積もりと不足時の拒否。
- `engine/src/qwen35/q36_engine.cu:405-526,659-690,834-857,2774-2800,2810-2825,2866-2888` — INT8/Q4 の格納・読み出しと各形式の attention kernel 選択。
- `engine/src/qwen35/q36_engine.cu:82-89,2249-2259` — CUDA API エラー処理、Q4 の head dimension 条件、起動時の cache 形式表示。
