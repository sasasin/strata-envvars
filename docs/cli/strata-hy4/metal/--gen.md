# `strata-hy4-metal --gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（Metal backend、サブコマンドなし） |
| オプション | `--gen` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される生成トークン数 |

## 役割

プロンプトの prefill 後に生成するトークン数の上限を指定する。モデルとトークン ID ファイルを指定する通常のオフライン実行で使う。生成は greedy decode が基本で、条件を満たす場合は DFly2 speculative decode が使われる。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt-ids.txt --gen 32
```

`--model` と `--tokens` は別途必要な入力であり、`--gen` は生成数を追加する指定である。出力先を変える場合は `--out` を併用できる。

## 値と既定値

- 既定値は `0`。値は `atoi` による整数変換で取得され、変換エラーや値域を明示的に検査する処理は parser にない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1492,1504-1513`）。
- 通常デコードの分岐は `gen > 0` の場合だけ実行される。0 以下では通常のトークン生成を行わない（同 `:1944-1952`）。
- 生成ループは最大 `N` 回を上限とするが、EOS トークンが出ると途中で止まる（同 `:1951-1955`）。

## 実行時の動作

- 入力トークンを読み込んで prefill した後、最後の logits の最大値に対応する token ID を最初の生成 token とする greedy 経路がある（同 `:1676-1705,1789-1817,1944-1953`）。
- `--temp`、`--top-p`、`--top-k`、`--min-p` などで sampling が有効な場合、plain decode は分布から token を選ぶ。これらは `--gen` の個数上限そのものは変えない（同 `:1567-1571,1818-1844`）。
- `--draft` の既定値は `auto`。`--gen > 0` で、モデルに DFly2 tensor があり、chunk が16以上、`--all-logits` でなく、画像入力もない場合は speculative 経路を有効にできる。speculative 実行にも `gen` が limit として渡される（同 `:1501,1755-1762,1912,1936`）。
- 通常の生成結果は標準出力に `generated ids: ...` として表示され、`--out` のディレクトリに `gen_ids.txt` として書き出される。出力 ID は空白区切りで、ファイル末尾に改行が付く（同 `:1970-1976`）。`--out` の既定値は `.`（同 `:1489`）。

## 適用条件と副作用

- `--serve` を指定するとサーバーモードへ分岐し、通常の offline prefill/decode 経路およびここで説明した生成結果ファイルの書き出しには進まない（同 `:1635-1675`）。
- `--gen` が0以下でも、通常のオフライン処理ではモデル・入力トークンの読み込みと prefill が行われ、最後に `top5.txt` が `--out` の下へ書かれる（同 `:1676-1715,1789-1817,1978-1980`）。
- speculative decode は、drafter tensor がない、chunk が16未満、または `--all-logits` を使う場合などには選択されない。`--draft dfly2` を要求しても `--gen > 0` でこの条件を満たさない場合、不能の旨を stderr に出し plain 経路を続ける（同 `:1760-1762`）。
- `--out` のディレクトリ作成やファイル書き込み結果の検査は、これらの書き出し箇所では確認できない。既存の同名ファイルは `ofstream` で開かれるため置き換えられる（同 `:1975-1980`）。

## 出力とエラー

- `--model` が空なら usage を stderr に表示して終了コード `2`（同 `:1611-1614`）。
- 読み込んだ token が0件なら `no tokens` を stderr に出して終了コード `2`（同 `:1676-1705`）。
- 通常デコード中の `forward_chunk` 失敗は `forward: ...` を stderr に出して終了コード `1`（同 `:1955-1960`）。DFly2 の `Spec::run` が `finish == "error"` を返した場合は `spec: ...` を stderr に出して終了コード `1`（同 `:1936-1938`）。
- 未知の引数は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード `2`（同 `:1604-1609`）。

## 根拠

- parser、既定値、数値変換: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1513`
- トークン入力・prefill と context の初期化: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1676-1715,1789-1818`
- DFly2 適用条件と生成数の引き渡し: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1912,1936`; 上限・EOS・context 終了は `engine/src/hy4flash/metal/hy4_metal_spec.h:717-745,748-754`
- 通常デコード、出力、エラー: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1980`

