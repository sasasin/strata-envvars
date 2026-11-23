# `--native`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（ルート） |
| オプション | `--native` |
| 別名 | `--model` |
| 値 | モデルファイルのパスを1つ取る。使用例とエラー文は `.strata` ファイルを前提としている。 |

## 役割

`--native` は Hy4-Flash SYCL 実行ファイルに読み込ませるモデルファイルを指定する。値は `--model` と共通の `model` 変数に入り、通常のトークン入力モードでは `SyModel::load` と expert 初期化に、`--serve` モードではサーバー設定を経て同じロード・expert 初期化経路に渡される。相対パスの基準ディレクトリを変更する処理はこのオプションにはなく、コード上は指定文字列をそのままロード関数へ渡す。

## 使い方

```sh
# 通常モード: モデル、Engram、入力 token ID ファイルを指定する
strata-hy4-sycl --native ./model.strata --engram ./engram.strata --tokens ./ids.txt

# engine line protocol のサーバーモード
strata-hy4-sycl --serve --native ./model.strata --engram ./engram.strata

# 同じモデル指定の別名
strata-hy4-sycl --model ./model.strata --engram ./engram.strata --tokens ./ids.txt
```

## 値と既定値

- 値を1つ取る。`--native` と `--model` は同じ分岐で処理され、どちらを使っても `model` 文字列を設定する。既定値は空で、どちらも指定しない場合にモデルは選ばれない（`engine/src/hy4flash/sycl/sy_main.cpp:93,130`）。
- 数値形式や拡張子の parser 検証はない。値は文字列として受け取られ、通常モードでは `SyModel::load` に渡される。実際に開けるファイル・形式かどうかはロード段階で決まる（`engine/src/hy4flash/sycl/sy_main.cpp:130,260-264`、`engine/src/hy4flash/sycl/sy_model.h:67-72`）。
- 値を省略してオプションが末尾にある場合、`nxt()` が `ERR --native needs a value` を標準出力へ出し、終了コード `2` で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 同じオプションまたは別名を複数回指定した場合、parser は各値で同じ変数を代入するため、最後に指定した値が残る（`engine/src/hy4flash/sycl/sy_main.cpp:107-130`）。
- 明示的な空文字列は `model.empty()` と判定され、モードに応じて必須値なしとして扱われる（`engine/src/hy4flash/sycl/sy_main.cpp:215-220,250-254`）。

## 実行時の動作

- 通常モードでは、`model` を `SyModel::load(model, err)` に渡す。ロード関数は `StrataFileReader::open` でファイルを開き、マニフェスト等を読み込む。その後も expert 配置と GPU expert 初期化に同じモデルパスを渡す（`engine/src/hy4flash/sycl/sy_main.cpp:255-264,298-307,323-328`、`engine/src/hy4flash/sycl/sy_model.h:67-73`）。
- `--serve` を指定した場合は、`model` を `ServeOpts::model` に格納して `hy4s_serve_main` へ渡す。serve 側でもモデル本体と expert 設定に使用される（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:28-30,236-246,280-285,289-294`）。
- `--serve` は引数走査前に全引数から検出されるため、`--native` との並び順でモード選択は変わらない（`engine/src/hy4flash/sycl/sy_main.cpp:105-107`）。
- パスの存在確認や値の正規化を parser で行う処理はない。ロードと expert 初期化はモデルファイルを参照するが、このオプション自体によるファイル書き換えは確認できない。

## 適用条件と副作用

- 対象は `strata-hy4-sycl` のルート CLI。CUDA/HIP 版と Metal 版は別の入口・スコープであり、この文書の説明対象外（索引 [`docs/cli/README.md`](../../README.md) の `strata-hy4` 節）。
- 通常モードではモデルのほかに token ファイルが必要であり、`--native` 単独では推論入力を与えない。`--load-only` では token 読み込みを省けるが、モデルは引き続きロードされる（`engine/src/hy4flash/sycl/sy_main.cpp:260-274`）。
- `--serve` ではモデル指定が必須。値がない場合は `ERR --native FILE.strata is required` を標準出力に出し、終了コード `2` で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:215-220`）。

## 出力とエラー

- `--serve` でモデルを開けない場合、serve のプロトコル出力に `ERR cannot load <path>: <理由>` を出し、終了コード `1` を返す（`engine/src/hy4flash/sycl/sy_serve.h:241-247`）。
- 通常モードでロードできない場合、標準エラーに `load: <理由>` を出し、終了コード `1` を返す（`engine/src/hy4flash/sycl/sy_main.cpp:260-264`）。
- 通常モードでモデル未指定の場合は usage を標準エラーに出し、終了コード `2` を返す（`engine/src/hy4flash/sycl/sy_main.cpp:250-254`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-115,129-130` — モデル変数の初期値、値取得関数、`--native` / `--model` の同一 parser 分岐。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — serve モードの必須判定、設定への格納と serve 呼び出し。
- `engine/src/hy4flash/sycl/sy_main.cpp:250-264,298-307,323-328` — 通常モードの必須判定、モデルロード、expert 初期化での利用。
- `engine/src/hy4flash/sycl/sy_model.h:67-73` — モデルパスを保持して `StrataFileReader::open` と manifest 読み込みを行う処理。
- `engine/src/hy4flash/sycl/sy_serve.h:236-247,280-294` — serve 側でのモデルロードと expert 初期化、ロード失敗応答。
