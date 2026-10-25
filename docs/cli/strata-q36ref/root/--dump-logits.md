# `--dump-logits`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（root） |
| オプション | `--dump-logits PATH` |
| 別名 | なし |
| 値 | 出力ファイルのパス。parser による形式・拡張子・範囲検証なし |

## 役割

生成候補の上位2 token の ID と logit を、1 record 4 個の `float` として raw binary で保存します。Qwen3.6 reference executable の近接候補（near-tie）確認用出力です。全語彙の logits を保存する [`--dump-full-logits`](--dump-full-logits.md) とは出力範囲が異なります。【`src/qwen35/q36ref.cu:25-31,811-819`】

## 使い方

```sh
strata-q36ref --model ./model.gguf --tokens 1,2,3 --dump-logits ./q36ref-top2.bin
```

出力先は必要なデータを置いていないパスにしてください。ファイルは `wb` で開かれ、既存ファイルは切り詰められます。【`src/qwen35/q36ref.cu:790-792`】

## 値と既定値

- 値は `--dump-logits` の直後の argv 1 個をパス文字列として受け取ります。値を省略すると `q36ref: --dump-logits needs a value` を stderr に出し、終了コード `2` で終了します。【`src/qwen35/q36ref.cu:725-732,746`】
- 既定値は空文字列です。空文字列を渡した場合も、後段の `empty()` 判定でファイル出力を無効にします。パスの事前検証はありません。【`src/qwen35/q36ref.cu:723,746,791`】
- 同じ option を複数回指定した場合、parser は文字列を都度代入し、処理後に最後の値だけを開きます。【`src/qwen35/q36ref.cu:725-747,791`】

## 実行時の動作

- 指定パスを `fopen(..., "wb")` で開きます。ファイルには header なしで、各 record に `[greedy token ID, greedy token logit, 2位 token ID, 2位 token logit]` の順に `float` 4 個を書きます。各 record はソース上 16 byte です。書込に使う値は、語彙全体から最大値の token と、それを除いた最大値の token を選んだものです。【`src/qwen35/q36ref.cu:790-793,806-819`】
- 出力対象は prompt 全位置ではありません。prompt の最後の token を処理した時点から各生成決定位置で1 record を書き、通常は `n_gen` record になります。`n_gen` の既定値は `64` です。【`src/qwen35/q36ref.cu:723-724,797-818`】
- [`--force`](--force.md) を使うと、与えた continuation token は後続 step の入力に使われますが、`gen` とこの dump に記録する候補は引き続き greedy 判定から得られます。`--dump-full-logits` が併用されていれば、同じ決定位置の全 logits も別ファイルへ書きます。【`src/qwen35/q36ref.cu:767-770,806-819`】

## 適用条件と副作用

- `strata-q36ref` の推論ループで有効です。これは索引で照合用の独立 executable と分類されている Qwen3.6 reference path です。製品 `strata` engine の同名 option とは別スコープです。【`docs/cli/README.md:1487-1497`; `src/qwen35/q36ref.cu:722-747`】
- 出力ファイルは prompt/context の実行条件を確認する前に開かれます。`total > ctx` の場合は終了コード `2` で戻るため、既存ファイルは切り詰められた状態になり得ます。【`src/qwen35/q36ref.cu:790-800`】
- ファイルを開けなかった場合、`fg` は null となり、この dump の書込だけが行われません。open 失敗を知らせる診断や非ゼロ終了はこの処理にはありません。【`src/qwen35/q36ref.cu:791,816-819`】
- `--dump-layers`、`--dump-logits`、`--dump-full-logits` は別々に同時 open されます。同じパスを複数の dump option に指定した場合の整合性は保証されないため、異なる出力先を指定してください。【`src/qwen35/q36ref.cu:790-793`】
- `fwrite` の戻り値は検査されません。書込・close 時の I/O エラーを個別に報告する経路は確認できません。【`src/qwen35/q36ref.cu:815-825`】

## 出力とエラー

- 正常終了後、標準出力には `gen:` に続けて greedy token ID 列が出ます。処理時間等は標準エラーに出ます。top-2 record は標準出力ではなく指定ファイルへ出力されます。【`src/qwen35/q36ref.cu:826-831`】
- `--dump-logits` の値欠落は終了コード `2` です。context に収まらない場合も `q36ref: ... positions do not fit --ctx ...` を stderr に出して `2` で終了します。【`src/qwen35/q36ref.cu:728-731,797-800`】

## 根拠

- `src/qwen35/q36ref.cu:722-765` — option parser、値の取得、usage と未知 option の失敗経路。
- `src/qwen35/q36ref.cu:790-800` — dump file の open、出力 buffer、context 判定。
- `src/qwen35/q36ref.cu:806-831` — greedy top-2 選択、record 書込、close と標準出力・標準エラー。
- `docs/cli/README.md:1487-1497` — `strata-q36ref` の索引 scope と予定リンク。
