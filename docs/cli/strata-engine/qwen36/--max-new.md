# `--max-new`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 実装（または `strata-q36`） |
| オプション | `--max-new` |
| 別名 | なし。`--n` は別の表記で同じ生成数変数を設定する |
| 値 | 整数として `std::atoi` で変換 |

## 役割

Qwen3.6 の単発トークン生成モードで、出力するトークン数の上限を指定します。モデルが GGUF の `qwen35moe` family なら、`strata` は引数一式を Qwen3.6 実装に渡します。CMake の該当 build では同じ実装を `strata-q36` としても生成します（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:790-794`）。

## 使い方

```sh
strata --model ./qwen36.gguf --tokens 1,2,3 --max-new 32
```

`--tokens` には prompt の token ID をカンマ区切りで渡します。単体実行ファイルを使う場合も `strata-q36 --model ./qwen36.gguf --tokens 1,2,3 --max-new 32` と指定できます。Qwen3.6 parser は `--model` / `--native`、`--tokens`、`--max-new` を処理します（`src/qwen35/q36_engine.cu:3742-3761`）。

## 値と既定値

- 省略時は `64` トークンです（`src/qwen35/q36_engine.cu:3735-3738`）。
- 値は `std::atoi` で整数化され、parser 自体は正数・数値形式の検証をしません（`src/qwen35/q36_engine.cu:3744-3750`）。末尾に値がなければ `strata-q36: --max-new needs a value` を stderr に出して終了コード `2` で終了します（同 `:3744-3746`）。
- 数値に変換できない文字列は `atoi` の結果 `0` となり、数値以外を含む文字列も数値部分だけが変換対象です。単発生成では `0` 以下の場合に生成ループが実行されません。MTP の単発経路ではループ後に `gen.resize((size_t) n_gen)` を行うため、負数は巨大な size への変換となり、割り当て失敗等の異常終了につながり得ます（同 `:3940-3950`）。
- `--n` も同じ `n_gen` を設定します。両方を指定した場合は引数列で後に現れた方が残ります（同 `:3750-3760`）。

## 実行時の動作

通常の `--tokens` モードでは、`n_gen` 回のループで greedy token を追加し、`gen: <token id> ...` を stdout に出します。`--max-new` が生成ループの回数を決めます。MTP が有効で、`--force` と `--dump-full-logits` がない場合は speculative 経路に入り、同じ `n_gen` を上限として候補 token を追加します（`src/qwen35/q36_engine.cu:3935-3958`、`3960-3974`）。このモードのループには EOS による早期終了判定がなく、指定数までの token ID を出力します。

`--force IDS` により強制 token 列が空でない場合、parser で設定した `--max-new` / `--n` は後から `forced.size() + 1` に置き換わります。したがって、この組み合わせでは `--max-new` の値は生成数を決めません（`src/qwen35/q36_engine.cu:3760`、`3916-3918`、`3960-3969`）。

`--serve` モードでは起動時の `n_gen` は使われません。各 `GEN` / `GENI` 要求が独自に `<max_new>` を渡し、serve 実装がその値を検証し、生成上限として使います。要求値が `1` 未満、または prompt token 数との合計が engine context を超える場合は要求を拒否します。serve の通常要求は `T` 行と `DONE` 行、batch 要求は `BT` / `BDONE` 行で結果を返します（同 `:3431-3452`、`:3494-3508`、`:3630-3638`、`:3284-3299`）。

`--bench-pp` / `--bench-tg` の benchmark 分岐は `n_gen` を参照せず、`--bench-tg` の回数を使います（同 `:3889-3914`）。

## 適用条件と副作用

- `strata` での適用条件は、`--model` または `--native` が指す GGUF の architecture が `qwen35moe` であり、Qwen3.6 実装を含む build であることです。それ以外は通常 engine parser に進みます（`src/program/generate.cpp:2393-2407`）。
- `--tokens` の単発生成数に対する明示的な正数チェックや、prompt + `--max-new` が `--max-context` に収まるかの事前検査は、Qwen3.6 parser のこの経路では確認できません。`--max-context` の既定値は `32768` で、engine はその値を `E.init` に渡します（`src/qwen35/q36_engine.cu:3737`、`:3807-3809`、`:3863`）。
- `--max-new` 自体はファイルや環境変数を書き換えません。生成された token ID を stdout に出し、所要時間等を stderr に報告します（同 `:3951-3957`、`:3972-3977`）。

## 出力とエラー

- 成功時、token ID 列は `gen:` を先頭に stdout へ出力し、生成数と所要時間等は stderr に出力します（`src/qwen35/q36_engine.cu:3951-3957`、`:3972-3977`）。
- 値の欠落は前述の通り終了コード `2` です。`--model` の欠落も終了コード `2` でエラーになります（同 `:3744-3746`、`:3797`）。
- `--serve` の要求単位では、`max_new < 1` は stdout の `ERR bad request: max_new or the ids` で拒否され、context 超過は `ERR prompt ... exceeds the context ...` で拒否されます。これらは要求エラーであり、起動時 `--max-new` の validation ではありません（同 `:3494-3508`）。

## 根拠

- parser、既定値、変換と同一変数の `--n`: `src/qwen35/q36_engine.cu:3735-3760`
- 単発生成数の上書き、MTP / 通常生成、標準出力と統計: `src/qwen35/q36_engine.cu:3916-3977`
- serve の要求単位上限、validation、生成停止条件: `src/qwen35/q36_engine.cu:3431-3508`、`:3625-3638`
- `strata` から family 固有実装への振り分け: `src/program/generate.cpp:2393-2407`
- 独立 executable の entry point と build target: `src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:790-794`

調査範囲は上記 commit のソースです。同一 revision の既存バイナリによる `--help` や Release 配布物は確認していません。値変換はソースの `std::atoi` と実際の使用箇所に基づき記載しました。
