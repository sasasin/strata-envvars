# `strata-vision --model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（`strata-vision-hip` / `strata-vision-sycl` も同じ parser） |
| オプション | `--model` |
| 別名 | なし |
| 値 | 必須の引数を1つ消費する。内容・パス形式の検証はない |

## 役割

`--model` は旧 reader や server の起動引数との互換性のために受理されるテキストモデル指定です。現行 `strata-vision` の own reader はテキストモデルを使わず、値は parser で読み捨てられます。画像 encoder の読み込みに使われるのは `--mmproj` で渡す vision encoder / projector ファイルです（`terminal/tools/vision/strata_vision.cpp:67-69,140`、`terminal/tools/vision/own/own_reader.cpp:80-90`）。

## 使い方

```sh
# server / 旧 run config と同様にテキストモデルの値を併記する例。
# reader は --model の値を参照せず、mmproj を使って常駐起動する。
strata-vision --mmproj ./vision-mmproj.gguf --model ./text-model.gguf
```

通常、vision reader にテキストモデルのパスを渡す必要はありません。`--model` を指定する場合は値を1つ付けます。

## 値と既定値

- 値を取るオプションです。parser は次の argv 要素をそのまま消費し、値を保存・検証しません。拡張子、ファイルの存在、モデル形式は確認されず、未指定時に代わりの値を設定する処理もありません（`terminal/tools/vision/strata_vision.cpp:63-69`）。
- 1つの `--model` ごとに値が必要です。値が続かない場合は `<option> needs a value` を標準エラーへ出して終了コード `2` で終了します（同 `:63-65`）。
- 複数回指定しても、各値を順に消費して捨てます。値は後続処理に影響しません（同 `:61-69`）。

## 実行時の動作

`strata-vision` は `--model` の値を保持せず、画像処理の起動関数 `strata_vit::own_reader_run(o)` に渡す設定 `o` にも格納しません（`terminal/tools/vision/strata_vision.cpp:56,67-69,140`）。reader 本体は `o.mmproj` から vision encoder を読み込み、CPU または GPU の経路を初期化します（`terminal/tools/vision/own/own_reader.cpp:80-94`）。したがって、テキストモデルのロード・選択・妥当性確認は `--model` の効果ではありません。

一方、server の `Vision.reader_args` は設定された `cfg["model"]` を `--model` の値として起動引数に含めます（`terminal/serve/server.py:3016-3023`）。現行 reader がその値を無視するため、これは server からの互換的な引き渡しです。実際の vision reader の入力は同じ引数列の `--mmproj` です。

## 適用条件と副作用

- 通常版・HIP 版・SYCL 版は同じ `strata_vision.cpp` の parser から構成されます。ビルド設定により実行ファイル名が変わります（`terminal/tools/vision/CMakeLists.txt:77-97`）。
- `--model` 単独ではファイル読み込み、ネットワークアクセス、プロセス起動、GPU 初期化などの副作用はありません。後続の vision reader 初期化や画像エンコードの副作用は `--mmproj` 等によるもので、このオプションの値では変わりません（`terminal/tools/vision/strata_vision.cpp:67-69,97-107,140`）。
- `--mmproj` が空または指定されていない場合は、この値の有無にかかわらず usage を標準エラーへ出して終了コード `2` になります（同 `:93-96`）。未知の引数も標準エラーに `unknown argument ...` を出し、終了コード `2` です（同 `:91-92`）。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:63-69` — 値の消費処理と `--model` を捨てる parser 分岐。
- `terminal/tools/vision/strata_vision.cpp:91-96,140` — 未知引数・必須 `--mmproj` の失敗経路と、設定を reader に渡す箇所。
- `terminal/tools/vision/own/own_reader.cpp:80-94` — encoder を `o.mmproj` から読み込み、常駐 reader を初期化する箇所。
- `terminal/serve/server.py:3016-3027` — server が `cfg["model"]` を `--model` に渡す箇所。
- `terminal/tools/vision/CMakeLists.txt:77-97` — 同一 parser を使う vision executable と HIP / SYCL 名の設定。
