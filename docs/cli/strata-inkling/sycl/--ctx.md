# `strata-inkling-sycl --ctx`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--ctx` |
| 別名 | `--max-context` |
| 値 | 整数。実効値は最低 256。ソース上の上限検証はない |

## 役割

SYCL runner が確保する context 長を指定します。全体 attention の KV cache の stride と、DSpark が有効な場合の DSpark context cache の長さに使われます。指定値が大きいほどこれらの GPU メモリ確保量が増え、並列 slot 数との積でさらに増加します。

## 使い方

```sh
# 最大 context 長を 8192 にして SYCL エンジンを初期化する
strata-inkling-sycl --model ./model.strata --ctx 8192
```

`--ctx` と `--max-context` は同じ値を設定します。両方または同じ表記を複数回指定した場合、引数走査で後に現れた値が残ります（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`）。

## 値と既定値

- 省略時は `4096` です（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-105`）。
- parser は値を `std::atoi` で `int` に変換し、`--ctx` と `--max-context` のどちらでも同じ変数 `max_ctx` に代入します。専用の数値形式・範囲検証はありません（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-126`）。
- runner は `std::max(256, ctx_len)` を使うため、0、負数、および 256 未満の値は実効値 256 になります。上限値を丸める処理はこの箇所にありません（`engine/src/inkling2/sycl/ink_sy_runner.h:223-229`）。
- 引数値が欠けた場合も `need()` は空文字列を返し、それが `atoi` に渡されます。parser 自身が「値が必要」というエラーを出す実装ではありません（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-126`）。

## 実行時の動作

モデルのロード後、main は `max_ctx` を `InkSyRunner::init` に渡します（`engine/src/inkling2/sycl/ink_sy_main.cpp:183,198-203`）。runner は各 visit の KV cache を確保し、SWA visit にはモデルの `swa_win`、それ以外には実効 `max_ctx` を stride として使います。K/V それぞれに `max_slots × stride × n_kv × head_dim` 個の half を確保します（`engine/src/inkling2/sycl/ink_sy_runner.h:223-247`）。

モデルが DSpark を持ち、かつ `--no-dspark` が指定されていない場合、runner は `max_slots × max_ctx × 1024` 個の half を各 3 層の DSpark K/V cache に確保します。DSpark 無効時はこの追加 cache を確保しません（`engine/src/inkling2/sycl/ink_sy_runner.h:223-229,313-325`）。

`--parallel` は通常の初期 slot 数となり、`--par-sweep` 指定時は 64 slot で初期化されます。runner は slot 数を 1〜64 に制限するため、これらは `--ctx` による KV 確保量と乗算で関係します（`engine/src/inkling2/sycl/ink_sy_main.cpp:198-201`; `engine/src/inkling2/sycl/ink_sy_runner.h:223-228`）。

DSpark の greedy decode では、現在位置が context の末尾 8 token に達すると speculative draft を使わず、通常の 1 token forward に進みます（`engine/src/inkling2/sycl/ink_sy_main.cpp:52-71`; `engine/src/inkling2/sycl/ink_sy_runner.h:835-840`）。

## 適用条件と副作用

- この記述は SYCL 用の `strata-inkling-sycl` parser と runner に限定されます。CUDA/HIP や Metal の同名オプションの挙動は対象外です。
- context 長に比例する KV cache を GPU device memory に確保します。長い値や多数 slot の組み合わせでは device memory 不足になり得ます。確保失敗時、`dalloc` は要求 byte 数・累積確保量を含む診断文字列と `out of device memory` を `strata::core::exit_device_error` に渡します（`engine/src/inkling2/sycl/ink_sy_common.h:228-238`）。同 helper の実装は確認範囲内で見つからず、最終的な表示形式・終了コードはここでは確定できません。
- runner 初期化が成功すると stderr に `runner ready: ... ctx=<実効値> ...` を出します（`engine/src/inkling2/sycl/ink_sy_runner.h:328-335`）。
- この CLI の model load 呼び出しでは追加 reserve に `0` を渡し、その後 runner cache を確保します（`engine/src/inkling2/sycl/ink_sy_main.cpp:183,198-203`）。したがって、この呼び出し経路で `--ctx` に応じた KV 量を model load の expert 配置用 reserve に反映する処理は確認できません。

## 出力とエラー

runner cache の device allocation が失敗した場合は、前述の `dalloc` から `exit_device_error` へ進みます。runner の成功ログには clamp 後の context 値が含まれます（`engine/src/inkling2/sycl/ink_sy_common.h:229-238`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-335`）。`--ctx` 固有の validation error、警告、または上限超過時の拒否経路は parser・runner の確認範囲では見つかりませんでした。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:103-126` — 既定値、`--ctx` / `--max-context` の別名、値変換。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:183,198-203` — model load 後に parser 値を runner 初期化へ渡す経路。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-247,313-335` — 最低値 clamp、slot 数、通常 KV / DSpark cache 確保、成功ログ。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:52-71`; `engine/src/inkling2/sycl/ink_sy_runner.h:835-840` — context 末尾で speculative draft から通常 forward に切り替える条件。
- `engine/src/inkling2/sycl/ink_sy_common.h:228-238` — device memory 確保失敗時に渡す診断内容。
