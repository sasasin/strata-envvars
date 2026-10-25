# `--tokens`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（トップレベル） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | 必須。トークン ID の列を表す文字列 |

## 役割

モデルへ渡す入力 prompt の token ID 列を指定します。これは CMake で GPU backend build 時に作られる Qwen3.6 reference executable のオプションで、通常の `strata` CLI のオプションではありません。索引では照合・開発用ツールとして扱われ、Release への同梱実績は確認されていません（`CMakeLists.txt:771-775`、[CLI 索引](../../README.md) の `strata-q36ref` 節）。

## 使い方

```sh
strata-q36ref --model ./Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 248045,846,198 --n 4
```

`--tokens` に渡す値は tokenizer によるテキストではなく、モデルが受け取る整数 ID の列です。実行例のモデルファイル名は usage にある形式に沿った例であり、ここではファイルの存在や実行可能性を確認していません（`src/qwen35/q36ref.cu:25-27,760-762`）。

## 値と既定値

- `--tokens` は次の argv 要素を値として受け取ります。値を省略すると `q36ref: --tokens needs a value` を stderr に出して終了コード 2 で終了します（`src/qwen35/q36ref.cu:725-735`）。
- 値はカンマ、空白、改行で区切られた整数列として読み取られます。各要素は `atoi` で変換されるため、整数として厳密に検証されず、数値として読めない要素は 0 になります（`src/qwen35/q36ref.cu:708-718`）。
- `--tokens` 自体に既定値はありません。未指定または空列は prompt が空として扱われ、`--model and --tokens are required` を stderr に出して終了コード 2 になります（`src/qwen35/q36ref.cu:766,771-773`）。
- 繰り返し指定時は通常の `--tokens` が内部文字列を置き換えるため、最後の `--tokens` が残ります。`--tokens-file` は同じ文字列へファイル内容を追記するので、両者を混ぜた場合は引数順によって置換・追記の結果が変わります（`src/qwen35/q36ref.cu:723-742`）。ファイル入力の詳細は [`--tokens-file`](--tokens-file.md) を参照してください。

## 実行時の動作

parse した列は prompt として保持され、全 token が順に `forward()` へ渡されます。各 token は token embedding の行を読み出す ID として使われます。テキストの tokenization はこの CLI 内では行いません（`src/qwen35/q36ref.cu:766,802-805,592-605,608-614`）。

prompt 処理後、既定ではさらに `--n` の既定値である 64 個の生成位置を処理します。全処理位置数 `prompt.size() + n_gen - 1` が `--ctx` の既定値 4096 を超えると、処理開始前にエラーを stderr に出して終了コード 2 になります。したがって prompt の長さは `--n` と `--ctx` の値にも影響します（`src/qwen35/q36ref.cu:724,797-800`）。

`--force` を併用すると、その値を同じ token 列 parser で読み取り、列が空でなければ生成位置数を「強制列の長さ + 1」に設定します。強制 token は次の forward に入力されますが、stdout に出す `gen:` 列は各生成位置での greedy ID です（`src/qwen35/q36ref.cu:747,767-770,802-818,826-828`）。

## 適用条件と副作用

この prompt は `strata-q36ref` の reference path でのみ適用されます。モデルをロードして GPU 上で token ごとに forward を行います（`src/qwen35/q36ref.cu:1-7,775-805`）。このツールは Qwen3.6 reference 用として CMake の GPU 条件内で定義されています（`CMakeLists.txt:771-775`）。

token ID の範囲を vocabulary サイズと照合する validation は、確認した parser と embedding 呼び出し経路にはありません。ID は embedding row index に直接渡されます（`src/qwen35/q36ref.cu:592-605,708-718`）。したがって範囲外 ID の安全な扱いはソースから確認できず、利用例では対象モデルに対応する有効な ID を指定してください。

## 出力とエラー

- 生成結果は stdout の `gen: <id> ...` に出力されます。実行時間と prompt/generated の位置数は stderr に出力されます（`src/qwen35/q36ref.cu:826-830`）。
- オプション値の欠落、prompt 列が空、または prompt と生成位置数が context に収まらない場合は stderr に診断を出して終了コード 2 になります（`src/qwen35/q36ref.cu:727-731,771-773,797-800`）。
- 不明なオプションでは usage を stderr に出して終了コード 2 になります（`src/qwen35/q36ref.cu:759-764`）。

## 根拠

- parser と必須値処理、`--tokens-file` との関係: `src/qwen35/q36ref.cu:723-765`
- token 列の変換と prompt/強制列への割り当て: `src/qwen35/q36ref.cu:708-718,766-773`
- context 上限、入力処理、greedy 出力: `src/qwen35/q36ref.cu:797-830`
- token ID が embedding row index として使われる箇所: `src/qwen35/q36ref.cu:592-605,608-614`
- reference executable の build target: `CMakeLists.txt:771-775`
