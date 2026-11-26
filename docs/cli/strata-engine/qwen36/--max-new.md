# `strata` / `strata-q36` `--max-new`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--max-new` |
| 別名 | なし。`--n` は同じ生成数変数を設定する別オプション |
| 値 | 整数。Qwen parser は `std::atoi` で読み取る |

## 役割

非 serve の Qwen3.6 推論で生成する token 数を指定します。`strata` は `--model` または `--native` で指定された GGUF の family が Qwen3.6 (`qwen35moe`) なら、通常 engine の処理に入る前に Qwen 専用実装へ引数全体を渡します。単独 executable の `strata-q36` も同じ Qwen parser を使います（`engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-2`、`engine/src/qwen35/q36_engine.cu:5339-5356`）。

## 使い方

```sh
strata --model model.gguf --tokens 1,2,3 --max-new 32
strata-q36 --model model.gguf --tokens 1,2,3 --max-new 32
```

`--tokens` は token ID のプロンプト例です。実際の GGUF パスと入力 token 列に置き換えてください。

## 値と既定値

- 省略時は `64` token です（`engine/src/qwen35/q36_engine.cu:5342`）。
- 値は `std::atoi` で整数化されます。別名 `--n` も同じ `n_gen` を設定します。両方、または同一オプションを複数回指定した場合、引数を左から処理するため最後に現れた値が残ります（`engine/src/qwen35/q36_engine.cu:5348-5366`）。
- 値を省略すると `strata-q36: --max-new needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5348-5352`）。数値でない値を含む厳密な数値形式の validation はありません。`atoi` が変換できない値は 0 となり、通常の単独生成では生成ループが実行されず空の `gen:` が出ます（`engine/src/qwen35/q36_engine.cu:5356`、`5639-5653`）。

## 実行時の動作

通常の `--tokens` 実行では `n_gen` 回 greedy decode し、生成 token ID を stdout の `gen:` 行に出します。MTP が有効で forced token 列も logits dump もない場合は MTP の speculative loop が同じ上限まで生成します（`engine/src/qwen35/q36_engine.cu:5610-5637`、`5639-5657`）。この parser では `--greedy` も受理されますが、Qwen3.6 の `--tokens` 経路はもともと greedy とされ、`--max-new` は sampling を有効化しません（`engine/src/qwen35/q36_engine.cu:5354-5360`）。

`--force` で token 列を指定した場合は、その列の長さに 1 を足した値で `n_gen` が上書きされます。従ってこの場合 `--max-new` の指定値は使われません（`engine/src/qwen35/q36_engine.cu:5595-5597`）。

`--serve` では engine 起動後の各 `GEN` / `GENI` 要求が独自の `max_new` をプロトコル行で渡し、要求単位で 1 以上かつ prompt と合わせて context 内に収まるか検証します。起動時 `--max-new` の `n_gen` はこの上限を決めません（serve への分岐 `engine/src/qwen35/q36_engine.cu:5561-5562`、要求値の parse・検証 `engine/src/qwen35/q36_engine.cu:5025-5026,5067-5081`）。

## 適用条件と副作用

- `strata` の Qwen parser へ切り替わるのは、モデル指定から GGUF architecture が `qwen35moe` と判定された場合です。Qwen3.6 以外のモデルではこの `qwen36` scope の parser は使われません（`engine/src/program/generate.cpp:3804-3818`）。
- Qwen parser は `--max-new` の正数検証を行いません。0 以下では通常の token 生成ループは動きません。負数と MTP 有効・forced 列なしの組合せでは、speculative loop 後の `gen.resize((size_t)n_gen)` に負数が `size_t` として渡されます。正常な生成上限として使える値ではなく、例外等で異常終了する可能性があります（`engine/src/qwen35/q36_engine.cu:5614-5629`）。
- 生成経路で context を使い、serve 要求では prompt と `max_new` の合計が `E.ctx` を超える要求を拒否します。単独 `--tokens` 経路の `--max-new` と context 容量との境界について、parser 直後の同等な明示 validation は確認できませんでした。内部処理が許容する境界の詳細は本調査範囲では確定できません。
- ファイル出力の副作用はこのオプション自体にはありません。別オプション `--dump-full-logits` は単独生成の出力先を開きますが、その設定は本書の対象外です。

## 出力とエラー

値の不足は stderr と終了コード 2 になります。`--max-new` 固有の範囲エラーや警告は parser にありません。通常生成の生成 ID 列は stdout、生成数や時間の要約は stderr に出ます（`engine/src/qwen35/q36_engine.cu:5350-5352,5651-5657`）。serve の不正な要求は `ERR ...` 行を stdout に返し、engine 起動時の `--max-new` はこれらの要求上限を変更しません（`engine/src/qwen35/q36_engine.cu:5067-5081`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3818` — GGUF family による Qwen 専用 parser への dispatch。
- `engine/src/qwen35/q36_engine.cu:5342-5366` — 既定値、値変換、`--n` との共有。
- `engine/src/qwen35/q36_engine.cu:5595-5657` — forced token による上書き、通常生成・MTP の上限と出力。
- `engine/src/qwen35/q36_engine.cu:5025-5081` — serve protocol の要求ごとの上限と context validation。
