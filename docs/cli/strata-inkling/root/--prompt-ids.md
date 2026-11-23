# `strata-inkling --prompt-ids`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root、CUDA/HIP） |
| オプション | `--prompt-ids` |
| 別名 | なし |
| 値 | 必須。カンマ区切りの10進 token ID 列（文字列） |

## 役割

通常の直接生成モードに入力する token ID 列を指定します。同じ値は `--dump-ref` の teacher-forced reference logits 作成にも使われます。自然言語の tokenizer 入力ではなく、モデルの token ID を直接与えるオプションです。

## 使い方

```sh
# 3 個の token ID を prompt として直接生成する
strata-inkling --native model.strata --prompt-ids 200002,200004,100 --gen 32

# 同じ ID 列で reference logits をファイルに書き出す
strata-inkling --native model.strata --dump-ref reference.bin --prompt-ids 200002,200004,100
```

## 値と既定値

- 値は次の引数文字列 1 個です。parser は各 ID を `strtol(..., 10)` で読み、カンマを区切りとして `int32_t` 列に格納します（`engine/src/inkling2/ink_main.cpp:482-483`、`engine/src/inkling2/ink_serve.h:256-271`）。
- 別名はありません。parser は同じオプションが複数回あれば文字列を都度代入するため、最後の指定が残ります（`engine/src/inkling2/ink_main.cpp:379-384,482-483`）。
- 省略時、通常の直接生成は組み込み token 列 `{200002, 200004, 100, 200010, 200000, 200004, 101, 200010, 200001, 200004}` を使います。`--dump-ref` は別の既定列 `{1, 2, 3, 4, 5, 6, 7, 8}` を使います（`engine/src/inkling2/ink_main.cpp:334-339,580-585`）。
- 空文字列は `prompt_ids_str.empty()` により「未指定」と同じ扱いです（`engine/src/inkling2/ink_main.cpp:334-339,580-585`）。
- `parse_id_list` が失敗するのは ID を一つも読み取れない場合、または読み取り位置で整数を開始できない場合です。`strtol` が受理する符号・空白の扱い、整数の `int32_t` 範囲超過や語彙範囲は、この関数では検査されません。末尾カンマも追加 token なしで受理されます（`engine/src/inkling2/ink_serve.h:256-271`）。値の安全な範囲は当該 parser からは確定できません。

## 実行時の動作

通常の直接生成では列を `StepBatch` に prompt として積み、backend で prefill した後、その ID 列を生成履歴に初期化して sampling に渡します（`engine/src/inkling2/ink_main.cpp:575-604`）。token ID 列は stdout に出力される生成結果の初期文脈になります。

`--dump-ref` と併用すると通常の生成経路より先に dump 処理へ分岐し、指定列（または dump 用既定列）で forward した logits と token ID を `--dump-ref` の出力ファイルにバイナリ形式で書きます（`engine/src/inkling2/ink_main.cpp:324-357,544-549`）。

この値は全モード共通ではありません。`--serve` は server loop に進んでから各リクエストの prompt を処理するため、この起動時オプションを読みません（`engine/src/inkling2/ink_main.cpp:571-573`）。`--kld-eval` と `--bench` も先に別処理へ return するので、指定した `--prompt-ids` は使われません（`engine/src/inkling2/ink_main.cpp:544-549`）。

## 適用条件と副作用

対象は索引上の `strata-inkling` root（CUDA/HIP）です。Metal と SYCL は別コマンド階層です。SYCL 側では `--prompt-ids` が `--prompt-tokens` の別名として索引化されていますが、本書のオプションとはスコープが異なります（`docs/cli/README.md:1509-1549,1572-1588`）。

通常生成では指定した全 ID を prefill に渡します。parser は語彙 ID の上下限や prompt 長を検証しません（`engine/src/inkling2/ink_serve.h:256-271`）。backend が不正な ID や長さをどう扱うかは、ここで確認した CLI 側の検証からは保証できません。`--dump-ref` では出力先をバイナリファイルとして作成・上書きします（`engine/src/inkling2/ink_main.cpp:349-355`）。

## 出力とエラー

- オプション値が欠けると `missing value after --prompt-ids` を stderr に出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:381-384`）。
- ID 列を解析できない場合は `bad token id list` を stderr に出し、通常生成または `--dump-ref` の経路で終了コード 2 を返します（`engine/src/inkling2/ink_serve.h:256-271`、`engine/src/inkling2/ink_main.cpp:334-339,580-583`）。
- 通常生成では生成 token ID をカンマ区切りで stdout に出します（`engine/src/inkling2/ink_main.cpp:598-605`）。`--dump-ref` では書き込み成功時に出力先、token 数、語彙数、backend 名を表示し、書き込みに失敗すると stderr に `dump-ref: cannot write ...` を出して終了コード 1 を返します（`engine/src/inkling2/ink_main.cpp:349-357`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384,482-483` — root parser の値取得と欠落値のエラー。
- `engine/src/inkling2/ink_serve.h:256-271` — token 列の解析方法と失敗条件。
- `engine/src/inkling2/ink_main.cpp:324-357,544-549` — `--dump-ref` 経路、既定列、ファイル出力。
- `engine/src/inkling2/ink_main.cpp:575-613` — 通常生成での prefill、履歴への利用、生成出力。
- `docs/cli/README.md:1509-1549,1572-1588` — 対象 root scope と Metal/SYCL の別 scope。
