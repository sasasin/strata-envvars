# `STRATA_DUMMY_NODES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP エンジンの verifier が verify window の GPU 処理を記録するとき、値 `k` に応じて空の kernel launch を追加する計測用スイッチです。通常値は 0 で追加 launch はありません。正の値では、各層・各 group の layer 前処理に `k` 個ずつ追加します。空 kernel はデータを読み書きせず、推論計算や出力 token の選択を変更しません。読み取りと追加箇所は `Verifier::record_window` の `pre` lambda 内です（`engine/src/core/verify.cpp:1681-1683,1820-1824`）。

`gpu_noop` の CUDA 実装は空の kernel を 1 block・32 thread で同じ stream に launch します（`engine/src/kernels/cuda/verify_kernels.cu:2025-2028`）。ヘッダーのコメントは「one-thread kernel」と記していますが、実装の block size は 32 です（`engine/include/strata/kernels/verify_kernels.hpp:123-127`）。この環境変数を読む箇所は CUDA/HIP 側の `engine/src/core/verify.cpp` だけで、別実装の SYCL verifier には名前の参照がありません。Metal の `gpu_noop` は未実装関数へ委譲する stub です（`engine/metal/src/engine/stubs.cpp:216`）。したがって、このスイッチが追加 kernel を動かすのは CUDA/HIP の verifier 経路です。

## 値と判定

`std::getenv` が null なら 0、設定されていれば `std::atoi` の結果を関数内 `static const int` に保存します。文字列全体の検証はなく、`atoi` が先頭から変換できた整数が使われます。未設定・空文字・整数に変換できない先頭文字は 0 です。先頭空白と符号は `atoi` の変換規則に従い、整数の後ろの文字列は検査されません。コードに範囲検査や clamp はありません（`engine/src/core/verify.cpp:1821-1823`）。

| 条件 | unset | 追加 launch あり | launch なし |
|---|---:|---|---|
| CUDA/HIP verifier がこの箇所を実行 | 0 | 変換結果が正（例: `1`, `+2tail`, ` 3x`） | 空文字、`0`, `-1`, `true`, `false`, `0anything`, `x1` |
| SYCL / Metal 経路 | この変数を読まない | 該当なし | この変数による追加なし |

ループ条件は `d < dummy` なので、0 以下では launch しません。`1anything` は 1、`0anything` は 0 として扱われます。`atoi` の戻り値が `int` の表現範囲を超える入力について、コードは範囲を検査せず、その挙動を定めていません。

## 有効になる条件

- CUDA/HIP エンジンの verifier が `record_window` を記録し、`pre` の該当箇所まで実行する必要があります。通常 window と batch window の双方が `record_window` を呼びます（`engine/src/core/verify.cpp:3279,4689`）。
- 追加数は verifier が処理する層範囲と group 数に依存します。`record_window` は `pre` を初期層から各 group について呼び、後続層も group ごとに呼びます（`engine/src/core/verify.cpp:1482-1486,2996-3002`）。split 等で `G` が 2 なら各層に 2 group 分の追加があり、通常の `G == 1` なら 1 group 分です。
- 値が正でも、SYCL の別 `record_window` 実装では環境変数を読まないため有効になりません。Metal にも読み取り箇所はありません。
- CLI 引数、別環境変数、モデル状態による上書きや値の優先順位は、この読み取り箇所にはありません。

## 実行時の詳細

読み取りは `pre` lambda 内の block-local `static` の初期化時に一度行われ、結果はプロセス内でキャッシュされます。したがって、最初の到達後にプロセス環境を変更しても値は更新されません。CUDA 側では `record_window` が stream capture 中に呼ばれるため、追加された各 `gpu_noop` launch は window の graph に含まれます（`engine/src/core/verify.cpp:3270-3281`）。再利用される graph は記録済みの node 数を再実行し、環境を読み直しません。

各層の `pre` では fused read の後、入力待ち処理・次の stamp より前に no-op launch を enqueue します（`engine/src/core/verify.cpp:1816-1829`）。これは計測用に kernel launch/node の負荷を加えるもので、値の数だけ同じ stream 上に空 kernel の graph node を増やします。

## ログと測定値

この環境変数の値や有効化を示す専用ログは読み取り・分岐箇所にありません。ソースコメントは「measurement only」と用途を記しますが、`docs/DETAILS.md` にこの変数の測定値や測定条件の記載は見つかりません。kernel launch に起因する失敗が起きた場合の一般的な capture / graph 経路はありますが、この変数専用のエラー文言はありません（`engine/src/core/verify.cpp:3270-3285`）。

## 根拠

- `engine/src/core/verify.cpp:1681-1683,1816-1829` — `pre` と環境変数の読み取り、no-op の配置。
- `engine/src/core/verify.cpp:1482-1486,2996-3002` — 対象層範囲、group ごとの呼び出し。
- `engine/src/core/verify.cpp:3270-3285,4680-4696` — 通常・batch window の capture と graph 記録。
- `engine/src/kernels/cuda/verify_kernels.cu:2025-2028` — 空 kernel と CUDA/HIP stream launch 実装。
- `engine/include/strata/kernels/verify_kernels.hpp:123-127` — kernel API とコメント。
- `engine/metal/src/engine/stubs.cpp:216` — Metal stub。
