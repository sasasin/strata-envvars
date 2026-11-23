# `--kld-eval`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--kld-eval` |
| 別名 | なし |
| 値 | 必須。`--dump-ref` が出力する参照 logits ファイルのパス |

## 役割

指定した参照ファイルとモデルを同じトークン列で teacher-forced forward し、各位置の logits から平均 KL divergence、Top-1 一致率、Perplexity を計算します。量子化形式や backend などを変えたモデル出力を参照 logits と比較する用途です。参照ファイルは `--dump-ref` で作成できます。

## 使い方

```sh
# 参照 logits を使ってモデル出力を評価する
strata-inkling --kld-eval reference.bin --native model.strata

# CPU backend を指定して同じ評価を行う
strata-inkling --kld-eval reference.bin --native model.strata --cpu
```

`--native`（別名 `--model`）で評価対象モデルを指定します。`--cpu` を付けない場合は、そのビルドで利用可能な既定 backend が選択されます。

## 値と既定値

- 値は参照ファイルのパスです。オプション直後に引数がなければ `missing value after --kld-eval` を標準エラーへ出し、終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:379-383,400-401`）。
- 既定値はありません。値を受け取る parser は独自の引数走査で、パスを `kld_ref` に保存します（`engine/src/inkling2/ink_main.cpp:375,379-383,400-401`）。
- 空文字列を値にした場合は `kld_ref.empty()` となるため評価分岐に入りません。その後は別モードまたは通常生成の経路へ進みます（`engine/src/inkling2/ink_main.cpp:547-553`）。
- 同じオプションを複数回指定すると、走査中に `kld_ref` が後の値で置き換わります（`engine/src/inkling2/ink_main.cpp:379-383,400-401`）。

参照ファイルは、先頭から `int32 n_tokens`、`int32 vocab_unpadded`、`n_tokens` 個の `int32` token ID、`n_tokens × vocab_unpadded` 個の `float` logits を格納したバイナリです。実装は各要素をネイティブ表現のまま読みます。`--dump-ref` は同じ並びで書き出します（`engine/src/inkling2/ink_main.cpp:252-254,263-269,349-355`）。

## 実行時の動作

parser が読み取った参照パスは、`--native` のモデルパス、backend 設定、CPU 強制フラグとともに評価関数へ渡されます。評価関数は参照ファイルを開いて全 token ID と logits を読み、モデルを開き、backend を初期化して slot 0 を確保します。モデル語彙数と参照ファイルの語彙数を比較した後、全 token ID を位置 `i` の入力として一括 forward し、各位置 `t` では参照分布とモデル分布の KL、argmax の一致、次 token `ids[t+1]` に対する NLL を計算します。最後に `n_tokens - 1` 位置の平均値を出力します（`engine/src/inkling2/ink_main.cpp:254-320`）。

評価モードの選択は parser 完了後に行われます。`--info`、`--export-tokenizer`、`--selfcheck` が同時に指定されている場合はそれらが先に選択され、`--kld-eval` は `--dump-ref`、`--bench`、serve／通常生成より先に選択されます（`engine/src/inkling2/ink_main.cpp:544-553`）。通常の評価では `--native` が必要です。パスが空または不正ならモデル読み込みが失敗します（`engine/src/inkling2/ink_main.cpp:275-279`）。

## 適用条件と副作用

- この文書の対象 scope は索引にある CUDA/HIP 系 `strata-inkling` です。実際に選ばれる非 CPU backend はビルド条件によって異なり、`--cpu` を付けると CPU backend を選びます（`engine/src/inkling2/ink_backend.h:150-168`）。
- `--gpu`、`--gpus`、`--kv-dtype` など parser が受け付ける共通 backend 設定は評価関数にも渡されます。ただし、その設定が特定 backend でどう実装されるかは各 backend とビルドに依存します（`engine/src/inkling2/ink_main.cpp:404-475,544-549`; `engine/src/inkling2/ink_backend.h:150-168`）。
- `--kld-eval` 自体は参照ファイルを読み込み、モデルを開いて backend forward を実行します。出力ファイルは作成しません。評価用 backend の初期化・推論に伴うメモリおよびデバイス利用が発生します（`engine/src/inkling2/ink_main.cpp:254-289`）。
- ヘッダーでは `n_tokens > 1` を検査し、参照語彙数とモデル語彙数の一致を検査します。ソース上、`V_ref` の正値検査、token ID の範囲検査、余剰データの検査は確認できません（`engine/src/inkling2/ink_main.cpp:257-282`）。不正な参照ファイルに対するこれらのケースの安全な処理は、この実装からは保証できません。

## 出力とエラー

- 成功時は標準出力に `[kld-eval] n=... | Mean KLD=... | Top-1=...% | PPL=...` を出し、終了コード `0` を返します（`engine/src/inkling2/ink_main.cpp:318-320`）。
- 参照ファイルを開けない、ヘッダーが読めない／`n_tokens <= 1`、必要なデータが不足、モデルを開けない、backend 初期化または forward に失敗した場合は標準エラーへ理由を出し、終了コード `1` を返します（`engine/src/inkling2/ink_main.cpp:255-279,287-289`）。
- 参照語彙数とモデル語彙数が異なる場合は `vocab mismatch ...` を標準エラーへ出し、終了コード `1` で終了します（`engine/src/inkling2/ink_main.cpp:281-282`）。
- オプション値が欠けている場合の終了コードは `2` です（`engine/src/inkling2/ink_main.cpp:379-383`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,400-401` — CLI 引数の取得、必須値の扱い。
- `engine/src/inkling2/ink_main.cpp:252-320` — 参照形式、検証、モデル推論、指標計算、出力と失敗経路。
- `engine/src/inkling2/ink_main.cpp:544-553` — `--kld-eval` と他モードの選択順、モデル未指定時の通常経路。
- `engine/src/inkling2/ink_main.cpp:323-357` — `--dump-ref` が参照ファイルを作成する形式。
- `engine/src/inkling2/ink_backend.h:150-168` — build 条件および `--cpu` による backend 選択。
