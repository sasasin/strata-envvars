# `STRATA_SPEC_WATCH`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

投機的デコードのループで進捗が止まった状態を検知し、停止段階と診断情報を stderr に出した後、engine プロセスを `abort()` で終了させる診断用 watchdog です。デコード方式や生成値を選ぶ設定ではありません。

## 値と判定

このコードは環境変数が設定されている場合に `std::atoi()` で整数へ変換し、その結果が正の場合だけ watchdog を起動します。文字列全体の妥当性検査はありません。

| 値 | 動作 |
|---|---|
| 未設定 | watchdog を起動しない |
| 空文字、数値に変換できない文字列、`0`、負値 | `atoi` の結果が 0 以下になり、起動しない |
| 正の整数になる文字列 | 監視を起動し、変換後の秒数を停止判定のしきい値にする |

`atoi` は先頭の空白と符号を許し、先頭の整数部分を読み取ります。たとえば `3seconds` は 3、`+3` は 3、`-3` は -3 として扱われます。数値の後ろに続く文字列は検査されません。`1.5` は 1 として扱われます。実装は環境変数を2回 `atoi` に渡し、最初の値で起動可否、次の値で秒数を決めます。

## 有効になる条件

- `src/program/generate.cpp` の投機的デコード処理まで実行が進んだ場合に評価されます。通常の非投機的な生成だけではこの箇所に到達しません。
- 値が正の整数に変換されることが必要です。値が有効でも、投機的デコードに入らない実行では監視スレッドは作られません。
- 対象箇所は `src/program/generate.cpp` です。調査対象 HEAD では同名変数の他の読み取り箇所は見つかりませんでした。`sycl/src/program/generate.cpp` に同じ環境変数の読み取りはありません。

## 実行時の詳細

条件を満たすと、コードは共有進捗状態の `busy` を `true` にして、秒ごとに進捗カウンター `beats` を確認する detached thread を起動します。`beats` が変化すると無進捗時間の計測をリセットし、しきい値の秒数を超えて変化しないと停止と判定します。監視スレッドは投機ループの区間内に作られますが、コード上は detached thread を停止・join する処理がこの箇所にありません。

停止時にはまず stderr に次の形式の行を出し、その後 `stall_report()` で現在の stage、最後の進捗以降に処理した layer 数、登録済み pool/verify/pipeline 診断、メモリ情報などを出力します。非 Windows ではディスク待ちスレッド情報も対象になります。Windows では条件が整えば thread stack を含む minidump も試みます。

```text
strata generate: no progress for <秒数> s (<stage>)
```

続けて `release_gpu_waits(stderr)` を呼び、GPU の待機を解放する診断 callback が登録されていれば実行してから、`std::abort()` します。したがって通常のエラー戻りや要求単位のキャンセルではなく、engine プロセスが異常終了する動作です。サーバーが終了した engine を再起動するかどうかはサーバー側の管理動作であり、この環境変数の処理自体は再起動しません。

## 根拠

- `src/program/generate.cpp:16229-16250` — 環境変数の読み取り、正値判定、進捗監視、stderr 出力、GPU wait 解放、`abort()`。
- `src/program/generate.cpp:1309-1314` — stage 表示の組み立て。
- `src/program/generate.cpp:1430-1485` — stall report の内容と Windows minidump 処理。
- `include/strata/core/progress.hpp:17-27,39-43,48-61` — 共有進捗カウンターと GPU wait release callback。
- `docs/release-notes-0.2.2.md:47` — 変数を「停止した投機的ループの stage を報告する watchdog」と記載。測定結果や `STRATA_SPEC_WATCH` の具体的な値の解釈は記載されていません。

