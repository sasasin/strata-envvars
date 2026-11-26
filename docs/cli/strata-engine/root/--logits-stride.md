# `strata --logits-stride`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--logits-stride` |
| 別名 | なし |
| 値 | 正の 10 進 `int64`（符号、空白、接尾辞なし） |

## 役割

`--dump-logits` が保存する logits 行を間引きます。各入力位置の条件付けは維持したまま、0 始まりの位置番号が stride の倍数となる行と最後の入力位置の行を保存対象にします。既定値 `1` は全行を選びます。間引きは保存行の選択だけを変え、推論や生成の入力を間引くものではありません（`engine/include/strata/program/logits_selection.hpp:9-27`）。

## 使い方

```sh
# 一時ディレクトリに logits を保存。stride 4 の倍数位置と末尾位置を記録する
out=$(mktemp -d)
./strata --tokens 1,2,3,4,5 --max-new 1 \
  --dump-logits "$out/logits.bin" --logits-stride 4
```

`--logits-stride` が `1` の場合は省略できます。stride を `1` より大きくする場合は `--dump-logits` と `--max-new 1` の両方が必要です（`engine/src/program/generate.cpp:5201-5204`）。

## 値と既定値

- 既定値は `1` です（`engine/src/program/generate.cpp:766-767`）。
- 値は正の 10 進 `int64` 全体として解析されます。`0`、負数、先頭の `+`、空文字、空白、接尾辞、`int64` の範囲外は拒否されます（`engine/include/strata/program/logits_selection.hpp:11-17`）。
- 同じ引数列で複数回指定すると拒否されます。値を省略した場合も引数解析の `next` が stderr に不足を表示して終了コード `2` で終了します（`engine/src/program/generate.cpp:3840-3846,3887-3892`）。
- 不正値では `--logits-stride requires a positive decimal int64`、重複指定では `--logits-stride must be supplied only once` を stderr に出し、終了コード `2` を返します（`engine/src/program/generate.cpp:3887-3892`）。

## 実行時の動作

`--dump-logits` の出力対象位置数は `tokens.size() - 1 + max_new` です。保存するのはその範囲内の 0 始まり位置 `pos` のうち、`pos % stride == 0` または `pos == total - 1` を満たす位置です。末尾位置が倍数でも重複して数えません。保存行数は共通 helper の `row_count` で同じ規則から算出します（`engine/src/program/generate.cpp:10657-10676`; `engine/include/strata/program/logits_selection.hpp:20-27`）。

stride が `1` より大きく、`--max-new` が `1` でないか `--dump-logits` が未指定なら、stderr に `strata generate: --logits-stride > 1 requires --max-new 1 and --dump-logits` を出し、終了コード `2` で終了します。stride が `1` なら、この条件検査はありません（`engine/src/program/generate.cpp:5201-5204`）。

dump ファイルは `fopen(..., "wb")` で開かれるため、指定先に既存ファイルがあれば切り詰めます。先頭に `int32` 2 要素（語彙数、保存行数）のヘッダーを書き、続けて各行の `float` logits を書きます。ヘッダーは最初の保存行と同時に書かれ、保存行が一度もなければ空ファイルになります（`engine/src/program/generate.cpp:10652-10676,24358-24382`）。

この option は通常の parser (`engine/src/program/generate.cpp`) と SYCL parser (`engine/sycl/src/program/generate.cpp`) の両方にあり、選択 helper を共有します。SYCL 側にも同じ重複・値検査、相互作用条件、行数計算、選択、ファイル書き込みがあります（`engine/sycl/src/program/generate.cpp:1881-1888,1925-1932,2615-2618,6087-6112,13585-13619`）。

## 適用条件と副作用

- `--logits-stride > 1` は `--max-new 1` と `--dump-logits` を必要とします。`--logits-stride 1` は `--dump-logits` がなければ保存処理を有効にしません。
- 間引き位置の logits を保存するため、その位置では GPU からホストへの logits 読み戻しと同期が行われます（`engine/src/program/generate.cpp:24358-24365`）。
- 出力ファイルはバイナリ書き込み用に作成または切り詰められます。ファイルを開けない場合は `strata generate: cannot write <path>` を stderr に出して終了コード `1` です（`engine/src/program/generate.cpp:10658-10666`）。
- dump 寸法が `int32` に収まらない場合は stderr に `strata generate: logits dump dimensions exceed int32` を出し、終了コード `2` です。ヘッダーまたは行の書き込み失敗、および終了時の `fclose` 失敗は stderr に診断を出して終了コード `1` になります（`engine/src/program/generate.cpp:10658-10666,24375-24382,25379-25381`）。

## 根拠

- parser・重複指定・値検査: `engine/src/program/generate.cpp:3840-3846,3886-3892`、SYCL 対応 parser: `engine/sycl/src/program/generate.cpp:1881-1888,1925-1932`。
- 値の厳密な解析と位置選択: `engine/include/strata/program/logits_selection.hpp:11-27`。
- stride と `--max-new` / `--dump-logits` の検証: `engine/src/program/generate.cpp:5201-5204`、SYCL: `engine/sycl/src/program/generate.cpp:2615-2618`。
- 出力範囲・行数・ファイル形式・書き込み: `engine/src/program/generate.cpp:10652-10676,24358-24382`、SYCL: `engine/sycl/src/program/generate.cpp:6087-6112,13585-13619`。
- Strata checkout の調査時状態は `main...origin/main` で、未コミット変更はありません。索引 `docs/cli/README.md:1113` はこの文書を `strata-engine` root の option として掲載しています。
