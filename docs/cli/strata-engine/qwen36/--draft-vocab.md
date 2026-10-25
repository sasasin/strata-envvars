# `--draft-vocab`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 engine parser（`strata --model` での family 振り分け、または `strata-q36`） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | 整数 `N`。MTP draft が候補にする先頭 `N` 個の token ID の行数 |

## 役割

Qwen3.6 の MTP draft が出力 head の全語彙ではなく先頭 `N` 行だけから候補を選べるようにします。draft は提案に使われ、検証窓が採用を決めるため、ソースコメント上は最終回答はこの値にかかわらず通常の greedy 結果です。`--mtp N` で MTP draft を有効にして使う設定です（`src/qwen35/q36_engine.cu:2107-2110,2142-2147,3767-3774,3882-3885`）。

このオプションは Qwen3.6 専用 parser のものです。通常の engine parser の `--mtp-draft-vocab FILE` や、setup CLI の `--draft-vocab en|cjk|...` とは別のオプションです。`strata` はモデルの family が `Qwen35Moe` の場合にこの parser へ切り替え、CMake は別 executable `strata-q36` も作ります（`src/program/generate.cpp:2399-2406`, `CMakeLists.txt:776-794`）。

## 使い方

```sh
strata --model /models/qwen36.gguf --mtp 4 --draft-vocab 65536 --tokens 1,2,3 --n 64
```

値は例として `65536` を示しています。適切な `N` の推奨値や性能効果はこの文書では断定しません。独立 executable では `strata-q36` が同じ `strata::qwen35::run` parser を呼びます（`src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- parser は次の引数を `std::atoi` で整数化します。値の形式・範囲を検査する validation はこの箇所にありません（`src/qwen35/q36_engine.cu:3740-3745,3774`）。
- `--draft-vocab` を省略した場合、初期値は `-1` です。`STRATA_Q36_DRAFT_VOCAB` が設定されていればその値を `atoi` で読み、設定がなければ `std::max(0, -1)` により `0` になります（`src/qwen35/q36_engine.cu:3740,3883-3885`）。
- `draft_n == 0` は全語彙を使う設定です。従って、引数・環境変数のいずれも指定しない場合の実効値は全語彙です（`src/qwen35/q36_engine.cu:2107-2110,3884-3885`）。
- 明示した値が環境変数より優先します。ただし、明示値が負数なら `draft_vocab < 0` の条件を満たして環境変数で置き換わります。環境変数がなければ負数も `0` に丸められます。明示した `0` は環境変数を参照せず全語彙を選びます（`src/qwen35/q36_engine.cu:3884-3885`）。
- 不正な数値文字列は `atoi` の結果 `0` となるため、全語彙扱いになります。数値で始まる余分な文字をどう扱うかも `atoi` に委ねられ、独自 validation はありません（`src/qwen35/q36_engine.cu:3774,3884`）。

## 実行時の動作

初期化後の値は `E.draft_n` に設定されます。MTP の draft head は `draft_n > 0` かつ語彙数より小さく、8 の倍数である場合などに、出力 head の先頭 `draft_n` 行だけを計算し、その中から argmax を選びます（`src/qwen35/q36_engine.cu:2111-2130,3882-3885`）。

値が `0`、語彙数以上、8 の倍数でない場合、または `fast_k`・head の型・形状などの条件を満たさない場合は、先頭 `N` 行の経路を使わず全語彙の `head_rows` に戻ります。これらの値はエラーにはならず、指定値のまま計算範囲だけが fallback します（`src/qwen35/q36_engine.cu:2111-2118`）。

この設定は `STRATA_Q36_DRAFT_VOCAB` からも受け取れます。コマンドライン値が負数または省略のときだけ環境変数を読む順序です。Qwen3.6 が family switch で起動された場合にも同じ parser と処理が使われます（`src/qwen35/q36_engine.cu:3882-3885`, `src/program/generate.cpp:2399-2406`）。

## 適用条件と副作用

- 対象は `src/qwen35/q36_engine.cu` の Qwen3.6 engine parser です。CMake 上、`STRATA_HIP_GFX906` では Qwen3.6 library / executable の追加と `strata` へのリンクが行われません（`CMakeLists.txt:776-794`）。
- MTP draft の head 計算に作用します。`--mtp` の値が正でモデルに MTP block がある場合に MTP draft 数が設定されます。`--draft-vocab` 単独では MTP を有効化しません（`src/qwen35/q36_engine.cu:3767-3774,3882-3885`）。
- 指定値に対する明示的な警告、ファイル操作、ネットワーク操作は parser / head の該当処理にはありません。無効化条件では全語彙計算へ戻ります（`src/qwen35/q36_engine.cu:2111-2118,3774,3884-3885`）。

## 出力とエラー

- 値を省略して `--draft-vocab` を渡すと、共通の `next()` が `strata-q36: --draft-vocab needs a value` を stderr に出して終了コード `2` で終了します（`src/qwen35/q36_engine.cu:3744-3746,3774`）。
- 負数、0、語彙数以上、8 の倍数でない値は、このオプション由来のエラーになりません。実行時の head 処理で全語彙経路へ fallback する条件があります（`src/qwen35/q36_engine.cu:2111-2118`）。
- `--draft-vocab` 自体に対応する usage 表示、値の validation error、通常時のログ出力は確認できません。未知オプションの場合は usage を stderr に表示してコード `2` を返しますが、本オプションは parser に登録済みです（`src/qwen35/q36_engine.cu:3782-3795`）。

## 根拠

- Qwen3.6 parser、初期値、引数消費、環境変数との合成: `src/qwen35/q36_engine.cu:3735-3779,3882-3888`
- draft head の subset / fallback と最終回答に関する説明: `src/qwen35/q36_engine.cu:2107-2130,2142-2147`
- `strata` の family switch: `src/program/generate.cpp:2399-2406`
- 独立 executable と build 条件: `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:776-794`
- 同じ文字列を持つ別 CLI との区別: 索引 [`docs/cli/README.md`](../../README.md) の `strata-engine` / `strata-engine/qwen36` scope と setup の項目。source 側の setup parser は `setup.py:8518`。

調査範囲は記載した checkout のソースです。同一 revision の実行バイナリによる `--help` は確認していません。値の有効域を model vocab に照らした実行時検査もこの parser / draft head では確認できません。
