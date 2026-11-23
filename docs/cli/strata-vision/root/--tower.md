# `strata-vision --tower`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--tower` |
| 別名 | なし |
| 値 | 必須。`mtmd`、`own`、`auto` のいずれか |

## 役割

旧来の呼び出し元との互換性のために値を受け取るオプションです。現行の `strata-vision` は Strata 独自の own vision tower だけを使い、値による tower の切り替えはしません。`own` と `auto` は警告なしで受理され、`mtmd` も警告を出したうえで同じ own reader を実行します（`terminal/tools/vision/strata_vision.cpp:3-8,56-60,70-74,140`）。

## 使い方

```sh
# 現行 reader を起動する（明示値 own）
strata-vision --mmproj mmproj.gguf --tower own

# 旧設定に残る値も受理されるが、mtmd reader には切り替わらない
strata-vision --mmproj mmproj.gguf --tower mtmd
```

`--mmproj` は reader の起動に必要です。サーバーは `--mmproj` と `--model` などを組み立てますが、現在の引数組み立てでは `--tower` を追加しません（`terminal/serve/server.py:3016-3029`）。

## 値と既定値

- 値は別引数で指定します。受理される文字列は大文字小文字を区別する `mtmd`、`own`、`auto` です（`terminal/tools/vision/strata_vision.cpp:70-74`）。
- 省略時は `--tower` の処理自体がなく、後段の `own_reader_run` に進むため own reader が使われます（`terminal/tools/vision/strata_vision.cpp:61-74,140`）。
- 値なしの場合は stderr に `--tower needs a value` を出して終了コード 2 で終了します。未対応値では stderr に `--tower takes own or auto` を出して終了コード 2 です（`terminal/tools/vision/strata_vision.cpp:63-65,70-74`）。
- `--tower=own` のような等号形式は parser に定義されておらず、未知の引数として終了コード 2 になります（`terminal/tools/vision/strata_vision.cpp:61-65,70-74,91`）。
- 同じオプションを複数回指定した場合、各値が順に検証されます。各回とも reader 選択状態は保存されず、`mtmd` が含まれればその回ごとに警告します（`terminal/tools/vision/strata_vision.cpp:61-74`）。

## 実行時の動作

`own` と `auto` は値の検証後に何も変更せず、`mtmd` は stderr に `strata-vision: --tower mtmd is no longer read; Strata's picture reader runs` と出力します。どの受理値でも最終的に `strata_vit::own_reader_run(o)` が呼ばれ、mtmd 実装への分岐はありません（`terminal/tools/vision/strata_vision.cpp:70-74,140`）。

サーバーもこのオプションを通常は渡しません。さらに、旧環境変数 `STRATA_VISION_TOWER` は `own` と `auto` 以外の非空値で互換性警告を出すだけで、選択には使われません（`terminal/tools/vision/strata_vision.cpp:57-60`）。サーバーが `--model` を渡しても、現行 reader では値を読み捨てます（`terminal/tools/vision/strata_vision.cpp:67-69`）。

## 適用条件と副作用

この parser は `strata-vision` の入口にあり、ビルド条件に応じて同じ実行ファイルが `strata-vision-hip` または `strata-vision-sycl` という名前になります（`terminal/tools/vision/CMakeLists.txt:77-98`）。`--tower` 自体は GPU backend や platform による分岐を行いません。

`mtmd` を指定したときだけ、標準エラーに互換性の警告を出します。値は状態に保持されず、ファイルや GPU の処理を直接変更しません。実際の reader は `--gpu` や build/backend 条件など、別の設定に従います（`terminal/tools/vision/strata_vision.cpp:69-74,97-125,140`）。

## 出力とエラー

有効値 `mtmd` は警告を stderr に出しますが、引き続き own reader の初期化へ進みます。`own` と `auto` はこのオプション由来の出力を出しません。値なし・無効値・未知の引数は stderr と終了コード 2 で失敗します（`terminal/tools/vision/strata_vision.cpp:63-65,70-74,91`）。その後の mmproj 読み込みなど reader 初期化時の失敗は、このオプションの値ではなく `own_reader_run` 側で処理されます（`terminal/tools/vision/own/own_reader.cpp:42-59`）。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:3-8` — 現行プログラムが own tower を使い、`--tower` を互換用に受理すること。
- `terminal/tools/vision/strata_vision.cpp:56-74` — 旧環境変数の扱い、引数値の取得・許容値・`mtmd` 警告。
- `terminal/tools/vision/strata_vision.cpp:91-95,140` — 未知引数と必須 `--mmproj` の失敗経路、および最終的な own reader 呼び出し。
- `terminal/tools/vision/own/own_reader.cpp:42-59` — parser 後に呼ばれる reader 初期化とその失敗出力。
- `terminal/tools/vision/CMakeLists.txt:77-98` — CPU 名の `strata-vision` と HIP/SYCL バリアントが同じ parser 実装を使うこと。
- `terminal/serve/server.py:3016-3029` — サーバーが組み立てる reader 引数に `--tower` が含まれないこと。
