# `strata-vision --threads`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（トップレベル、`root/`） |
| オプション | `--threads` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換する値 |

## 役割

CPU で画像を vision tower に通す際の CPU スレッド数を指定する。`strata-vision`、`strata-vision-hip`、`strata-vision-sycl` は同じ parser を使い、GPU を使わない実行では CPU 側の画像エンコードに指定値が使われる。GPU 実行ではこの値はエンコードに使われない。

## 使い方

```sh
strata-vision --mmproj vision-projection.gguf --threads 4
```

`--mmproj` には vision encoder と projector を含む GGUF ファイルを指定する。`--threads` を省略した場合、CPU 実行では利用可能なハードウェアスレッド数の半分を基準に、1〜16 の範囲で選ばれる。

## 値と既定値

- parser は次の引数を `std::atoi` で整数に変換して保存する。独自の数値形式・範囲検証は行わず、同じオプションを複数回指定したときは後の値が残る（`terminal/tools/vision/strata_vision.cpp:61-65,87`）。
- 値が欠けていると `--threads needs a value` を標準エラーに出して終了コード 2 で終了する（`terminal/tools/vision/strata_vision.cpp:63-65`）。
- 値が 0 以下の場合、CPU reader はハードウェアスレッド数の半分を 1〜16 に収めた値へ置き換える。明示値が正の場合は、そのまま CPU encoder に渡す（`terminal/tools/vision/own/own_reader.h:14-20`、`terminal/tools/vision/own/own_reader.cpp:60-62,80-94`）。
- parser 自体に正の値の上限検査はない。極端に大きい値を指定した場合の実行可能性は、CPU のスレッド生成など実行環境に依存し、ソースから一律には確定できない。

## 実行時の動作

CPU reader は初回エンコード時に指定数で `Team` を作成し、既存の team のスレッド数が異なれば作り直す。`Team(n)` は呼び出し元スレッドに加えて最大 `n-1` 個の worker を生成し、CPU tower の処理タスクを並列実行する（`terminal/tools/vision/own/vit_cpu.cpp:194-203`、`terminal/tools/vision/own/cpu_team.h:31-35,49-67`）。参照実装 `STRATA_VIT_CPU=ref` を選んだ場合も同じスレッド数が `VitRef::encode` に渡される（`terminal/tools/vision/own/own_reader.cpp:80-100`、`terminal/tools/vision/own/vit_ref.cpp:217-224`）。

サーバーの vision 設定に `threads` があれば `terminal/serve/server.py` が reader 起動引数へ渡す。値が未指定の場合、サーバーはエンジン設定で明示された正の `--pool-workers` / `--threads` または `threads` を vision 設定へ引き継ぐことがある（`terminal/serve/server.py:3017-3029,8891-8899`）。

`--gpu` と併用して GPU reader を動かす場合、GPU の `encode` 呼び出しに `threads` は渡らず、この指定は画像エンコードのスレッド数を変えない（`terminal/tools/vision/own/own_reader.cpp:95-100,102-117`）。

## 適用条件と副作用

この値がスレッド数を制御するのは CPU エンコード経路である。CPU tower は設定された数に応じて worker を生成し、その team を reader の実行中に再利用する（`terminal/tools/vision/own/vit_cpu.cpp:201-202`、`terminal/tools/vision/own/cpu_team.h:31-35,87-109`）。`--threads` によるファイル・ネットワーク操作は確認できない。

## 出力とエラー

CPU reader は起動時に、実際に採用したスレッド数を含む `strata-vision: own tower ... on the CPU, N threads` の行を標準エラーへ出す（`terminal/tools/vision/own/own_reader.cpp:91-94`）。スレッド数自体を範囲外として拒否する CLI エラー経路は parser にはない（`terminal/tools/vision/strata_vision.cpp:61-95`）。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:36-36,61-95` — 共通 parser、`--threads` の値取得、必須値・未知引数・`--mmproj` 欠落時の終了経路。
- `terminal/tools/vision/own/own_reader.h:14-20`、`terminal/tools/vision/own/own_reader.cpp:60-100` — 値の保持、CPU 側既定値の決定、GPU/CPU encoder への分岐。
- `terminal/tools/vision/own/vit_cpu.cpp:194-203`、`terminal/tools/vision/own/cpu_team.h:31-35,49-67` — CPU tower の team 作成と並列タスク実行。
- `terminal/tools/vision/own/vit_ref.cpp:217-224` — 参照 CPU 実装にもスレッド数が渡ること。
- `terminal/serve/server.py:3017-3029,8891-8899` — server 設定から reader 引数への値の転送と、エンジン側の明示的 CPU thread cap の引き継ぎ。
