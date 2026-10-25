# `--greedy`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family 経路、または `strata-q36` |
| オプション | `--greedy` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Qwen3.6 専用 parser は `--greedy` を受理します。ただしこの parser ではフラグの処理が空で、生成設定を変更しません。単発の `--tokens` 生成はそもそも argmax で行われるため、このモードでは `--greedy` の有無で選択方式は変わりません。索引上は通常の engine parser と意味が異なる可能性を考慮して `qwen36/` scope に分けられています。

## 使い方

```sh
strata --model ./qwen3.6.gguf --tokens 1,2,3 --n 16 --greedy
```

`--model` が Qwen3.6 family と判定されると、`strata` は全引数を Qwen3.6 runner に渡します。`strata-q36` は同じ runner を直接呼び出す executable です。実際の model path と prompt token ID は環境に合わせてください。

## 値と既定値

- `--greedy` は値なしで指定します。引数 parser に専用の値変換・範囲検査はありません。複数回指定しても毎回空の処理を通るだけです。
- Qwen3.6 の単発生成で argmax を選ぶのは `--greedy` の設定によるものではありません。生成ループが `E.greedy()` を呼ぶ実装です。
- Qwen3.6 の `--serve` 経路では、sampling の初期値は `temperature=0`（greedy）です。serve protocol の各 `GEN` / `BGEN` request に `temperature` などの key/value を渡すと request の sampling 設定が変わります。起動時の `--greedy` はその設定を固定しません。

## 実行時の動作

ネイティブ `strata` は `--model` または `--native` のモデルヘッダーを読み、family が `Qwen35Moe` の場合に Qwen3.6 runner へ分岐します。そこで `--greedy` は認識されますが、ソースコメントにも `--tokens` はここでは常に greedy decode と記され、実装は空です。単発生成では prompt を処理した後 `E.greedy()` で次 token を選び、指定回数分の token ID を `gen:` 行として stdout に出します。

serve mode は別経路です。request parser は `temperature`、`top_p`、`top_k`、`min_p`、penalty 群、`seed` を protocol の key/value から読み、temperature が 0 以下なら argmax、正なら sampling を行います。従って serve を使う場合、生成方式は request の key/value が決め、CLI の `--greedy` はそれを上書きしません。

## 適用条件と副作用

- Family switch は `STRATA_HAVE_QWEN35` が有効な build でコンパイルされる分岐です。別 executable `strata-q36` も同じ Qwen runner を直接呼びます。Release での配布有無はこの調査では確認していません。
- フラグ自体はファイル、環境変数、ネットワーク、GPU 状態を変更しません。Qwen3.6 runner の起動・生成が伴う場合のモデル読み込みや GPU 利用は通常の runner の動作です。
- `--model` を省略すると runner はエラーで終了します。非-serve 経路で未知の引数を渡すと usage を stderr に出して status 2 を返します。serve mode では、未知の `--...` 引数は警告して無視する実装です。
- `--greedy` 自体による出力行、警告、失敗経路はありません。通常生成では `gen:` が stdout、生成計時情報が stderr に出ます。

## 出力とエラー

- `strata-q36: --model is required` を stderr に出し、status 2 で終了します（モデル指定がない場合）。
- prompt token が空で、serve / benchmark でもない場合は `strata-q36: --tokens, --serve or --bench-pp is required` を stderr に出して status 2 で終了します。
- 有効な通常生成では token ID を `gen: ...` として stdout に出します。`--greedy` の有無による出力差は parser / 生成経路に実装されていません。

## 根拠

- 索引の掲載位置と Qwen3.6 scope: `docs/cli/README.md:1318-1337`（strata-envvars）。
- Qwen family の検出と runner への引き渡し: `src/program/generate.cpp:2393-2408`。
- standalone executable の入口と build target: `src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:790-792`。
- parser 宣言、値なし受理、serve 時の未知 option 処理、一般エラー、必須 model validation: `src/qwen35/q36_engine.cu:3735-3797`。
- Serve request の sampling 初期値・protocol key/value の読取: `src/qwen35/q36_engine.cu:3012-3016`、`src/qwen35/q36_engine.cu:3452-3485`。temperature による argmax / sampling 分岐: `src/qwen35/q36_engine.cu:3030-3055`。
- 通常生成の argmax 経路、prompt 不足エラー、`gen:` 出力: `src/qwen35/q36_engine.cu:3916-3975`。

調査は指定 revision のソースと索引を対象にし、CLI help の実行、build、GPU 実行、性能測定、テストは行っていません。Release artifact ごとの挙動や Qwen3.6 の serve protocol を起動する外部 caller の設定内容は、この調査範囲では確認していません。
