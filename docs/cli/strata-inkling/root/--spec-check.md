# `--spec-check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--spec-check N` |
| 別名 | なし |
| 値 | 生成トークン数を表す整数。`N > 0` のとき診断を実行 |

## 役割

greedy の通常実行を2回繰り返した結果、D-Spark の推測実行を含む結果、複数トークンをまとめて forward した結果を比較し、推測実行が通常実行と一致するか、バッチ処理の logits が1件ずつ処理した値と一致するかを調べます。サーバーを起動するオプションではありません。parser は整数変換した値を `spec_check_n` に保存し、値が正の場合に専用処理へ分岐します（`engine/src/inkling2/ink_main.cpp:842-843,966-968,1062-1069`）。

## 使い方

```sh
# モデルと整数 token ID のプロンプトを指定し、16 token 分を比較する
strata-inkling --native MODEL.strata --prompt-ids 1,2,3,4 --spec-check 16
```

`--prompt-ids` はカンマ区切りの整数列を受け取ります。`@FILE` を指定するとファイル内容を読み込みます（`engine/src/inkling2/ink_main.cpp:957-963`）。

## 値と既定値

`N` は `std::atoi` で整数に変換され、既定値は `0` です。正の値だけが診断分岐を起動し、0以下では起動しません。明示的な範囲検証はありません。したがって数値に変換できない値も `atoi` により0となり、診断を起動しません。複数回指定した場合は parser が順に代入するため最後の値が使われます（`engine/src/inkling2/ink_main.cpp:842-843,966-968,1062`）。

値を省略すると `missing value after --spec-check` を標準エラーへ出して終了コード2で終了します（`engine/src/inkling2/ink_main.cpp:845-849`）。

## 実行時の動作

正の値を指定すると `--prompt-ids` が必須です。値が空、または整数列として解析できない場合はエラーメッセージを標準エラーへ出して終了コード2で終了します。`@FILE` の読み込みに失敗した場合も parser が終了コード2を返します（`engine/src/inkling2/ink_main.cpp:957-963,1062-1069`）。ID 列の解析関数は10進整数を列挙して空でないことを確認しますが、語彙範囲の検証はこの関数では行いません（`engine/src/inkling2/ink_serve.h:290-305`）。

診断処理はモデルを開き、backend を初期化して1 slot を確保した後、指定プロンプトを prefill します。コンテキスト長は少なくとも「プロンプト長 + N + 64」となるよう調整され、並列 slot 数は1に固定されます。また D-Spark を有効にして通常の greedy 結果と、serve loop に沿った推測結果を比較します（`engine/src/inkling2/ink_main.cpp:599-623`）。モデルを開けない、backend 初期化・slot 確保に失敗する、prefill や生成時の forward に失敗する場合は標準エラーへ理由を出し、終了コード1になります（`engine/src/inkling2/ink_main.cpp:601-629,674-687,706,723-727`）。

比較は、(1) B=1 の通常 greedy を2回行い token ID と logits hash を比較、(2) 通常 greedy と推測生成の token ID を比較、(3) M=2,3,4,8 の複数行 forward の logits を B=1 の対応位置と bitwise 比較、(4) 8 token 以上生成できた場合は drafter が読む4箇所の hidden-state tap を比較、の順です。token ID または logits の比較で差異があれば `DIFFERS` を出力し終了コード1、これらが一致すれば `identical` を出力し終了コード0です。tap の差は別途表示されますが終了コードには反映されません（`engine/src/inkling2/ink_main.cpp:656-670,672-757,759-823`）。

`N=1` の場合、各通常実行と推測実行は prefill 後の最初の top-1 token を記録して終了します。生成 token を入力する後続 step や推測 loop は実行されないため、この値では verify-window 比較も行われません（`engine/src/inkling2/ink_main.cpp:632-654,672-683,759-762`）。

## 適用条件と副作用

`--native`（別名 `--model`）でモデルを指定して使います。モデル指定がないと専用処理側でモデルを開けず、終了コード1になります。`--cpu` はbackend選択に渡されます。`--dspark` のパスもモデル読込と推測処理へ渡されます（`engine/src/inkling2/ink_main.cpp:870-871,906-907,599-611`）。

この分岐では通常の `--parallel` の設定を1 slotに上書きし、`--draft` の設定にかかわらず D-Spark を有効にします。`--gen` は別の `bench_gen` に代入されるため、このモードの生成数は `--spec-check N` が決めます（`engine/src/inkling2/ink_main.cpp:877-878,895-898,955-956,604-607`）。

先行する `--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref`、`--ring-check`、`--batch-check` の分岐が有効な場合は、そちらが `--spec-check` より先に処理されます。一方 `--bench` よりは `--spec-check` が先に処理されます（`engine/src/inkling2/ink_main.cpp:1039-1071`）。

診断結果や fingerprint は標準出力へ出力されます。`STRATA_SPEC_CHECK_IDS=1` は比較した token ID 列も出力し、`STRATA_SPEC_CHECK_QUICK=1` は推測結果の比較後に verify-window 比較を省略します。`STRATA_SPEC_CHECK_STEPS=1` は通常実行の各 step の logits hash と top-1 ID を出力します（`engine/src/inkling2/ink_main.cpp:637-642,745-755`）。モデル・backend の計算と読み込みを行いますが、この処理経路に結果ファイルへの書き出しはありません。

## 出力とエラー

診断は標準出力に各比較結果、比較回数、fingerprint、最後に `RESULT: identical` または `RESULT: DIFFERS` を出します。通常実行2回の差、推測結果の差、verify-window logits の差はいずれも終了コード1に反映されます。tap の差は詳細行に出ますが、このコードではそれだけで `rc` を変更しません（`engine/src/inkling2/ink_main.cpp:659-670,731-755,759-823`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:842-843,966-968` — 初期値と parser 登録、整数変換。
- `engine/src/inkling2/ink_main.cpp:957-963,1062-1069` — `--prompt-ids` の値処理と必須条件、診断への分岐。
- `engine/src/inkling2/ink_serve.h:290-305` — token ID 列の構文解析。
- `engine/src/inkling2/ink_main.cpp:599-629` — モデル/backend/slot の準備、コンテキスト調整、prefill。
- `engine/src/inkling2/ink_main.cpp:656-823` — 比較内容、結果出力、終了コード。
- `engine/src/inkling2/ink_main.cpp:1039-1075` — 他モードとの分岐順。
