# `--n`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（Qwen3.6 reference CLI） |
| オプション | `--n` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換する値 |

## 役割

生成する greedy token の数を指定します。`strata-q36ref` は Qwen3.6 の照合用 reference executable で、CMake の GPU backend build 内に target が定義されています。索引の説明では、Release での配布実績は確認されていません（`CMakeLists.txt:771-775`、索引 `docs/cli/README.md:1487-1501`）。

## 使い方

```sh
strata-q36ref --model Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 248045,846,198 --n 64
```

`--model` と `--tokens` は必須です。usage の例も `--n 64` を示しています（`src/qwen35/q36ref.cu:25-27,760-763,771-774`）。

## 値と既定値

- 既定値は `64` です。parser は値を `std::atoi` で `int` に変換し、`--n` が複数回現れた場合は後の値が前の値を置き換えます（`src/qwen35/q36ref.cu:724-725,743`）。
- 明示的な数値形式・範囲・正数の検証はありません。`atoi` の変換結果をそのまま使うため、数値に変換できない値は `0` となり、負数も拒否されません。末尾に非数値文字を含む場合も、変換できる先頭部分が使われます（`src/qwen35/q36ref.cu:743`）。
- 値を省略すると `next()` が `q36ref: --n needs a value` を stderr に出して終了コード `2` で終了します（`src/qwen35/q36ref.cu:727-733,743`）。

## 実行時の動作

`--n` は prompt の長さ `P` と合わせて処理位置数 `total = P + n_gen - 1` を決めます。各 prompt token を処理した後、さらに必要な位置を1 tokenずつ実行し、各位置の greedy token を `gen` に追加します。通常は `--n 1` で1 token、既定の `--n 64` で64 token を出力します（`src/qwen35/q36ref.cu:797-820,826-830`）。

ただし `--force` から読み取った continuation が空でなければ、`n_gen` は `forced.size() + 1` に設定され、`--n` の値は使われません。forced token は次の forward pass へ入力されますが、表示する `gen` には各位置で計算した greedy token が追加されます（`src/qwen35/q36ref.cu:747,767-770,802-819`）。

`total > --ctx` の場合は処理位置数のエラーで終了コード `2` になります。`--n` 自体に下限検証はないため、0 または負値で `total` が prompt 長より小さくなれば、生成ループが prompt 全体に届かず、通常は生成 token のない `gen:` を出力します（`src/qwen35/q36ref.cu:797-802,826-830`）。

## 適用条件と副作用

モデルをロードして GPU state を初期化した後に `total > ctx` を検査します。また、`--dump-layers`、`--dump-logits`、`--dump-full-logits` が指定されていると、同検査より前に各ファイルを `wb` で開きます。そのため、context 超過で拒否される場合でもモデルのロード・GPU メモリー確保が先に行われ、指定済みダンプファイルは作成または切り詰められることがあります（`src/qwen35/q36ref.cu:775-800`。context cache の確保は `src/qwen35/q36ref.cu:558-587`）。

## 出力とエラー

- 正常終了時は stdout に `gen:` と greedy token ID 列を出し、stderr に prompt/generated position 数と所要時間を出します（`src/qwen35/q36ref.cu:826-831`）。
- context 超過時は stderr に `q36ref: <total> positions do not fit --ctx <ctx>` を出して `2` を返します（`src/qwen35/q36ref.cu:797-800`）。
- `--n` の値不足は stderr に不足を示して `2` で終了します。未知の引数は usage を stderr に出して `2` を返します（`src/qwen35/q36ref.cu:727-733,759-764`）。
- モデルのロード失敗や CUDA 呼び出し失敗では別の失敗経路があり、`--n` 専用のエラーではありません。前者は `1` を返し、CUDA error は `CK` macro が stderr に出して `1` で終了します（`src/qwen35/q36ref.cu:53-60,775-784`）。

## 根拠

- `src/qwen35/q36ref.cu:25-31` — executable の用途、usage、生成数の説明。
- `src/qwen35/q36ref.cu:722-770` — parser、`--n` の既定値・変換・`--force` による上書き。
- `src/qwen35/q36ref.cu:775-831` — モデル・state・出力ファイルの準備、位置数判定、生成ループ、出力と終了経路。
- `src/qwen35/q36ref.cu:551-588` — GPU allocation と attention cache の容量。
- `CMakeLists.txt:771-775` — `strata-q36ref` target の定義。
- `docs/cli/README.md:1487-1501`（調査リポジトリ）— tool-id、文書階層、`--n` 索引リンクと配布状況の注記。

調査は指定 checkout の parser と使用箇所に限定しました。CLI の実行、build、Release artifact の確認は行っていません。
