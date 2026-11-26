# `--model`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--model` |
| 別名 | `--native` |
| 値 | GGUF モデルファイルのパス。parser による形式・存在確認や既定値はない |

## 役割

Qwen3.6 エンジンが読み込むモデルファイルを指定する。`strata` は `--model` または `--native` で指定された GGUF の family を見て、`qwen35moe` の場合に Qwen3.6 専用実装へ処理を渡す。`strata-q36` ではこの専用 parser が直接処理する。

## 使い方

```bash
strata --model /models/Qwen3.6.gguf --serve
```

`--tokens` を使う実行では、たとえば `strata --model /models/Qwen3.6.gguf --tokens 1,2,3 --n 64` のように指定する。Qwen3.6 parser の usage は `--model GGUF` を必須引数として示し、実行モードは `--serve`、`--tokens`、または `--bench-pp` と `--bench-tg` の組み合わせを案内している。

## 値と既定値

- `--model` の直後の argv 要素をパス文字列として受け取る。parser はファイル拡張子・存在・空でないことをその場では検証しない。
- 既定値はない。`--model` と `--native` は同じ `model` 変数を設定するため、どちらかが必要。
- 同じオプションを複数回指定した場合、parser は出現ごとに同じ変数へ代入するため最後の値が残る。
- 値を省略すると parser の `next()` が stderr に `strata-q36: --model needs a value` を出して終了コード 2 で終了する。値が空文字列の場合は必須チェックで終了コード 2 になる。

## 実行時の動作

`strata` の入口は `--model` / `--native` の次の引数から GGUF の shard path を解決してヘッダーを調べ、family が `Qwen35Moe`（GGUF architecture `qwen35moe`）なら、元の argv 全体を Qwen3.6 parser に渡す。Qwen3.6 parser は指定値を `model` に格納し、`load(model, ...)` に渡して `GgufModel::open` でファイルを開く。

ロード時には GGUF の geometry と tensor layout を検証し、family が `Qwen35Moe` であること、およびこの driver が扱う geometry 条件（head dimension 256、SSM state size 128、convolution 4、expert 数 512 以下、top-k 15 以下）を満たすことを確認する。これらの条件は `--model` の値検証ではなく、指定ファイルをロードする処理の条件である。

## 適用条件と副作用

- `strata` の Qwen3.6 専用経路へ入るのは、先頭の `--model` / `--native` で指定されたファイルの header から Qwen3.6 family を識別できた場合。読み取りに失敗したときは family switch では例外を捕捉して通常経路へ進み、通常経路側のエラー処理に委ねる。
- 指定ファイルは Qwen3.6 専用実装が受け付ける GGUF である必要がある。別 family、壊れた layout、非対応 geometry はロード時に拒否される。
- このオプション自体がファイルを書き換える処理は確認できない。値はロード対象の選択に使われる。

## 出力とエラー

- `--model` の値がなく `next()` が呼ばれると、stderr に `strata-q36: --model needs a value` を出して終了コード 2。
- `model` が空のままなら stderr に `strata-q36: --model is required` を出して終了コード 2。
- `load()` が検証エラーを返す場合はその説明を stderr に出して終了コード 1。ロード中の `std::exception` も例外メッセージを stderr に出して終了コード 1。
- ファイルが開けない場合の具体的なエラーメッセージは `GgufModel::open` 側に依存するため、本調査では固定文言を特定していない。

## 根拠

- `engine/src/program/generate.cpp:3804-3818` — `strata` が `--model` / `--native` の値から GGUF family を判定し、Qwen3.6 parser へ argv を渡す経路。
- `engine/src/qwen35/q36_engine.cu:5339-5355` — parser の変数と既定状態、および `--model` / `--native` の値取得。
- `engine/src/qwen35/q36_engine.cu:5419-5420` — 未指定時の必須チェック。
- `engine/src/qwen35/q36_engine.cu:5413-5417` — usage と必須値の表記。
- `engine/src/qwen35/q36_engine.cu:1387-1402` — GGUF を開き、family・layout・geometry を検証するロード処理。
- `engine/src/qwen35/q36_engine.cu:5458-5464` — `load()` 呼び出し、検証失敗と例外の stderr / 終了コード。

調査範囲は上記 revision の Strata 所有ソース。CLI の help 実行や build は行っていない。
