# `--ctx`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（トップレベル） |
| オプション | `--ctx N` |
| 別名 | なし |
| 値 | `std::atoi` で整数化するコンテキスト位置数。既定値 `4096` |

## 役割

Qwen3.6-35B-A3B の参照 executable が確保する attention K/V cache の容量と、処理できる prompt・生成位置の合計上限を指定します。この executable は GPU backend build で作られる照合用プログラムです。ソースコメントでは全モデルを VRAM に常駐させ、prompt も含め一度に1 tokenずつ処理する参照経路とされています（`CMakeLists.txt:771-775`; `src/qwen35/q36ref.cu:1-7`）。

## 使い方

```sh
strata-q36ref --model Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 248045,846,198 --ctx 8192
```

`--model` と `--tokens` は必須です。`--ctx` を省略すると `4096` です（`src/qwen35/q36ref.cu:25-31,722-745,771-774`）。

## 値と既定値

- parser の初期値は `4096`、指定値は `std::atoi` で `int` に変換されます。同じオプションを複数回指定すると後の値が前の値を上書きします（`src/qwen35/q36ref.cu:724-745`）。
- `atoi` のため、数値として解釈できない文字列や空文字列は `0` になります。ソースには `--ctx` 固有の正数・最小値・最大値検証がありません。
- `--ctx` の値がない場合は `q36ref: --ctx needs a value` を stderr に出し、終了コード `2` で終了します（`src/qwen35/q36ref.cu:727-732`）。

## 実行時の動作

parser の値は `State::ctx` に設定され、各 attention/QSA layer の K cache と V cache をそれぞれ `n_head_kv × ctx × head_dim` 個の float として GPU に確保します（`src/qwen35/q36ref.cu:542-549,575-580,786-788`）。Attention preparation と attention kernel の双方にも `s.ctx` が渡され、cache と context の上限として使われます（`src/qwen35/q36ref.cu:645-649`）。

実行前には `total = prompt token 数 + n_gen - 1` を計算し、`total > ctx` なら処理を拒否します。`--force` に空でない continuation を渡すと `n_gen` が `force` token 数 + 1 に置き換わるため、`--ctx` と合わせたこの総数判定に影響します（`src/qwen35/q36ref.cu:766-770,797-800`）。

## 適用条件と副作用

- このオプションは `strata-q36ref` のみのもので、通常の `strata` 推論 engine の `--ctx` と同一の parser ではありません。CMake 上は `strata-q36ref` を GPU backend build 部分に定義しています（`CMakeLists.txt:335,771-775`）。
- `--ctx` は値が大きいほど、QSA layer ごとに確保する K/V GPU memory を増やします。モデルのロード後、`--ctx` を state に設定して GPU state を初期化し、その後に prompt と生成位置の合計を上限検査します。そのため、容量不足を検出する前に大きな cache allocation を試みる場合があります（`src/qwen35/q36ref.cu:775-800`）。
- 同じ順序により、`--dump-layers`、`--dump-logits`、`--dump-full-logits` のファイルが指定されていると、`--ctx` 上限の拒否より前に `fopen(..., "wb")` で作成または切り詰められます。失敗後にこれらのファイルが残ることがあります（`src/qwen35/q36ref.cu:786-800`）。
- 0、負数、数値でない値への専用 validation はありません。特に 0 や負数で cache allocation がどう失敗するかは CUDA runtime とデバイス状況に依存し、ソースだけでは結果を一意に断定できません。安全な値域はこの調査では確定できません。

## 出力とエラー

- prompt と生成の合計位置が `--ctx` を超える場合、stderr に `q36ref: <total> positions do not fit --ctx <ctx>` を出して終了コード `2` で終了します（`src/qwen35/q36ref.cu:797-800`）。
- cache などの CUDA allocation / memory 操作が失敗すると、`CK` macro が `q36ref: <CUDA expression> failed: <CUDA error> (<file>:<line>)` を stderr に出して終了コード `1` で終了します（`src/qwen35/q36ref.cu:53-60,551-555`）。
- `--help` 専用分岐はなく、未認識 option として usage を stderr に出し終了コード `2` になります。usage に `--ctx 4096` が示されています（`src/qwen35/q36ref.cu:759-764`）。

## 根拠と調査範囲

- `src/qwen35/q36ref.cu:722-745` — parser、既定値、整数変換、値不足処理。
- `src/qwen35/q36ref.cu:575-580,645-649,786-800` — cache 容量への反映、attention への引き渡し、上限検査の順序。
- `CMakeLists.txt:771-775` — executable の定義。
- `docs/cli/README.md` は `strata-q36ref/root/--ctx.md` を `strata-q36ref` のトップレベル option として索引化しています（`docs/cli/README.md:1487-1495`）。
- 調査は上記 commit の checkout ソースに限定しました。CLI バイナリの `--help` は実行していません。CMake の build 条件とソース parser は確認しましたが、backend/platform ごとの実機動作や Release 配布物での有無はこの option 文書では確認していません。
