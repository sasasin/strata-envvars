# `--force`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（サブコマンドなし） |
| オプション | `--force` |
| 別名 | なし |
| 値 | カンマ、空白、改行で区切る token ID 列 |

## 役割

プロンプトの後にモデルが選んだ greedy token を次の入力に使う代わりに、指定した token 列を順番に入力します。Qwen3.6 reference path の同一 token 列での比較（teacher forcing）に使う機能です。各位置の logits から選んだ greedy token は `gen:` に出力され続けます。

この実行ファイルは CMake の GPU backend 条件内で定義される照合用 CLI です。索引では現行 Release への同梱を確認できていないとされています。

## 使い方

```sh
strata-q36ref --model model.gguf --tokens 248045,846,198 --force 12,34,56
```

`--model` と `--tokens` は必須です。実際の起動には GPU backend を有効にしてビルドした `strata-q36ref` と、対応するモデル・GPU 環境が必要です。

## 値と既定値

- 値は必須です。次の引数を値として受け取ります。省略すると `q36ref: --force needs a value` を stderr に出して終了コード 2 で終了します。
- `--force` 自体の既定値は空です。空、または `parse_ids` の結果が空になる値では forcing は有効になりません。
- token 列はカンマ、空白、改行で区切られ、各要素は `std::atoi` で整数に変換されます。厳密な数値形式や token ID の範囲を検査する処理はこの parser 経路にはありません。数値以外を含む要素は `atoi` により 0 になる場合があるため、モデルの語彙に対応する整数 ID を指定してください。
- オプションを複数回指定した場合、引数走査中に同じ文字列変数へ代入されるため、最後の値が残ります。

## 実行時の動作

`--force` の値を token 列へ変換し、列が空でなければ生成位置数 `n_gen` を強制列の要素数＋1に設定します。この後に適用されるため、引数順にかかわらず非空の `--force` は `--n` の値を上書きします。空の列では `--n` がそのまま使われます。

プロンプトを処理した後、各ステップの logits から greedy ID を選び、その ID を `gen` に追加して `gen:` の出力用に保持します。次の forward に入力する token は、まだ強制列が残っていればその要素、残っていなければ greedy ID です。したがって `--force` は表示される `gen:` の ID を直接固定する指定ではなく、後続の forward が読む token 列を固定します。強制列を最後まで読み込んだ位置でも logits と greedy ID を記録します。

総処理位置数はプロンプト長＋`n_gen`−1です。これが `--ctx` を超える場合は `q36ref: ... positions do not fit --ctx ...` を stderr に出し、終了コード 2 で終了します。指定 ID は embedding の token row 読み出しへ渡されます。

`--dump-logits` または `--dump-full-logits` と併用すると、強制入力列に沿って計算した各位置の top-2 または全語彙 logits が、それぞれ指定先へバイナリで書かれます。出力ファイルは `wb` モードで開かれるため、既存ファイルは上書きされます。ファイルを開く処理は `--ctx` の位置数検査より前にあり、context 超過で終了する場合も既存ファイルを切り詰める可能性があります。`fopen` の失敗を示すエラー処理は確認できず、その出力は無効になります。`--force` 単独ではファイルを作成しません。

## 適用条件と副作用

この機能は `strata-q36ref` のみのオプションです。通常の Terminal CLI や推論 engine の `strata` に対する option ではありません。CMake では CUDA または HIP backend が有効な場合に `strata-q36ref` target を定義します。

指定した ID の語彙範囲検査は parser にありません。ID は `embed` から embedding row reader に渡されるため、モデルの有効な token ID のみを使用してください。GPU 上での範囲外 ID の結果はこの調査では実行確認していません。

## 出力とエラー

- 値がない場合: stderr に `q36ref: --force needs a value`、終了コード 2。
- 未知の引数の場合: usage を stderr に出し、終了コード 2。
- 非空の強制列を使い、総位置数が `--ctx` を超える場合:位置数エラーを stderr に出し、終了コード 2。
- 正常終了時: `gen:` に各位置で選択した greedy ID を stdout へ出します。処理時間などの要約は stderr へ出ます。

## 根拠

- `src/qwen35/q36ref.cu:25-31` — usage と `--force` の概要（parser と実際の処理を優先して確認）。
- `src/qwen35/q36ref.cu:708-717` — token ID の分割と `atoi` 変換。
- `src/qwen35/q36ref.cu:722-770` — 引数 parser、値の欠落時の終了、`--force` の読み込みと `n_gen` の上書き。
- `src/qwen35/q36ref.cu:771-800` — 必須値確認、状態初期化、総位置数と `--ctx` 超過時の失敗。
- `src/qwen35/q36ref.cu:802-831` — forward に渡す token、greedy ID の保持、最終出力と終了経路。
- `src/qwen35/q36ref.cu:592-605,608-614` — token ID が embedding row reader へ渡される経路。
- `CMakeLists.txt:333-335,771-775` — GPU backend 条件と `strata-q36ref` target の定義。
