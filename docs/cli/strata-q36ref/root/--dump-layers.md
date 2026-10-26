# `--dump-layers`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（root scope） |
| オプション | `--dump-layers` |
| 別名 | なし |
| 値 | 出力ファイルの path（1 引数） |

## 役割

処理した各 token 位置について、各 transformer layer の出力 hidden state を float32 のバイナリファイルへ保存します。Qwen3.6 reference executable の中間値照合用です。これは製品の `strata generate` ではなく、CMake が GPU backend build 内で定義する独立した `strata-q36ref` executable のオプションです（`CMakeLists.txt:771-775`）。

## 使い方

既存ファイルを上書きしないよう、新しい出力 path を指定します。

```sh
strata-q36ref --model model.gguf --tokens 248045,846,198 --dump-layers ./run-20261026.layers.f32
```

`--model` と `--tokens` は必須です（`src/qwen35/q36ref.cu:771-773`）。

## 値と既定値

- 値は path 文字列です。option parser は path の形式、拡張子、書き込み可能性を事前検証しません。値を省略すると `q36ref: --dump-layers needs a value` を stderr に出して終了コード 2 で終了します（`src/qwen35/q36ref.cu:725-732,745`）。
- 未指定時の内部値は空文字列で、layer dump を行いません。明示した値が空文字列の場合も同じく出力しません（`src/qwen35/q36ref.cu:723-724,790`）。
- 同じ option を複数回指定すると parser は値を順に代入し、最後の値だけを後段で開きます（`src/qwen35/q36ref.cu:725-746,790`）。
- 指定 path は `fopen(path, "wb")` で開かれます。既存ファイルを指定すると内容を切り詰めます（`src/qwen35/q36ref.cu:790`）。

## 実行時の動作

モデル読み込み後、状態初期化の後に layer dump のファイルを開きます。各 layer の MoE 加算を終えた時点の `s.x` を、layer 順に host buffer へコピーします。1 回の forward が終わると、その buffer 全体を `fwrite` で出力します。したがって出力は処理位置順に `[position][layer][n_embd]` の float32 が連続する形式です。コードのコメントは Qwen3.6 の 40 層を説明していますが、実際の buffer 長は読み込んだモデルの `n_layers * n_embd` です（`src/qwen35/q36ref.cu:9-23,652-700,789-805`）。

出力対象の position は prompt の全 token と、その後に実際に forward した continuation token です。既定の `--n 64` では `total = prompt.size() + 63` 回 forward し、各回の dump を試みます。`--n` や `--force` によって forward 回数が変わります（`src/qwen35/q36ref.cu:743,767-770,797-805`）。

## 適用条件と副作用

- `strata-q36ref` は Qwen3.6 (`qwen35moe`) 用 reference path です。異なる model family は `load` で拒否されます（`src/qwen35/q36ref.cu:479-488`）。
- モデル読み込みと GPU state 初期化の後にファイルを開きます。指定した path が書き込み可能でない場合、`fopen` は null を返しますが、プログラムはエラーを表示せず `fl == nullptr` のまま続行し、layer dump を無効化します（`src/qwen35/q36ref.cu:786-805`）。
- context 超過はファイルを開いた後に検査されます。そのため `total > ctx` の場合は終了コード 2 で終了し、すでに作成・切り詰めた dump file は空のまま残り得ます（`src/qwen35/q36ref.cu:790-800`）。
- `fwrite` と `fclose` の戻り値は検査されません。ディスク不足などで書き込みが完了しなくても、専用のエラー表示や失敗終了を行わない実装です（`src/qwen35/q36ref.cu:802-825`）。

## 出力とエラー

この option 固有の成功メッセージはありません。生成 token は stdout の `gen: ...`、実行時間などは stderr に出ます（`src/qwen35/q36ref.cu:826-830`）。option の値不足は stderr と終了コード 2、model/context 条件の失敗もそれぞれ stderr と非 0 終了になります（`src/qwen35/q36ref.cu:725-731,771-800`）。出力 file の open・write 失敗自体は検出されないため、CLI の終了コードだけでは dump の完全性を確認できません。

## 根拠と調査範囲

- `src/qwen35/q36ref.cu:25-31` — usage コメントと想定形式の説明。
- `src/qwen35/q36ref.cu:722-765` — parser、値の取得、option 不明時の usage 出力。
- `src/qwen35/q36ref.cu:652-705` — layer 出力の取得位置と各 position の forward 処理。
- `src/qwen35/q36ref.cu:786-831` — file open、context 判定、連続書き込み、close、終了時出力。
- `CMakeLists.txt:771-775` — executable target と GPU backend build への配置。

同一 revision の既存実行ファイルによる `--help` 表示や Release artifact は確認していません。parser と実際の処理は上記 checkout のソースで照合しました。
