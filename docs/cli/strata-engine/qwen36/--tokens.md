# `--tokens`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family parser / `strata-q36` |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | prompt の token ID 列。カンマまたは空白で区切る |

## 役割

トークナイザーを介さず、数値 token ID の列を Qwen3.6 engine に prompt として渡します。Qwen3.6 専用 parser は `strata-q36` executable と、`strata` が Qwen3.6 family に切り替わった場合に使われます。通常 engine parser の `--tokens` とは別 scope です（索引の [Qwen3.6 節](../../README.md)）。

## 使い方

```sh
strata-q36 --model /path/to/model.gguf --tokens '248045,846,198' --n 32
```

`strata` から呼び出す場合も、Qwen3.6 family に選択されたとき専用 parser に引数が渡ります。Qwen3.6 専用実装では `--tokens-file` は定義されていません。

## 値と既定値

- 値は1つの文字列で、`,` または `strtol` が前置空白として扱う空白を区切りに読み取られます。usage にはカンマ区切り形式が記載されています。
- オプション自体に既定値はありません。通常の一回生成モードでは空の token 列となり、空列はエラーになります。`--tokens` を複数回指定すると、後の値が前の値を置き換えます。
- `parse_ids` は `strtol` で各数値の先頭部分を読み、`int32_t` に変換します。負数や語彙範囲外の値を拒否する検査はこの parser にありません。また、数値として読めない部分に達するとそこで解析を止め、すでに読んだ ID があればその列を返します。そのため、厳密な整数列 validation が必要な入力ではありません。
- 値を省略すると `strata-q36: --tokens needs a value` を stderr に出して終了コード 2 で終了します。

## 実行時の動作

通常の一回生成モードでは、読み取った列を `prompt` として `Engine::process` に渡し、その後 greedy token を生成します。`--n` と `--max-new` は同じ生成数を設定し、両方を指定した場合は後に現れた方が有効です。指定がなければ 64 です。`--force` の列が空でなければ、生成数はその列の長さ + 1 に置き換わります。`--greedy` はこの経路では何もせず、生成は元から greedy です。

`--tokens` は serve / benchmark と組み合わせても一回生成経路には使われません。serve mode は request ごとに token 列を受け取り、benchmark mode は別途合成 token 列を作ります。`--mtp` を有効にして通常生成する場合も同じ prompt を使い、MTP 経路で生成・検証します。

## 適用条件と副作用

- `--model` が必要です。通常生成では token 列が空だと、model load と（既定で有効な）warmup の後に必要引数エラーを出します。
- 通常の一回生成経路には、prompt 長と context 長の比較や prompt token ID の語彙範囲検査が見当たりません。`Engine::process` は受け取った列を chunk に分けて処理します。意図しない ID や context を超える列を安全に扱えるとはソースから確認できないため、有効な model の token ID と context 内に収まる列を指定してください。
- serve 経路では別途、各 request の token 列が空でないこと、`prompt + max_new` が context 内に収まること、各 ID が語彙範囲内であることを検査します。失敗 request は `ERR ...` を stdout に出し、その request を処理しません。
- `--tokens` 自体によるファイル書き込みやネットワーク通信はありません。通常生成は prompt と生成 token ID を `gen:` 行として stdout に出し、処理時間等を stderr に出します。

## 出力とエラー

- 通常生成で token 列が空の場合、`strata-q36: --tokens, --serve or --bench-pp is required` を stderr に出して終了コード 2 になります。
- `--tokens` に値がない場合は前述の parser エラーで終了コード 2 です。
- 一回生成経路に明示的な token 値検証がないため、不正値に対する専用エラー出力は確認できません。値の解釈で安全に処理できる範囲は parser だけから保証できません。

## 根拠

- 専用 parser と既定値: `src/qwen35/q36_engine.cu:3735-3761`（`tokens` の初期値、`--tokens`、`--n` / `--max-new`、`--greedy`）。
- token 列の読み取り規則: `src/qwen35/q36_engine.cu:3058-3069`。
- 通常生成の空列エラー、prompt 適用、出力: `src/qwen35/q36_engine.cu:3916-3933`, `src/qwen35/q36_engine.cu:3960-3978`。warmup 呼び出しは `src/qwen35/q36_engine.cu:3890`。
- prompt の chunk 処理: `src/qwen35/q36_engine.cu:2429-2470`。
- serve request の長さ・語彙検査: `src/qwen35/q36_engine.cu:3494-3512`。
- 独立 executable の entry point と build target: `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:790-794`。

調査はこの checkout のソースと索引に限定しました。同一 revision の既存バイナリによる `--help` は確認していません。専用 parser には `--help` action がなく、parser 宣言と処理箇所を根拠にしています。
