# `STRATA_SPLIT_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

serve のリクエスト処理後に、各 verifier stage の window 数と、window あたりの host 側時間を stderr に出す診断スイッチです。検証や layer split の処理を切り替えるコードではなく、既に集計されている時間を表示する条件だけを変えます。通常 engine と SYCL engine の両方に同じ判定と出力があります（`engine/src/program/generate.cpp:23898-23906`、`engine/sycl/src/program/generate.cpp:13236-13244`）。

## 値と判定

両実装とも `std::getenv("STRATA_SPLIT_TIMING") != nullptr` の真偽だけを使います。値の parse、空白除去、大文字小文字変換、数値判定はありません。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常 engine（`engine/src/program/generate.cpp`） | 出力しない | 空文字、`0`、`false`、`1`、`0anything` など、値を問わず設定されていれば出力 | なし（環境変数が存在する場合） |
| SYCL engine（`engine/sycl/src/program/generate.cpp`） | 出力しない | 空文字、`0`、`false`、`1`、`0anything` など、値を問わず設定されていれば出力 | なし（環境変数が存在する場合） |

## 有効になる条件

- 上記の engine 実装を使い、serve のリクエスト完了処理まで実行することが必要です。値はその完了処理の診断出力を有効にします（`engine/src/program/generate.cpp:23576-23585,23898-23906`、SYCL 側: `engine/sycl/src/program/generate.cpp:13130-13135,13236-13244`）。
- `n_stages` が 1 の場合も stage 0 の行を出します。複数 stage の場合は `0` から `n_stages - 1` までを出力します。通常 engine では `n_stages` は分割 GPU がないと 1、分割があると `split_at.size() + 1` です（`engine/src/program/generate.cpp:13252-13256`）。
- 他の環境変数や CLI 引数によるこのログの抑止・上書きは、該当する出力条件にはありません。stage 数自体は実行時の分割構成で決まります。

## 実行時の詳細

判定は出力箇所の関数ローカル `static const bool` で初回に評価され、その後のリクエストではキャッシュされた値を使います。したがって、判定が初めて実行された後にプロセス環境を変更しても、このスイッチの値は再評価されません（`engine/src/program/generate.cpp:23900`、`engine/sycl/src/program/generate.cpp:13238`）。

リクエスト完了後、各 stage の `Verifier` から `windows` と `ms_wait`、`ms_pool`、`ms_host`、`ms_commit` を読み、各時間を window 数で割って 3 桁のミリ秒で表示します。window 数が 0 の場合は除数を 1 とします。出力時にカウンターをリセットしたりリクエスト単位の差分を取ったりせず、`Verifier` に蓄積された値を使います。カウンターのフィールドは `engine/include/strata/core/verify.hpp:455-456` にあり、SYCL 側にも同じフィールドがあります（`engine/sycl/include/strata/core/verify.hpp:278`）。

## ログと測定値

環境変数が設定されている場合、stage ごとに次の形式を stderr に出します（数値は実行時の値です）。

```text
strata serve: stage 0: <windows> windows; per window: wait for the GPU <ms> ms, pool + plan <ms> ms, host staging <ms> ms, commit <ms> ms
```

実装上の出力書式は `engine/src/program/generate.cpp:23904-23906` と `engine/sycl/src/program/generate.cpp:13242-13244` にあります。この変数に伴う警告・エラー・終了経路はありません。`docs/DETAILS.md` にこの変数の測定結果はなく、調査対象はログ出力の実装に限ります。

## 根拠

- `engine/src/program/generate.cpp:23898-23906` — 設定有無の判定、stage ループ、stderr の書式と値。
- `engine/sycl/src/program/generate.cpp:13236-13244` — SYCL 側の同じ判定と出力。
- `engine/src/program/generate.cpp:13252-13256` — 通常 engine の stage 数と stage verifier の対応。
- `engine/include/strata/core/verify.hpp:455-456`、`engine/sycl/include/strata/core/verify.hpp:278` — 集計カウンターのフィールド。
- `engine/src/program/generate.cpp:23576-23585`、`engine/sycl/src/program/generate.cpp:13130-13135` — 診断箇所の前にある serve の応答完了処理。
